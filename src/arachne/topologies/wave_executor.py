"""WaveExecutor -- wave-based parallel execution for graph nodes.

Manages the wave-by-wave execution loop: runs all nodes in a wave
concurrently, handles HITL prompts, propagates outputs downstream,
and marks downstream nodes as SKIPPED on failure.
"""

import asyncio
import time
from typing import Any

from rich.console import Console

from arachne.config import Settings
from arachne.topologies.schema import GraphTopology, NodeDef, NodeResult, ResultStatus, RunResult


class WaveExecutor:
    """Executes graph nodes in topological waves with parallel execution per wave."""

    def __init__(
        self,
        topology: GraphTopology,
        node_executors: dict[str, Any],
        settings: Settings,
        session: Any = None,
        initial_results: dict[str, Any] | None = None,
    ) -> None:
        self.topology = topology
        self.node_executors = node_executors
        self.settings = settings
        self.session = session
        self._results: dict[str, NodeResult] = dict(initial_results or {})
        self._executed_this_run: set[str] = set()
        self.console = Console()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute_waves(
        self,
        initial_inputs: dict[str, Any],
        knowledge_store: Any = None,
        ask_user_fn: Any = None,
    ) -> tuple[RunResult, dict[str, NodeResult]]:
        """Run all waves in topological order, returning the RunResult and per-node results."""
        from arachne.runtime.knowledge_store import KnowledgeStore

        if knowledge_store is None:
            knowledge_store = KnowledgeStore()

        start = time.monotonic()
        waves = self.topology.topological_waves()
        all_results: dict[str, Any] = dict(initial_inputs)
        console_lock = asyncio.Lock()

        # Inject previously-completed results for resumed sessions
        nodes_dict = self.topology.nodes_dict
        for nid, nr in self._results.items():
            if nr.status == ResultStatus.COMPLETED and nr.output:
                # Store by node ID
                node_output_dict = nr.output
                node_def = nodes_dict.get(nid)

                # Find the actual output value in the dict
                # NodeResult.output is {field_name: value}
                val = ""
                if node_def and node_def.output in node_output_dict:
                    val = node_output_dict[node_def.output]
                elif node_output_dict:
                    # Fallback to the first value if field name doesn't match
                    val = next(iter(node_output_dict.values()))

                all_results[nid] = val
                if node_def:
                    all_results[node_def.output] = val

        for wave_idx, wave in enumerate(waves):
            node_names = ", ".join(nid for nid in wave)
            self.console.print(
                f"\n  [bold blue]▶[/bold blue] [bold]Wave {wave_idx + 1}/{len(waves)}:[/bold] [dim]({node_names})[/dim]"
            )

            outcomes = await self._execute_wave(wave, all_results, knowledge_store, console_lock, ask_user_fn)

            failures = [err for _, err in outcomes if err is not None]
            done = sum(1 for _, e in outcomes if e is None)
            self.console.print(f"    [green]✓[/green] {done}/{len(wave)} nodes completed")

            if failures:
                self._skip_downstream(waves, wave_idx)
                break

        run_result = RunResult(
            graph_name=self.topology.name,
            goal=str(initial_inputs.get("goal", "")),
            node_results=list(self._results.values()),
            duration_seconds=time.monotonic() - start,
        )
        return run_result, self._results

    # ------------------------------------------------------------------
    # Wave-level execution
    # ------------------------------------------------------------------

    async def _execute_wave(
        self,
        wave: list[str],
        all_results: dict[str, Any],
        knowledge_store: Any,
        console_lock: asyncio.Lock,
        ask_user_fn: Any,
    ) -> list[tuple[str, Exception | None]]:
        """Execute a single wave of nodes in parallel."""

        async def run_one(node_id: str) -> tuple[str, Exception | None]:
            # Skip already completed nodes (resume path)
            if node_id in self._results and self._results[node_id].status == ResultStatus.COMPLETED:
                node_def = self.topology.nodes_dict.get(node_id)
                # If ANY upstream dependency was executed in this run, we must re-run this node
                # to prevent stale data propagation.
                if node_def:
                    # Check both explicit dependencies and data inputs (via upstream edges)
                    upstream_nodes = self.topology.upstream(node_id)
                    deps = set(node_def.depends_on) | set(upstream_nodes)
                    if not any(d in self._executed_this_run for d in deps):
                        return node_id, None

            node_exec = self.node_executors[node_id]
            node_def = node_exec.node
            inputs = self._get_node_inputs(node_id, all_results)
            ts = time.monotonic()

            try:
                is_hitl = getattr(node_def, "question", None) or node_def.role.value == "human_in_loop"
                if is_hitl:
                    result = await self._handle_human_input(
                        node_exec, node_def, inputs, knowledge_store, console_lock, ask_user_fn, all_results
                    )
                else:
                    result = await node_exec.execute(**inputs)

                self._store_result(node_id, node_def, result, all_results, knowledge_store, ts)
                self._executed_this_run.add(node_id)
                return node_id, None
            except Exception as exc:
                self._results[node_id] = NodeResult(
                    node_id=node_id,
                    status=ResultStatus.FAILED,
                    error=str(exc),
                    duration_seconds=time.monotonic() - ts,
                )
                return node_id, exc

        return await asyncio.gather(*(run_one(nid) for nid in wave))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_node_inputs(self, node_id: str, all_results: dict[str, Any]) -> dict[str, Any]:
        """Resolve inputs for a node from upstream results."""
        nodes_dict = self.topology.nodes_dict
        node_def = nodes_dict[node_id]
        inputs = {inp: str(all_results.get(inp, "")) for inp in node_def.inputs}
        # Always inject goal context for all nodes
        inputs["goal"] = str(all_results.get("goal", ""))
        return inputs

    def _store_result(
        self,
        node_id: str,
        node_def: NodeDef,
        result: Any,
        all_results: dict[str, Any],
        knowledge_store: Any,
        ts: float,
    ) -> None:
        """Extract output from a result, propagate it downstream, and record NodeResult."""
        all_results[node_id] = result

        output_value = result.get(node_def.output) or getattr(result, node_def.output, None)
        if output_value is not None:
            if hasattr(output_value, "formatted"):
                output_str = output_value.formatted or str(output_value)
            elif hasattr(output_value, "text"):
                output_str = output_value.text or str(output_value)
            else:
                output_str = str(output_value)
            # For HUMAN_IN_LOOP nodes, we keep the rich dict (feedback + original data)
            # in BOTH the output field and the node_id entry. This prevents the user's
            # feedback from shadowing the actual data being reviewed.
            from arachne.topologies.schema import NodeRole

            if node_def.role == NodeRole.HUMAN_IN_LOOP and len(result) > 1:
                all_results[node_def.output] = result
                all_results[node_id] = result
            else:
                all_results[node_def.output] = output_str
                all_results[node_id] = output_str
            knowledge_store.add(node_def.output, output_str, source="tool")
            knowledge_store.add(node_def.id, output_str, source="tool")

        self._results[node_id] = NodeResult(
            node_id=node_id,
            status=ResultStatus.COMPLETED,
            output={k: str(v) for k, v in result.items()},
            duration_seconds=time.monotonic() - ts,
        )

        # Persist FULL node output (including trace/thoughts) to session folder if session is active
        if self.session:
            self.session.save_node_output(node_id, self._results[node_id].output)
            self.session.append_log(node_id, f"Completed in {time.monotonic() - ts:.2f}s")

    def _skip_downstream(self, waves: list[list[str]], failed_wave_idx: int) -> None:
        """Mark all nodes in waves after the failure as SKIPPED."""
        for future_wave in waves[failed_wave_idx + 1 :]:
            for nid in future_wave:
                self._results[nid] = NodeResult(
                    node_id=nid,
                    status=ResultStatus.SKIPPED,
                    error="Upstream node failed",
                )
        if self.session:
            state = {"node_results": [r.model_dump(mode="json") for r in self._results.values()]}
            self.session.save_state(state)

    async def _handle_human_input(
        self,
        node_exec: Any,
        node_def: NodeDef,
        inputs: dict[str, Any],
        knowledge_store: Any,
        console_lock: asyncio.Lock,
        ask_user_fn: Any,
        all_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle a human-in-the-loop node: check pre-collected answers first."""
        response_key = node_def.output or "answer"
        pre_collected = all_results.get(response_key) or knowledge_store.get(response_key)

        # Pure gate optimization: skip if answer exists and node doesn't process data
        if pre_collected is not None and node_exec.module is None:
            async with console_lock:
                print("    ⏭ Skipped (answer pre-collected)")
            return {response_key: str(pre_collected)}

        if pre_collected is not None and not node_def.inputs:
            async with console_lock:
                print("    ⏭ Using pre-collected context")
            knowledge_store.add("user_response", str(pre_collected), source="user")
            inputs["user_response"] = str(pre_collected)
            return await node_exec.execute(**inputs)

        # Inject 'upstream_output' placeholder for query templating
        # This resolves Rule 50 in weaver.py where the LLM is told to use {upstream_output}
        if "upstream_output" not in inputs:
            primary_input = next((v for k, v in inputs.items() if k not in ("goal", "user_response")), None)
            if primary_input:
                inputs["upstream_output"] = primary_input

        async with console_lock:
            answer = await asyncio.to_thread(ask_user_fn, node_def, inputs)
        knowledge_store.add(response_key, answer, source="user")
        knowledge_store.add("user_response", answer, source="user")
        inputs["user_response"] = answer

        # For approval nodes, return BOTH the user's response AND the original content.
        # Downstream nodes need the actual content, not the approval response.
        result = {response_key: answer}

        # Include original upstream content so downstream nodes can use it
        for inp_key in node_def.inputs:
            if inp_key in inputs and inp_key not in ("goal", "user_response"):
                result[inp_key] = inputs[inp_key]

        # Pure gate optimization: if node has no upstream dependencies or LLM module,
        # return the answer directly without an LLM call.
        if node_exec.module is None or not node_def.inputs:
            return result

        exec_result = await node_exec.execute(**inputs)
        # Merge execution result with original content
        if isinstance(exec_result, dict):
            result.update(exec_result)
        return result
