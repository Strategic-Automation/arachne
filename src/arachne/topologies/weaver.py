"""The Loom -- DSPy module that weaves natural language into a GraphTopology."""

from __future__ import annotations

import logging

import dspy
from dspy.adapters.json_adapter import AdapterParseError

from arachne.config import Settings
from arachne.skills import registry as skill_registry
from arachne.tools import list_tools
from arachne.topologies.schema import GoalDefinition, GraphTopology, NodeRole

logger = logging.getLogger(__name__)


def _sanitize(value: str | None, max_length: int = 5000) -> str:
    """Sanitize input: strip whitespace, remove control chars, truncate."""
    if value is None:
        return ""
    return value.strip().replace("\x00", "")[:max_length]


class CategorySelectorSignature(dspy.Signature):
    """Pick 2-4 most relevant skill categories for the goal."""

    goal: str = dspy.InputField()
    available_categories: str = dspy.InputField(desc="Comma-separated list of expert domains.")
    selected_categories: list[str] = dspy.OutputField(desc="e.g. ['research', 'devops']")


class GoalClarifierSignature(dspy.Signature):
    """Analyze the user's goal for ambiguity or missing details.

    A goal is COMPLETE if it specifies:
    - WHAT: The core entity or task (e.g. 'ArgoDevOps company').
    - DEPTH: How much detail is needed (e.g. 'find directors and bios').
    - SCOPE: Where to look (e.g. 'check social media and deep web').

    A goal is UNDERSPECIFIED if it is:
    - Vague: 'Research something', 'Find info', 'Write a script'.
    - Missing Identifiers: 'Research a company' without a name.
    """

    goal: str = dspy.InputField()
    is_complete: bool = dspy.OutputField()
    clarifying_questions: list[str] = dspy.OutputField(desc="1-3 targeted questions to ask the user.")
    reasoning: str = dspy.OutputField(desc="Brief explanation of the goal status.")


