"""Triangulated evaluator -- DSPy-native quality assessment of agent output.

Level 0: Rule-based constraint check (cost, safety boundaries)
Level 1: Semantic evaluation via DSPy with Pydantic output
Level 2: Human escalation flag when score is below threshold
"""

import dspy

from arachne.runtime.schemas import SemanticResult
from arachne.topologies.schema import Constraint, FailureReport, NodeRole, ResultStatus


class SemanticEvalSignature(dspy.Signature):
    """Evaluate whether the agent's output achieves the stated goal.

    Score from 0.0 (complete failure) to 1.0 (fully achieved).
    List specific issues found and concrete improvements for re-weaving.
    """

    goal: str = dspy.InputField(desc="The user's original goal or query")
    criteria: str = dspy.InputField(desc="Success criteria to check against, or 'None'")
    trace: str = dspy.InputField(desc="Full execution trace of all nodes, inputs, and outputs.")
    evaluation: SemanticResult = dspy.OutputField(desc="Structured quality assessment")


class TriangulatedEvaluator(dspy.Module):
    """Runs the output through rules, data quality, then semantic DSPy evaluation."""

    MIN_TOOL_OUTPUT_LENGTH: int = 5

    def __init__(self, confidence_threshold: float = 0.8) -> None:
        super().__init__()
        self.confidence_threshold = confidence_threshold
        self.semantic_eval = dspy.Predict(SemanticEvalSignature)

    def _get_hitl_node_ids(self, topology) -> set[str]:
        if not topology:
            return set()
        # include nodes with explicit questions or human roles
        return {n.id for n in topology.nodes if n.role == NodeRole.HUMAN_IN_LOOP or n.question is not None}

    def _detect_bad_tool_data(self, run_result, topology, hitl_node_ids: set[str]) -> tuple[str, str] | None:
        """Check if tool nodes (ReAct) returned empty/garbage data."""
        bad_signals = [
            "no results",
            "no readable content",
            "error fetching",
            "no information",
            "not found",
            "could not find",
            "unable to",
            "no data",
        ]
        # Allow file write confirmations (these are success signals, not errors)
        allow_signals = ["successfully wrote", "saved to"]

        node_results = list(run_result.node_results)
        for nr in node_results:
            # Skip HITL nodes
            if nr.status != ResultStatus.COMPLETED or not nr.output or nr.node_id in hitl_node_ids:
                continue

            # Skip reasoning nodes from this L0.5 check (they are judged by semantic evaluator)
            node_def = topology.nodes_dict.get(nr.node_id) if topology else None
            if node_def and node_def.role not in (NodeRole.REACT,):
                continue

            for k, val in nr.output.items():
                if k in ("thought", "reasoning", "trajectory"):
                    continue
                text = str(val).strip()

                # Immediate failure for empty results
                if not text:
                    return nr.node_id, f"Node '{nr.node_id}' returned empty output for field '{k}'"

                # Skip allow_signals (file write confirmations are valid)
                if any(signal in text.lower() for signal in allow_signals):
                    continue

                # For suspected garbage or short outputs, treat as insufficient data
                if len(text) < self.MIN_TOOL_OUTPUT_LENGTH or any(signal in text.lower() for signal in bad_signals):
                    return nr.node_id, "Data quality check failed: output too short or contains error signals"
        return None

    def forward(
        self,
        goal: str,
        run_result,
        goal_definition=None,
        topology=None,
        attempt: int = 1,
    ) -> dspy.Prediction:
        report = FailureReport(
            goal=goal,
            attempt=attempt,
            confidence_score=1.0,
            evaluation_source="none",
        )

        hitl_node_ids = self._get_hitl_node_ids(topology)
        human_approved = False

        # ── Level 0: Human Supremacy ──
        for nr in run_result.node_results:
            if nr.node_id in hitl_node_ids and nr.status == ResultStatus.COMPLETED:
                raw_val = str(next(iter(nr.output.values()), "")).strip()
                val = raw_val.lower()

                if val in ("true", "yes", "approved", "ok"):
                    human_approved = True
                    break
                elif val.startswith("false") or val.startswith("no"):
                    human_approved = False
                    report.confidence_score = 0.0
                    report.evaluation_source = "human_rejection"

                    reason = (
                        raw_val.split(":", 1)[1].strip()
                        if ":" in raw_val
                        else raw_val[2:].strip()
                        if val.startswith("no")
                        else raw_val[5:].strip()
                    )
                    if not reason or reason.lower() in ("no", "false"):
                        reason = "User rejected result via interactive gate."
                    report.diagnosis = f"Human rejection: {reason}"
                    report.evaluation_details["issues"] = [reason]
                    break

        # Collect failed nodes
        report.failed_nodes = [n.node_id for n in run_result.failed_nodes]
        for nr in run_result.node_results:
            if nr.error:
                report.error_details[nr.node_id] = nr.error

        # ── Level 0: Rule-Based Constraints ──
        if goal_definition and goal_definition.constraints:
            violation = self._check_constraints(run_result, goal_definition.constraints)
            if violation:
                report.evaluation_source, report.confidence_score = "rule_constraint", 0.0
                report.diagnosis = f"Constraint violated: {violation.description}"
                return dspy.Prediction(report=report)

        if report.failed_nodes:
            report.evaluation_source, report.confidence_score = "rule_constraint", 0.0
            report.diagnosis = f"Nodes failed to execute: {', '.join(report.failed_nodes)}"
            return dspy.Prediction(report=report)

        # ── Level 0.5: Tool Output Quality Check ──
        bad_tool = self._detect_bad_tool_data(run_result, topology, hitl_node_ids)
        if bad_tool and not human_approved:
            bad_node_id, bad_diag = bad_tool
            report.evaluation_source, report.confidence_score = "bad_tool_data", 0.4
            report.diagnosis = f"Node '{bad_node_id}' returned suspected garbage or insufficient info: {bad_diag}."
            report.evaluation_details["issues"] = [f"Data quality issue in '{bad_node_id}': {bad_diag}"]
            return dspy.Prediction(report=report)

        # ── Level 0.7: Architectural Hygiene Check ──
        if topology:
            hygiene_issues = self._check_topology_hygiene(goal, topology, run_result)
            if hygiene_issues:
                report.confidence_score = min(report.confidence_score, 0.6)
                # Don't overwrite critical sources like human rejection
                if report.evaluation_source in ("none", "architectural_hygiene"):
                    report.evaluation_source = "architectural_hygiene"
                    report.diagnosis = f"Graph design issues: {'; '.join(hygiene_issues)}"
                else:
                    # Append hygiene issues to diagnosis if it's already a failure
                    report.diagnosis = f"{report.diagnosis}; Graph design issues: {'; '.join(hygiene_issues)}"

                report.evaluation_details["issues"] = list(
                    set(report.evaluation_details.get("issues", []) + hygiene_issues)
                )
                # If we have major hygiene issues, we might still proceed if human approved,
                # but if not, we should probably re-weave.
                if not human_approved:
                    return dspy.Prediction(report=report)

        # ── Level 1: Semantic Evaluation ──
        trace_parts = []
        hitl_answers = {}

        # 1. First pass: Collect all node results and build the trace
        for nr in run_result.node_results:
            node_id = nr.node_id
            status = nr.status.value

            # Extract content from output dict
            output_lines = []
            if nr.output:
                # Group ReAct steps vs final outputs
                main_outputs = {}
                react_steps = []

                # Identify steps
                steps = sorted({k.split("_")[1] for k in nr.output if "_" in k and k.split("_")[1].isdigit()})
                for idx in steps:
                    t = nr.output.get(f"thought_{idx}")
                    tool = nr.output.get(f"tool_name_{idx}")
                    obs = nr.output.get(f"observation_{idx}")

                    step_str = f"  Step {idx}: {t}"
                    if tool and tool != "None":
                        step_str += f"\n  Action: {tool}"
                        if obs:
                            # Truncate observations in the trace to keep it readable
                            obs_str = str(obs)
                            if len(obs_str) > 200:
                                obs_str = obs_str[:100] + " ... " + obs_str[-100:]
                            step_str += f"\n  Observation: {obs_str}"
                    react_steps.append(step_str)

                # Collect other fields
                for k, v in nr.output.items():
                    if any(k.startswith(p) for p in ["thought_", "tool_", "observation_", "tool_name_", "tool_args_"]):
                        continue
                    main_outputs[k] = v

                if react_steps:
                    output_lines.append("Trace:\n" + "\n".join(react_steps))

                for k, v in main_outputs.items():
                    # For very long outputs, just show a snippet
                    val_str = str(v)
                    if len(val_str) > 500:
                        val_str = val_str[:250] + "\n... [Output Snippet] ...\n" + val_str[-250:]
                    output_lines.append(f"{k}: {val_str}")

            output_val = "\n".join(output_lines) or "Empty"

            if nr.node_id in hitl_node_ids:
                node_def = topology.nodes_dict.get(nr.node_id) if topology else None
                question_text = "Question"
                if node_def and node_def.question:
                    question_text = (
                        node_def.question.query if hasattr(node_def.question, "query") else str(node_def.question)
                    )

                # Filter internal fields for HITL output display
                filtered_output = (
                    "\n".join([f"{k}: {v}" for k, v in nr.output.items() if k not in ("thought",)]) or output_val
                )

                trace_parts.append(
                    f"### [Node] {node_id} (HUMAN_IN_LOOP)\n- Question: {question_text}\n- Answer: {filtered_output}"
                )
                hitl_answers[node_id] = output_val
            else:
                trace_parts.append(f"### [Node] {node_id}\n- Status: {status}\n{output_val}")

        full_trace = "\n\n".join(trace_parts)

        # Basic sanity check: Even with human approval, verify meaningful output exists
        if human_approved:
            # Check if sink node(s) produced meaningful output
            sink_ids = set(topology.sink_nodes) if topology else set()
            has_sink_output = False
            for nr in run_result.node_results:
                if (
                    nr.node_id in sink_ids
                    and nr.output
                    and any(v and len(str(v).strip()) > 10 for v in nr.output.values())
                ):
                    has_sink_output = True
                    break

            if not has_sink_output:
                report.confidence_score, report.diagnosis, report.evaluation_source = (
                    0.0,
                    "Human approved but no meaningful output produced.",
                    "empty_output",
                )
            else:
                report.confidence_score, report.diagnosis, report.evaluation_source = (
                    1.0,
                    "Approved by human with meaningful output.",
                    "human_approval",
                )
        else:
            criteria_text = (
                "\n".join(goal_definition.success_criteria)
                if goal_definition and goal_definition.success_criteria
                else f"Evaluate goal: {goal}"
            )
            semantic = self.semantic_eval(goal=goal, criteria=criteria_text, trace=full_trace)
            res: SemanticResult = semantic.evaluation

            report.confidence_score = res.get_score()
            report.diagnosis = (
                f"Semantic Eval: {res.get_score():.2f}. {'; '.join(res.issues)}" if res.issues else "Success"
            )
            report.evaluation_source = "semantic_evaluator"
            report.requires_human = res.get_score() < self.confidence_threshold
            report.evaluation_details = {
                "issues": res.issues,
                "improvements": res.improvements,
                "trace": full_trace,
            }

        return dspy.Prediction(report=report)

    @staticmethod
    def _check_constraints(run_result, constraints: list[Constraint]) -> Constraint | None:
        for c in constraints:
            if c.is_hard_boundary and c.type.value == "cost" and c.value and run_result.total_cost_usd > c.value:
                return c
        return None

    def _check_topology_hygiene(self, goal: str, topology, run_result) -> list[str]:
        """Check for missing verification or bad HITL prompts."""
        issues = []
        tool_names = {t.name for n in topology.nodes for t in n.tools}

        # 1. Check for code generation without verification
        goal_lower = goal.lower()
        is_code_task = any(kw in goal_lower for kw in ["python", "code", "script", "implement", "function"])

        has_verification = any(t in tool_names for t in ["verify_python", "shell_exec"])
        if is_code_task and not has_verification:
            issues.append(
                "Goal involves code generation but no verification tool (verify_python, shell_exec) was used in the graph."
            )

        # 2. Check for HITL prompts without placeholders
        for node in topology.nodes:
            if node.question:
                query = node.question.query if hasattr(node.question, "query") else str(node.question)
                if "{" not in query or "}" not in query:
                    issues.append(
                        f"Human intervention node '{node.id}' has a static question. Use {{placeholder}} to show relevant upstream data to the human."
                    )

        # 3. Check for verification failures that were ignored
        for nr in run_result.node_results:
            node_def = topology.nodes_dict.get(nr.node_id)
            if node_def and any(t.name == "verify_python" for t in node_def.tools):
                output_str = str(nr.output).lower()
                if "syntax error" in output_str or "error" in output_str:
                    issues.append(
                        f"Verification node '{nr.node_id}' detected errors, but execution continued. Re-weave required to fix code."
                    )

        return issues


# Compatibility alias for backwards compatibility
FailureEvaluator = TriangulatedEvaluator
