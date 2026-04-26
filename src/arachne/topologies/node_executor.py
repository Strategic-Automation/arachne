"""NodeExecutor -- individual node execution logic.

Wraps a NodeDef into a typed DSPy module with optional tools, handles
signature building, module selection (Predict/CoT/ReAct/PoT), and
async execution with thread-local LM context.
"""

import asyncio
import logging
from typing import Any

import dspy
from dspy.adapters.chat_adapter import ChatAdapter
from dspy.adapters.json_adapter import AdapterParseError

from arachne.config import Settings, check_deno_installed, get_model_limits, get_rlm_sub_lm_kwargs
from arachne.runtime.token_manager import compress_payload, count_tokens
from arachne.skills import registry as skills
from arachne.topologies.schema import NodeDef, NodeRole
from arachne.topologies.tool_resolver import ToolResolver

logger = logging.getLogger(__name__)


class NodeExecutor:
    """Wraps a NodeDef into a typed DSPy module and executes it."""

    def __init__(self, node: NodeDef, settings: Settings, goal: str = "") -> None:
        self.node = node
        self.settings = settings
        self.goal = goal
        self._tool_resolver = ToolResolver(settings)
        self._tool_names = [t.name for t in node.tools]
        self._mcp_servers = node.mcp_servers
        self._tools = None
        self._adapter = None
        self._supports_function_calling = None
        self.module = None

    def _get_adapter(self) -> Any:
        """Get adapter based on detected model capabilities."""
        if self._adapter is not None:
            return self._adapter

        limits = get_model_limits(self.settings.llm_model, self.settings)
        self._supports_function_calling = limits.supports_function_calling

        if limits.supports_function_calling:
            self._adapter = ChatAdapter(use_native_function_calling=True)
        else:
            self._adapter = ChatAdapter()

        return self._adapter

    # ------------------------------------------------------------------
    # Signature & module construction
    # ------------------------------------------------------------------

    def _is_root_node(self) -> bool:
        """Check if this node has no upstream dependencies."""
        return not self.node.depends_on and not self.node.inputs

    def _build_signature(self) -> type[dspy.Signature]:
        """Create a dynamic DSPy Signature from the NodeDef description and I/O fields."""
        skill_texts = []
        for skill_name in self.node.skills:
            content = skills.get(skill_name)
            if content:
                logger.debug("Injected skill: %s into node %s", skill_name, self.node.id)
                skill_texts.append(f"## Skill: {skill_name}\n{content}")
            else:
                logger.warning("Skill NOT FOUND: %s for node %s", skill_name, self.node.id)

        base_desc = self.node.description
        if skill_texts:
            base_desc = base_desc + "\n\n" + "\n\n".join(skill_texts)

        # Inject prior search history from earlier healing attempts in this session
        from arachne.runtime.search_memory import get_store

        store = get_store()
        if store is not None and store.count() > 0:
            search_context = store.get_summary_for_context(max_chars=3000)
            if search_context:
                base_desc = base_desc + "\n\n" + search_context

        input_fields = {inp: dspy.InputField(desc=f"Input from {inp}") for inp in self.node.inputs}

        # Add user_response to signature if this is an HITL node
        if self.node.question:
            input_fields["user_response"] = dspy.InputField(desc="User's response to the question")

        output_fields = {self.node.output: dspy.OutputField(desc=f"Result for: {self.node.output}")}

        namespace = {
            "__doc__": base_desc,
            **input_fields,
            **output_fields,
        }
        return type(f"{self.node.name.replace(' ', '_')}Sig", (dspy.Signature,), namespace)

    def _build_module(self, additional_tools: list[dspy.Tool] | None = None) -> dspy.Module | None:
        """Select and instantiate the right DSPy module for this node's role."""
        sig = self._build_signature()
        role = self.node.role.value

        # Root nodes without dependencies get ReAct so they can use tools
        if self._is_root_node() and role in (NodeRole.CHAIN_OF_THOUGHT, NodeRole.PREDICT):
            role = NodeRole.REACT

        all_tools = list(self._tools or [])
        if additional_tools:
            all_tools.extend(additional_tools)

        if role == NodeRole.REACT:
            return dspy.ReAct(sig, tools=all_tools, max_iters=5)

        if role == NodeRole.RECURSIVE:
            return self._build_rlm_module(sig, all_tools)

        # Standardize: Map chain_of_thought to Predict + reasoning for better JSONAdapter compliance
        if role == NodeRole.CHAIN_OF_THOUGHT:
            return dspy.Predict(sig)

        if role == NodeRole.HUMAN_IN_LOOP:
            return None  # Pure approval gate — skip LLM entirely
        return dspy.Predict(sig)

    def _build_rlm_module(self, sig: type[dspy.Signature], tools: list[dspy.Tool]) -> dspy.RLM:
        """Build an RLM module for recursive large-context exploration."""
        if self.settings.rlm_require_deno and not check_deno_installed():
            raise RuntimeError(
                "Deno is required for RLM nodes but is not installed. "
                "Install with: curl -fsSL https://deno.land/install.sh | sh"
            )

        sub_lm_kwargs = get_rlm_sub_lm_kwargs(self.settings)
        sub_lm = dspy.LM(**sub_lm_kwargs)

        return dspy.RLM(
            signature=sig,
            tools=tools,
            sub_lm=sub_lm,
            max_iterations=20,
            max_llm_calls=50,
            verbose=False,
        )

    async def execute(self, **kwargs: Any) -> dspy.Prediction:
        """Run this node asynchronously with proactive context management."""
        from rich.console import Console

        console = Console()

        # Resolve tools asynchronously on first execution
        if self._tools is None:
            self._tools = await self._tool_resolver.resolve(self._tool_names, self._mcp_servers)

        # 1. Resolve model limits (OpenRouter/Ollama aware)
        limits = get_model_limits(self.settings.llm_model, self.settings)

        # 2. Setup semantic summarizer (uses primary model)
        lm_kwargs = self.settings.dspy_lm_kwargs.copy()
        lm_kwargs["max_tokens"] = min(limits.stability_floor, limits.max_output)
        sum_lm = dspy.LM(**lm_kwargs)

        from dspy import InputField, OutputField, Predict, Signature

        class SummarizerSig(Signature):
            """Summarize intermediate research steps/data concisely."""

            text = InputField()
            summary = OutputField()

        summarizer = Predict(SummarizerSig)

        def summarizer_fn(text: str) -> str:
            with dspy.settings.context(lm=sum_lm):
                return summarizer(text=text).summary

        # 3. Proactive Compression (Trajectory + Payload)
        input_content = self.node.description + str(kwargs) + self.goal
        for skill_name in self.node.skills:
            input_content += skills.get(skill_name) or ""

        current_input_tokens = count_tokens(input_content, self.settings.llm_model)

        if current_input_tokens > (limits.context_window * 0.6):
            console.print(
                f"  [dim yellow]⚠ Input massive ({current_input_tokens} tokens): compressing semantically[/dim yellow]"
            )
            kwargs = compress_payload(kwargs, self.settings.llm_model, (limits.context_window // 3), summarizer_fn)

        # 4. Calculate dynamic output cap
        dspy_overhead = 1000
        react_overhead = 1500 if self.node.role.value == "react" else 0
        total_overhead = dspy_overhead + react_overhead

        actual_input_tokens = count_tokens(self.node.description + str(kwargs) + self.goal, self.settings.llm_model)
        remaining_context = limits.context_window - actual_input_tokens - total_overhead

        node_requested_max = self.node.max_tokens or self.settings.llm_max_tokens
        verbose_keywords = ["summary", "deep dive", "report", "comprehensive", "analysis"]
        node_context = (self.node.name + " " + self.node.description).lower()

        # Boost for verbose nodes - prefer 8K when there's room
        if any(kw in node_context for kw in verbose_keywords) and remaining_context > 50000:
            node_requested_max = max(node_requested_max, 8192)

        # When context is large, allow more output; respect stability floor as minimum
        actual_max = min(node_requested_max, limits.max_output, remaining_context)

        # For large context windows, relax output limits
        if limits.context_window > 100000 and remaining_context > 50000:
            actual_max = max(node_requested_max, actual_max)

        actual_max = max(actual_max, limits.stability_floor)

        # 5. Configure LM with safe boundaries
        final_lm_kwargs = self.settings.dspy_lm_kwargs.copy()
        final_lm_kwargs["max_tokens"] = actual_max
        lm = dspy.LM(**final_lm_kwargs)

        if not self.module:
            self.module = self._build_module()

        if self.module is None and getattr(self.node, "question", None):
            return dspy.Prediction(answer="")

        # 6. Execution Loop
        timeout = self.node.timeout or self.settings.node_timeout or 300
        wrapped = dspy.asyncify(lambda **kw: self.module(**kw))

        # Only warn when truly tight context (not just default model limits)
        if actual_max < node_requested_max and actual_max < 2048:
            console.print(
                f"  [dim yellow]⚠ Context tight: capped output to {actual_max} tokens "
                f"(limit={limits.context_window}, input={actual_input_tokens})[/dim yellow]"
            )

        # Get adapter based on detected model capabilities (native function calling when supported)
        adapter = self._get_adapter()
        is_react = self.node.role.value == "react"
        pred = None
        last_error = None
        max_retries = 3
        current_timeout = timeout
        for attempt in range(max_retries):
            try:
                with dspy.settings.context(
                    lm=lm, adapter=adapter if is_react else None, allow_tool_async_sync_conversion=True
                ):
                    role_icon = "⚙" if is_react else "📝"
                    if attempt > 0:
                        console.print(
                            f"  [dim yellow]↻ Retry {attempt + 1}/{max_retries} (timeout={current_timeout}s)[/dim yellow]"
                        )
                    console.print(
                        f"  [cyan]{role_icon} Executing node:[/cyan] [bold]{self.node.name}[/bold] "
                        f"([dim]{self.node.role.value}[/dim])"
                    )
                    pred = await asyncio.wait_for(wrapped(**kwargs), timeout=current_timeout)
                    console.print(f"  [green]✓ Completed node:[/green] [bold]{self.node.name}[/bold]")
                    break
            except (AdapterParseError, ValueError) as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    console.print(f"  [dim yellow]⚠ Parse error, retrying: {last_error[:100]}[/dim yellow]")
                    continue
                raise
            except TimeoutError:
                last_error = f"timeout after {current_timeout}s"
                if attempt < max_retries - 1:
                    # Double timeout on each retry
                    current_timeout = min(current_timeout * 2, 600)
                    console.print(f"  [dim yellow]⚠ Timeout, retrying with {current_timeout}s timeout[/dim yellow]")
                    continue
                console.print(f"  [red]✖ Timeout:[/red] Node [bold]{self.node.name}[/bold] exceeded all timeouts")
                raise TimeoutError(f"Node {self.node.id} execution timed out after {max_retries} attempts") from None

        if pred is None:
            raise RuntimeError(f"Node {self.node.id} failed all {max_retries} attempts: {last_error}")

        # 7. Final Result Mapping
        out_key = self.node.output
        if out_key not in pred:
            found_fields = [v for k, v in pred.items() if str(v).strip()]
            if found_fields:
                pred[out_key] = found_fields[0]
            else:
                pred[out_key] = str(pred)

        if out_key in pred:
            val = str(pred[out_key])
            for p in ["Answer:", "Final Answer:", "Output:"]:
                if val.strip().startswith(p):
                    pred[out_key] = val.strip()[len(p) :].strip()

        return pred