class GraphWeaverSignature(dspy.Signature):
    """Design a multi-agent execution graph (DAG) for the provided goal.

    CRITICAL I/O RULES:
    - Each node's 'inputs' field must ONLY reference field names from upstream nodes' 'output' fields.
    - Root nodes (nodes with no incoming edges) can only have inputs: ["goal"].
    - Downstream nodes' inputs must match exact upstream output field names - NO made-up field names.
    - Example valid chain: node_a.output="result" → node_b.inputs=["result"]
    - Example INVALID: node_b.inputs=["something_not_produced"]

    FILE WRITING RULE:
    - When saving content to a file, use the 'write_file' tool (NOT shell_exec with echo/redirect).
    - The node output field should contain the actual content (or a summary), NOT just the filename.
    - Example: node.output="haiku" (the actual haiku text), then save to file separately.
    - Do NOT output just filenames as node results - users want to SEE the content in the UI.

    SKILL ASSIGNMENT RULE:
    - For EVERY node, you MUST select 1-3 relevant skills from the provided 'skill_catalog'.
    - Use the full hierarchical names (e.g., 'research/search-specialist').
    - Skills provide the expert protocols necessary for high-quality execution.

    RECOVERY RULE:
    - If 'previous_topology' is provided, EVOLVE it rather than replacing it from scratch.
    - Preserve successful nodes and only add, modify, or remove nodes to address the failures described in 'failure_context'.

    INTAKE & CLARIFICATION RULE:
    - If the goal is underspecified or vague (e.g. 'research a company' without a name), DO NOT guess.
    - Instead, design a 1-node graph with role='human_in_loop'.
    - Use the 'request_context' tool or a specific 'question' to ask for the missing details.
    - Example: If goal is 'Research directors', ask 'Which company should I research directors for?'.

    TRIANGULATION SEARCH RULE (RANKED):
    - For high-stakes research, design graphs that use MULTIPLE specialized tools in parallel.
    - RANKING (Top to Bottom):
        1. Reliable Discovery: Use 'duckduckgo_search_async' (Always use first, very reliable and FREE).
        2. High-Fidelity Content: Use 'jina_search_async' for full markdown page content (Best for content).
        3. Global/Regional Discovery: Use 'deep_research_async' for regions/sites without APIs (e.g. Baidu, local portals).
        4. Factual/Entity Definitions: Use 'wikipedia_search_async'.
        5. Technical/Academic: Use 'arxiv_search_async'.
        6. API-Based Discovery: Use 'google_search_async' ONLY if 'SERPAPI_API_KEY' is configured (Fallback only).
    - HEADLESS CAUTION: Standard 'google_search_async' (headless) often fails due to blocks. Prefer 'duckduckgo_search_async' or 'deep_research_async' for autonomous browsing.
    - Complex Navigation: Use 'deep_research_async' for autonomous multi-step browsing or when regional-specific search engines (Baidu/Naver/etc) are required.
    - Synthesis: Always feed parallel search results into an 'Aggregator' node to reconcile findings.

    USER APPROVAL RULE:
    - For human_in_loop nodes, the question.query MUST include the content being reviewed.
    - Include the actual content in the question text so users can make informed decisions.
    - Example: question.query="Review this report:\\n{upstream_output}\\n\\nDo you approve?"
    - NEVER ask yes/no without showing the content first.

    TOOL AVAILABILITY RULE:
    - ONLY use tools that appear in the 'available_tools' list.
    - If a tool mentioned in the 'TRIANGULATION SEARCH RULE' ranking is NOT in 'available_tools', skip it and use the next best available tool.
    - Do NOT invent tool names or assume tools are available if they are not listed.

    CUSTOM ASSET RULE:
    - Only add entries to custom_tools if the tool name does NOT appear in available_tools.
    - Only add entries to custom_skills if the skill name does NOT appear in skill_catalog.
    - If a tool or skill already exists, reference it in the node's tools/skills list — do NOT recreate it.
    """

    goal: str = dspy.InputField()
    available_tools: str = dspy.InputField(
        desc="Built-in tools for 'react' nodes. Includes write_file for saving files."
    )
    skill_catalog: str = dspy.InputField(desc="Expert protocols index.")
    constraints_text: str = dspy.InputField(desc="Constraints from goal definition.")
    success_criteria: str = dspy.InputField(desc="Success criteria to optimize for.")
    available_roles: str = dspy.InputField()
    max_nodes: int = dspy.InputField()
    modifications: str = dspy.InputField(desc="User requested changes.")
    previous_topology: str = dspy.InputField(desc="JSON of the previous graph to evolve.", default="")
    failure_context: str = dspy.InputField(desc="Diagnosis of why the previous attempt failed.", default="")
    topology: GraphTopology = dspy.OutputField(
        desc=(
            "JSON with 'topology' field: name (str), objective (str), edges (list), "
            "nodes (list of objects with: id, name, description, role, inputs, output, skills, tools), "
            "runtime_inputs (list), custom_tools (list), custom_skills (list). "
            "Each node in 'nodes' MUST have relevant 'skills' assigned from the catalog."
        )
    )


