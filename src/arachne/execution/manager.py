"""Execution manager for Arachne graph execution with self-healing."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import dspy

from arachne.config import Settings
from arachne.runtime.auto_healer import AutoHealer, FailedNodeInfo, HealAttempt
from arachne.runtime.evaluator import TriangulatedEvaluator
from arachne.runtime.provision import provision_graph
from arachne.sessions.manager import Session
from arachne.topologies.node_executor import NodeExecutor
from arachne.topologies.schema import GoalDefinition, GraphTopology, ResultStatus
from arachne.topologies.wave_executor import WaveExecutor
from arachne.topologies.weaver import GraphWeaver

logger = logging.getLogger(__name__)


def _run_async_safe(coro: Any) -> Any:
    """Run an async coroutine safely, whether or not an event loop is already running.

    This allows ExecutionManager to work inside FastAPI, Jupyter, pytest-asyncio,
    and other async environments — not just from plain synchronous entry points.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing event loop (FastAPI, Jupyter, etc.)
        # Schedule the coroutine on a separate thread with its own loop.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


class ExecutionManager:
    """Manages graph execution with self-healing loop and circuit breaker."""

    def __init__(
        self,
        settings: Settings,
        weaver: GraphWeaver,
        evaluator: TriangulatedEvaluator,
        goal_definition: GoalDefinition | None = None,
        max_retries: int = 3,
        confidence_threshold: float = 0.8,
        on_topology_update: Callable[[GraphTopology], None] | None = None,
        ask_user_fn: Callable[[Any, dict[str, Any]], str] | None = None,
        modifications: str = "",
        interactive: bool = False,
    ):
        self.settings = settings
        self.weaver = weaver
        self.evaluator = evaluator
        self.goal_definition = goal_definition
        self.max_retries = max_retries
        self.confidence_threshold = confidence_threshold
        self.on_topology_update = on_topology_update
        self.ask_user_fn = ask_user_fn or self._default_ask_user
        self.modifications = modifications
        self.interactive = interactive
        self._history: list[dict] = []

        # Initialize lightweight components
        self.auto_healer = AutoHealer()

    def execute(
        self,
        goal: str,
        topology: GraphTopology,
        session: Session | None = None,
        initial_results: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dspy.Prediction:
        """Execute the graph with self-healing loop and circuit breaker."""
        prev_results = initial_results or {}
        attempt_history: list[HealAttempt] = []
        diagnosis_counter: dict[str, int] = {}
        max_node_retries: int = 3
        max_global_heals: int = 10
        heal_count = 0

        while True:
            # Validate topology is a DAG before running — catch cycle errors early
            try:
                topology.topological_waves()  # raises ValueError if cyclic
            except ValueError as exc:
                if "cycle" in str(exc).lower() or "Topology contains" in str(exc):
                    heal_count += 1
                    if heal_count > max_global_heals:
                        raise RuntimeError(
                            f"Failed to weave a valid acyclic graph after {max_global_heals} attempts."
                        ) from exc
                    self._log_status(f"Heal #{heal_count}: Cyclic topology detected — re-weaving.", "warning", session)
                    topology = self._reweave(
                        goal=goal,
                        session=session,
                        previous_topology=topology,
                        failure_context=(
                            f"Previous graph was INVALID: {exc}\n\n"
                            "RULES: Arachne only supports DAGs (Directed Acyclic Graphs). "
                            "Do NOT create back-edges or loops. If the goal requires iteration "
                            "(e.g. fix → test → fix again), model it as a single linear chain: "
                            "analyze → fix → validate → output. The 'loop' happens implicitly "
                            "via the Arachne self-healing re-weave cycle if validation fails."
                        ),
                    )
                    continue
                raise

            # Initialize NodeExecutors for the current topology
            node_executors = {
                node.id: NodeExecutor(node=node, settings=self.settings, goal=goal) for node in topology.nodes
            }

            executor = WaveExecutor(
                topology=topology,
                node_executors=node_executors,
                settings=self.settings,
                session=session,
                initial_results=prev_results,
            )

            run_result, _node_results = _run_async_safe(
                executor.execute_waves(
                    initial_inputs={"goal": goal},
                    ask_user_fn=self.ask_user_fn,
                )
            )

            # Wrap in dspy.Prediction for compatibility with downstream eval
            result = dspy.Prediction(run_result=run_result)
            result.topology = topology

            # 1. Success Path: All nodes completed/skipped
            failed = [
                nr
                for nr in result.run_result.node_results
                if nr.status.value not in (ResultStatus.COMPLETED, ResultStatus.SKIPPED)
            ]

            if not failed:
                # Evaluate output quality
                eval_pred = self.evaluator(
                    goal=goal,
                    run_result=result.run_result,
                    goal_definition=self.goal_definition,
                    topology=topology,
                    attempt=heal_count + 1,
                )
                report = eval_pred.report

                # Propagate evaluation results to RunResult so the display layer
                # can show the actual evaluation verdict (not stale defaults).
                result.run_result.evaluation_source = report.evaluation_source
                result.run_result.confidence_score = report.confidence_score
                result.run_result.requires_human = report.requires_human

                if report.confidence_score >= self.confidence_threshold:
                    if self.interactive and self.ask_user_fn:
                        from arachne.cli.display import display_outputs
                        from arachne.topologies.schema import NodeDef, NodeRole, Question, QuestionType

                        # Display the generated outputs to the user before asking for approval
                        display_outputs(result.run_result, topology)

                        final_gate = NodeDef(
                            id="final_approval",
                            name="Final Review",
                            role=NodeRole.HUMAN_IN_LOOP,
                            question=Question(
                                query=f"Execution complete with confidence {report.confidence_score:.2f}. Are you happy with the result?",
                                type=QuestionType.SELECT,
                                choices=["Yes, finish", "No, I have feedback", "Cancel"],
                            ),
                        )

                        ans = self.ask_user_fn(final_gate, {})
                        if ans == "Cancel":
                            raise ValueError("Run cancelled during final approval.")
                        if ans == "No, I have feedback":
                            # Trigger a manual heal
                            heal_count += 1
                            report.confidence_score = 0.5
                            report.diagnosis = "User requested changes after final review."
                            topology, prev_results = self._handle_low_quality(
                                goal, topology, result, report, heal_count, max_global_heals, session
                            )
                            continue

                    if session:
                        session.save_state(result.run_result.model_dump(mode="json"))
                    result.run_result.attempts = heal_count + 1
                    result.run_result.success = True
                    return result

                # Low quality: Re-weave to improve
                heal_count += 1

                # Loop Protection: If we see the same diagnosis too many times, something is wrong
                diag_key = f"{report.evaluation_source}:{report.diagnosis}"
                diagnosis_counter[diag_key] = diagnosis_counter.get(diag_key, 0) + 1

                if diagnosis_counter[diag_key] >= 3:
                    self._log_status(
                        f"Circuit Breaker: Diagnosis repeated {diagnosis_counter[diag_key]} times. Stopping.",
                        "error",
                        session,
                    )
                    return self._finalize_result(result, session, heal_count, success=False)

                if heal_count > max_global_heals:
                    return self._finalize_result(result, session, heal_count, success=False)

                topology, prev_results = self._handle_low_quality(
                    goal, topology, result, report, heal_count, max_global_heals, session
                )
                continue

            # 2. Failure Path: Node failures detected
            if heal_count >= max_global_heals:
                return self._finalize_result(result, session, heal_count + 1, success=False)

            # Circuit Breaker: Per-node retry limit
            if self._check_circuit_breaker(failed, attempt_history, max_node_retries, session):
                return self._finalize_result(result, session, heal_count + 1, success=False)

            # 3. Healing Logic
            # Classification: separate transient infrastructure failures (timeout,
            # rate-limit, connection) from structural / logic errors. Transient
            # errors should NEVER trigger a re-weave of the graph — they need
            # retry or re-route only.
            from arachne.runtime.auto_healer import is_transient_error

            node_retry_counts: dict[str, int] = {}
            node_strategy_history: dict[str, set[str]] = {}
            for attempt in attempt_history:
                for nid in attempt.failed_nodes:
                    node_retry_counts[nid] = node_retry_counts.get(nid, 0) + 1
                    node_strategy_history.setdefault(nid, set()).add(attempt.strategy)

            # Classify whether all failures are transient
            all_transient = all(is_transient_error(nr.error or "") for nr in failed)

            if all_transient:
                # Transient errors: escalate through retry → re-route → human
                # NEVER re-weave for transient errors.
                needs_llm_diagnosis = False
                max_retries_per_node = 2  # try up to 2 retries before re-routing

                # Check if any failed node has exhausted retries
                any_exhausted_retries = any(
                    node_retry_counts.get(nr.node_id, 0) >= max_retries_per_node for nr in failed
                )
                # Check if re-route was already tried for these nodes
                any_rerouted = any("re-route" in node_strategy_history.get(nr.node_id, set()) for nr in failed)

                if any_rerouted:
                    # Already tried retry + re-route — escalate to human
                    diagnosis = dspy.Prediction(
                        fix_strategy="retry",
                        fix_description=(
                            "Persistent transient errors (timeouts/rate-limits) after retry and re-route. "
                            "The graph design is correct but the execution environment has issues. "
                            "Recommend checking network connectivity, API keys, and rate-limit quotas."
                        ),
                        requires_human=True,
                        confidence_score=0.3,
                    )
                elif any_exhausted_retries:
                    # Retries exhausted — try re-route (swap tools/approach)
                    diagnosis = dspy.Prediction(
                        fix_strategy="re-route",
                        fix_description=(
                            "Transient errors persist after retries. Attempting alternative "
                            "tools or approach adjustments."
                        ),
                        requires_human=False,
                        confidence_score=0.6,
                    )
                else:
                    # First failure(s) — simple retry
                    diagnosis = dspy.Prediction(
                        fix_strategy="retry",
                        fix_description="Transient error detected; retrying before considering alternatives.",
                        requires_human=False,
                        confidence_score=1.0,
                    )
            else:
                # Non-transient errors: use programmatic fast-path for first failure,
                # then delegate to the LLM healer for structural diagnosis.
                needs_llm_diagnosis = False
                for nr in failed:
                    if node_retry_counts.get(nr.node_id, 0) == 0:
                        error_str = (nr.error or "").lower()
                        if any(msg in error_str for msg in ["missing input", "keyerror", "not found"]):
                            needs_llm_diagnosis = True
                            break
                    else:
                        needs_llm_diagnosis = True
                        break

                if not needs_llm_diagnosis:
                    diagnosis = dspy.Prediction(
                        fix_strategy="retry",
                        fix_description="First failure detected; attempting transient retry before redesign.",
                        requires_human=False,
                        confidence_score=1.0,
                    )
                else:
                    diagnosis = self._diagnose_failure(goal, topology, result, failed, attempt_history)

            heal_count += 1

            if diagnosis.requires_human:
                self._log_status(f"Heal #{heal_count}: requires human -- {diagnosis.fix_description}", "error", session)
                return self._finalize_result(result, session, heal_count, success=False)

            # Apply healing strategy
            attempt_history.append(
                HealAttempt(
                    attempt=heal_count,
                    strategy=str(diagnosis.fix_strategy),
                    fix_description=diagnosis.fix_description,
                    outcome="",
                    confidence=diagnosis.confidence_score,
                    failed_nodes=[nr.node_id for nr in failed],
                )
            )

            topology, prev_results = self._apply_heal_strategy(
                goal, topology, result, failed, diagnosis, heal_count, max_global_heals, attempt_history, session
            )

            if not topology:  # Strategy failed to apply
                return self._finalize_result(result, session, heal_count, success=False)

    def _handle_low_quality(self, goal, topology, result, report, heal_count, max_global_heals, session):
        self._log_status(
            f"Heal #{heal_count}: Low quality (Confidence {report.confidence_score:.2f})", "warning", session
        )
        if report.diagnosis:
            logger.debug("Low quality reason: %s", report.diagnosis)

        details = report.evaluation_details if hasattr(report, "evaluation_details") else {}
        issues = details.get("issues", [])
        imps = details.get("improvements", [])
        trace = details.get("trace", "No trace available.")

        improvements_text = ""
        if issues:
            improvements_text += "Issues: " + "; ".join(issues) + ".\n"
        if imps:
            improvements_text += "Improvements: " + "; ".join(imps) + ".\n"
        if report.diagnosis:
            improvements_text += f"\nDiagnosis: {report.diagnosis}"

        # Truncate trace if it's massive to fit context
        truncated_trace = trace if len(trace) < 4000 else trace[:2000] + "\n... [TRUNCATED] ...\n" + trace[-2000:]

        failure_context = (
            f"Previous output quality too low (score: {report.confidence_score:.2f}).\n"
            f"{improvements_text}\n"
            f"--- Execution Trace ---\n{truncated_trace}"
        )

        if self.interactive and self.ask_user_fn:
            from arachne.topologies.schema import NodeDef, NodeRole, Question, QuestionType

            # Create a virtual node for feedback collection
            feedback_node = NodeDef(
                id="quality_feedback",
                name="Review Evaluation",
                role=NodeRole.HUMAN_IN_LOOP,
                question=Question(
                    query=(
                        f"I detected low quality in the result (Score: {report.confidence_score:.2f}).\n"
                        f"Issues: {'; '.join(issues) if issues else 'Unspecified data quality issues'}\n\n"
                        "How should I proceed?"
                    ),
                    type=QuestionType.SELECT,
                    choices=["Auto-fix (Re-weave)", "Adjust Goal / Provide Feedback", "Cancel Run"],
                ),
            )

            choice = self.ask_user_fn(feedback_node, {})

            if choice == "Cancel Run":
                raise ValueError("Run cancelled by user after low quality evaluation.")

            if choice == "Adjust Goal / Provide Feedback":
                user_feedback = self.ask_user_fn(
                    NodeDef(
                        id="user_guidance",
                        name="Manual Guidance",
                        role=NodeRole.HUMAN_IN_LOOP,
                        question=Question(
                            query="What specific changes or details should I focus on for the next attempt?"
                        ),
                    ),
                    {},
                )
                if user_feedback:
                    failure_context = f"{failure_context}\n\nUSER FEEDBACK: {user_feedback}"

        self._log_status(f"↺ Re-weaving graph... (Confidence: {report.confidence_score:.2f})", "info", session)
        if issues:
            logger.debug("Re-weave reason: %s", "; ".join(issues))

        new_topology = self._reweave(
            goal=goal, failure_context=failure_context, session=session, previous_topology=topology
        )
        # Preserve completed results even on re-weave to allow the new topology
        # to resume nodes that it didn't change (matching IDs).
        completed = {nr.node_id: nr for nr in result.run_result.node_results if nr.status == ResultStatus.COMPLETED}
        return new_topology, completed

    def _diagnose_failure(self, goal, topology, result, failed, attempt_history):
        failed_nodes_info = []
        for nr in failed:
            node_def = topology.nodes_dict.get(nr.node_id)
            failed_nodes_info.append(
                FailedNodeInfo(
                    node_id=nr.node_id,
                    role=node_def.role.value if node_def else "predict",
                    error=nr.error or "Unknown error",
                    duration_seconds=nr.duration_seconds,
                    tools_used=[t.name for t in node_def.tools] if node_def else [],
                    mcp_servers=node_def.mcp_servers if node_def else [],
                )
            )

        partial_results = {
            nr.node_id: str(nr.output) for nr in result.run_result.node_results if nr.status == ResultStatus.COMPLETED
        }

        topology_desc = f"Graph '{topology.name}': {len(topology.nodes)} nodes. flow: " + ", ".join(
            n.id + "(" + n.role.value + ")" for n in topology.nodes
        )

        return self.auto_healer(
            goal=goal,
            failed_nodes_list=failed_nodes_info,
            partial_results=partial_results,
            topology_description=topology_desc,
            attempt_history=attempt_history,
        )

    def _apply_heal_strategy(
        self, goal, topology, result, failed, diagnosis, heal_count, max_global_heals, attempt_history, session
    ):
        strategy = str(diagnosis.fix_strategy).lower()
        completed = {nr.node_id: nr for nr in result.run_result.node_results if nr.status == ResultStatus.COMPLETED}

        if strategy == "retry":
            logger.debug("↻ Auto-healing (retry): %s", diagnosis.fix_description)
            return topology, completed

        elif strategy == "re-route":
            logger.debug("↻ Auto-healing (re-route): %s", diagnosis.fix_description)
            for nr in failed:
                node_def = topology.nodes_dict.get(nr.node_id)
                if node_def:
                    self._log_status(f"↺ Re-routing node '{node_def.id}': rewriting instructions", "info", session)
                    new_desc = self.auto_healer.rewrite_node_description(
                        original_description=node_def.description, fix_description=diagnosis.fix_description
                    )
                    node_def.description = new_desc
            if self.on_topology_update:
                self.on_topology_update(topology)
            return topology, completed

        elif strategy == "re-weave":
            logger.debug("↻ Auto-healing (re-weave): %s", diagnosis.fix_description)
            context = f"Attempt {heal_count} failed. Diagnosis: {diagnosis.fix_description}. Failed: {[n.node_id for n in failed]}"
            if attempt_history:
                attempt_history[-1].outcome = f"Re-weave: {diagnosis.fix_description}"

            new_topology = self._reweave(
                goal=goal, failure_context=context, session=session, previous_topology=topology
            )
            return new_topology, completed

        return None, {}

    def _check_circuit_breaker(self, failed, attempt_history, max_node_retries, session) -> bool:
        node_retry_counts = {}
        for attempt in attempt_history:
            for nid in attempt.failed_nodes:
                node_retry_counts[nid] = node_retry_counts.get(nid, 0) + 1

        for nr in failed:
            if node_retry_counts.get(nr.node_id, 0) >= max_node_retries:
                if session:
                    session.append_log(nr.node_id, f"Circuit breaker: node retried {max_node_retries}x")
                return True
        return False

    def _finalize_result(self, result, session, attempts, success):
        result.run_result.success = success
        result.run_result.attempts = attempts
        if session:
            session.save_state(result.run_result.model_dump(mode="json"))
        return result

    def _reweave(
        self,
        goal: str,
        failure_context: str,
        session: Session | None = None,
        previous_topology: GraphTopology | None = None,
    ) -> GraphTopology:
        """Re-weave the topology with a failure context and re-provision."""
        new_topology = self.weaver(
            goal=goal,
            failure_context=failure_context,
            modifications=self.modifications,
            goal_definition=self.goal_definition,
            previous_topology=previous_topology,
        ).topology
        new_topology = provision_graph(new_topology, self.settings, goal)
        if session:
            session.save_graph(new_topology.model_dump(mode="json"))

        logger.info("Updated Graph (Healed): %s (%d nodes)", new_topology.name, len(new_topology.nodes))

        from arachne.cli.display import display_topology

        display_topology(new_topology, title=f"[bold]Healed Graph: {new_topology.name}[/bold]")

        if self.on_topology_update:
            self.on_topology_update(new_topology)
        return new_topology

    def _log_status(self, message: str, level: str = "info", session: Session | None = None):
        log_level = logging.INFO if level == "info" else logging.ERROR if level == "error" else logging.WARNING
        logger.log(log_level, message)
        if session:
            session.append_log("_manager", message)

    def _default_ask_user(self, node_def: Any, inputs: dict[str, Any]) -> str:
        """Fallback HITL handler using questionary with support for typed inputs (text, select, confirm)."""
        import questionary

        from arachne.topologies.schema import QuestionType

        q_obj = node_def.question
        if not q_obj:
            return questionary.text("  Please provide input:").ask()

        # Robust extraction for both Pydantic models and plain dictionaries
        if isinstance(q_obj, dict):
            prompt_text = q_obj.get("query", str(q_obj))
            q_type = q_obj.get("type", QuestionType.TEXT)
            choices = q_obj.get("choices", [])
            default = q_obj.get("default", "")
        else:
            prompt_text = q_obj.query
            q_type = q_obj.type
            choices = q_obj.choices
            default = q_obj.default

        # Dynamic Templating: Support {input_name} placeholders in prompt and choices
        # Use safe literal replacement instead of str.format() to handle values with curly braces
        def substitute_placeholders(text: str, values: dict[str, Any]) -> str:
            """Replace {key} placeholders with values without format-string parsing."""
            result = text
            for key, value in values.items():
                placeholder = f"{{{key}}}"
                result = result.replace(placeholder, str(value))
            return result

        prompt_text = substitute_placeholders(prompt_text, inputs)
        choices = [substitute_placeholders(str(c), inputs) for c in choices]
        default = substitute_placeholders(str(default), inputs) if default else default

        msg = prompt_text

        # Handle different question types
        if q_type == QuestionType.SELECT and choices:
            return questionary.select(msg, choices=choices, default=default or choices[0]).ask()
        if q_type == QuestionType.CONFIRM:
            val = questionary.confirm(msg, default=str(default).lower() == "true" if default else True).ask()
            return str(val)

        return questionary.text(msg, default=str(default)).ask()