class GraphWeaver(dspy.Module):
    def __init__(self, settings: Settings | None = None, max_nodes: int = 15) -> None:
        super().__init__()
        self.settings = settings or Settings()
        self.max_nodes = max_nodes
        self._available_roles = ", ".join(r.value for r in NodeRole)

        self.selector = dspy.Predict(CategorySelectorSignature)
        self.clarifier = dspy.Predict(GoalClarifierSignature)
        self.weave = dspy.Predict(GraphWeaverSignature)

        # Initialize tools and skills eagerly (required for test compatibility)
        self._available_tools: list[str] = []
        self._skill_catalog: dict[str, str] = {}
        self._ensure_initialized()

        # Auto-load pre-compiled few-shot demos if available (produced by `arachne compile-weaver`)
        self.compiled_demo_counts: dict[str, int] = {}
        self._try_load_fewshot_demos()

    def _try_load_fewshot_demos(self) -> None:
        """Auto-load compiled demos from disk using DSPy's native load().

        Demos are produced by ``arachne compile-weaver``. All three sub-predictors
        (weave, selector, clarifier) are loaded. Silent no-op if files don't exist
        (graceful degradation).
        """
        from arachne.optimizers.weaver_compiler import load_all_compiled

        self.compiled_demo_counts = load_all_compiled(self)
        total = sum(self.compiled_demo_counts.values())
        if total > 0:
            logger.debug(
                "Auto-loaded compiled demos into GraphWeaver: %s",
                ", ".join(f"{k}={v}" for k, v in self.compiled_demo_counts.items()),
            )
        else:
            logger.debug("No compiled demos found (run `arachne compile-weaver` to generate)")

    def _ensure_initialized(self) -> None:
        """Lazy initialization of tools and skills."""
        if self._available_tools:
            return
        try:
            self._available_tools = list_tools(self.settings)
        except Exception as e:
            logger.error("Tool discovery failed: %s", e)
            raise RuntimeError(f"Tool discovery failed: {e}") from e

        self._skill_catalog = skill_registry.list_available(with_descriptions=True)

    def _select_categories(self, goal: str) -> list[str]:
        """Select relevant skill categories for the goal."""
        categories = sorted({s.split("/")[0] for s in self._skill_catalog if "/" in s})
        with dspy.settings.context(temperature=0.0):
            result = self.selector(goal=goal, available_categories=", ".join(categories))
        return getattr(result, "selected_categories", [])

    def _build_skill_catalog(self, target_cats: list[str]) -> str:
        """Build skill catalog text from selected categories."""
        if not target_cats:
            return "\n".join(f"- {n}: {d}" for n, d in list(self._skill_catalog.items())[:20])

        lines = []
        for name, desc in self._skill_catalog.items():
            if any(name.startswith(cat + "/") for cat in target_cats):
                lines.append(f"- {name}: {desc}")

        if not lines:
            lines = [f"- {n}: {d}" for n, d in list(self._skill_catalog.items())[:20]]

        return "\n".join(lines)

    def _format_goal_definition(self, goal_definition: GoalDefinition | None) -> tuple[str, str]:
        """Format constraints and success criteria from goal definition for LLM prompt."""
        if not goal_definition:
            return "", ""

        constraints = ""
        if goal_definition.constraints:
            constraints = "\n".join(
                f"- [{c.type.value}] {c.description}" + (" (HARD BOUNDARY)" if c.is_hard_boundary else "")
                for c in goal_definition.constraints
            )

        success = ""
        if goal_definition.success_criteria:
            success = "\n".join(goal_definition.success_criteria)

        return constraints, success

    def _weave_once(
        self,
        goal: str,
        skill_catalog: str,
        constraints: str,
        success: str,
        modifications: str,
        temperature: float,
        failure_context: str = "",
        previous_topology: str = "",
    ) -> GraphTopology:
        """Execute a single weave call."""
        with dspy.settings.context(temperature=temperature):
            pred = self.weave(
                goal=goal,
                available_tools=", ".join(self._available_tools),
                skill_catalog=skill_catalog,
                constraints_text=constraints,
                success_criteria=success,
                available_roles=self._available_roles,
                max_nodes=self.max_nodes,
                modifications=modifications,
                previous_topology=previous_topology,
                failure_context=failure_context,
            )

        topology = getattr(pred, "topology", None)
        if topology is None:
            raise ValueError("LLM returned None for topology.")

        topology.model_validate(topology.model_dump())
        return topology

    def _recover_with_retry(
        self,
        goal: str,
        constraints: str,
        success: str,
        modifications: str,
        error_context: str,
        previous_topology: str = "",
    ) -> GraphTopology:
        """Retry topology generation with recovery context."""
        recovery_catalog = "\n".join(f"- {n}: {d}" for n, d in list(self._skill_catalog.items())[:30])

        return self._weave_once(
            goal=goal,
            skill_catalog=recovery_catalog,
            constraints=constraints,
            success=success,
            modifications=modifications,
            temperature=max(self.settings.weave_temperature + 0.2, 0.5),
            failure_context=error_context,
            previous_topology=previous_topology,
        )

    def forward(
        self,
        goal: str,
        goal_definition: GoalDefinition | None = None,
        failure_context: str | None = None,
        modifications: str = "",
        previous_topology: str | GraphTopology | None = None,
        check_intake: bool = True,
    ) -> dspy.Prediction:
        self._ensure_initialized()

        # 1. Intake Clarification (Optional)
        if check_intake and not previous_topology and not failure_context:
            with dspy.settings.context(temperature=0.0):
                clarification = self.clarifier(goal=goal)

            if not clarification.is_complete:
                return dspy.Prediction(
                    topology=None,
                    is_complete=False,
                    questions=clarification.clarifying_questions,
                    reasoning=clarification.reasoning,
                )

        # Sanitize inputs
        failure_context = _sanitize(failure_context)
        modifications = _sanitize(modifications)

        constraints, success = self._format_goal_definition(goal_definition)

        # Initial category selection
        target_cats = self._select_categories(goal)
        skill_catalog = self._build_skill_catalog(target_cats)

        logger.debug("Weaving with %d skills from categories: %s", len(skill_catalog.split("\n")), target_cats)

        # Prepare previous topology context
        prev_topo_str = ""
        if previous_topology:
            if isinstance(previous_topology, GraphTopology):
                prev_topo_str = previous_topology.model_dump_json()
            else:
                prev_topo_str = str(previous_topology)

        # Truncate if massive (e.g. 10k+ chars) to prevent context blowouts
        if len(prev_topo_str) > 12000:
            prev_topo_str = prev_topo_str[:6000] + "\n... [TRUNCATED] ...\n" + prev_topo_str[-4000:]

        try:
            topology = self._weave_once(
                goal=goal,
                skill_catalog=skill_catalog,
                constraints=constraints,
                success=success,
                modifications=modifications,
                temperature=self.settings.weave_temperature,
                failure_context=failure_context,
                previous_topology=prev_topo_str,
            )
        except (ValueError, AdapterParseError) as e:
            error_msg = str(e)
            logger.warning("Weave failed: %s. Attempting recovery.", error_msg[:200])

            # Extract specific I/O mismatch details from error
            io_mismatch = ""
            if "requires input" in error_msg and "Available outputs:" in error_msg:
                # Parse: "Node 'X' requires input 'Y', but no upstream node produces it. Available outputs: [...]"
                import re

                match = re.search(r"Node '(\w+)' requires input '(\w+)'.+Available outputs: \[([^\]]+)\]", error_msg)
                if match:
                    node_name, bad_input, available = match.groups()
                    io_mismatch = (
                        f"FIX THIS: Node '{node_name}' has inputs=['{bad_input}'] but no node produces '{bad_input}'. "
                        f"Only these outputs exist: {available}. "
                        f"Change '{node_name}'.inputs to use one of those outputs, or remove that node."
                    )

            recovery_context = (
                "CRITICAL I/O RULE: Every node.inputs MUST match an upstream node's output field name. "
                "Root nodes: inputs=['goal']. Downstream nodes: inputs must equal upstream output field. "
                f"{io_mismatch}"
                "Example VALID chain: NodeA(output='data') -> NodeB(inputs=['data']). "
                "Example INVALID: NodeB(inputs=['wrong_field']). "
                "Do NOT invent field names. Output a valid topology."
            )

            # Recovery: parse/LLM failure (null response, empty, etc.)
            topology = self._recover_with_retry(
                goal=goal,
                constraints=constraints,
                success=success,
                modifications=modifications,
                error_context=recovery_context,
                previous_topology=prev_topo_str,
            )

        return dspy.Prediction(topology=topology, is_complete=True, questions=[], reasoning="Goal is complete.")
