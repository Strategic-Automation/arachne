"""AutoHealer -- DSPy-based failure diagnosis and repair for Arachne."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import dspy

from arachne.runtime.schemas import (
    FailedNodeInfo,
    HealAttempt,
    HealDiagnosis,
)

logger = logging.getLogger(__name__)

# Patterns that indicate a transient / infrastructure failure rather than
# a structural graph design problem.
_TRANSIENT_ERROR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"timeout",
        r"timed?\s*out",
        r"rate.?limit",
        r"429",
        r"503",
        r"502",
        r"504",
        r"too many requests",
        r"connection\s*(reset|refused|aborted|error|closed)",
        r"ssl\s*error",
        r"read timeout",
        r"connect timeout",
        r"exceeded.*timeout",
        r"network\s*(error|unreachable)",
        r"temporary\s*failure",
        r"service\s*unavailable",
        r"gateway\s*timeout",
        r"retry\s*after",
        r"throttl",
        r"quota\s*exceeded",
        r"resource\s*exhausted",
        r"no specific final result was returned",
    ]
]


def is_transient_error(error_text: str) -> bool:
    """Return True if the error looks like a transient infrastructure issue."""
    return any(pat.search(error_text) for pat in _TRANSIENT_ERROR_PATTERNS)


class HealSignature(dspy.Signature):
    """
    Diagnose a node failure and prescribe a repair strategy.

    STRATEGY DEFINITIONS (follow strictly):

    1. retry — The node hit a TRANSIENT infrastructure error and should simply
       be re-executed with no changes. Use for: timeouts, rate-limits (429),
       connection resets, 502/503/504, temporary network failures, quota errors.

    2. re-route — The node's APPROACH needs adjustment but the overall graph
       structure is correct. Use for: wrong tool selected, prompt needs
       refinement, different API or search engine should be tried, input
       format mismatch that can be fixed by tweaking the node's description.

    3. re-weave — The graph DESIGN is fundamentally wrong for the goal. The
       decomposition of work into nodes is incorrect, steps are missing,
       dependencies are wrong, or the output structure doesn't serve the goal.
       ONLY use re-weave when the problem is architectural, NOT when nodes
       failed due to infrastructure issues like timeouts or rate-limits.

    CRITICAL RULES:
    - Timeouts, rate-limits, and connection errors are NEVER a reason to
      re-weave. These are transient — use retry or re-route instead.
    - re-weave means "the plan is wrong", NOT "execution had problems".
    - If a node keeps failing due to infrastructure issues after retries,
      set requires_human=True instead of re-weaving.
    - Never repeat a strategy that already failed for the same node.
    - Escalate (requires_human=True) if uncertain or if the same error
      persists after retry AND re-route attempts.
    """

    goal: str = dspy.InputField()
    failed_nodes_list: list[FailedNodeInfo] = dspy.InputField(desc="Failed nodes with errors")
    partial_results: str = dspy.InputField(desc="Successful node outputs")
    topology_description: str = dspy.InputField(desc="DAG structure")
    attempt_history: list[HealAttempt] = dspy.InputField(desc="Previous fix attempts")
    diagnosis: HealDiagnosis = dspy.OutputField(
        desc="Structured repair plan containing fix_strategy, fix_description, and confidence_score"
    )


class RewriterSignature(dspy.Signature):
    """
    Rewrite a node's description (instructions) based on a failure diagnosis.

    Goal: Create a single, cohesive, high-quality set of instructions that incorporates
    the fix for the previous failure.

    Rules:
    - Do NOT mention 're-route', 'failed', or 'attempt' in the new description.
    - Do NOT use tags like '[FIXED]' or '[RE-ROUTE]'.
    - The output should be a clean, direct instruction for the node to follow.
    - Preserve the original intent and core responsibilities of the node.
    - Incorporate the specific improvements suggested in the fix description (e.g. use specific tools, change search terms, handle specific data).
    """

    original_description: str = dspy.InputField(desc="The node's current instructions")
    fix_description: str = dspy.InputField(desc="Instructions on how to fix the node's approach")
    new_description: str = dspy.OutputField(desc="The improved, clean instruction for the node")


class AutoHealer(dspy.Module):
    """Analyzes graph execution failures and generates repair plans."""

    def __init__(self) -> None:
        super().__init__()
        self.analyzer = dspy.Predict(HealSignature)
        self.rewriter = dspy.Predict(RewriterSignature)

    def forward(
        self,
        goal: str,
        failed_nodes_list: list[FailedNodeInfo],
        partial_results: dict[str, Any],
        topology_description: str,
        attempt_history: list[HealAttempt],
    ) -> dspy.Prediction:
        # Context management: summarize partial results if too large
        from arachne.runtime.token_manager import count_tokens

        results_str = json.dumps(partial_results, indent=2, default=str)
        lm = dspy.settings.lm
        model_name = getattr(lm, "model", "gpt-4o")
        if count_tokens(results_str, model=model_name) > 4000:
            results_str = results_str[:2000] + "\n... [TRUNCATED] ...\n" + results_str[-2000:]

        result = self.analyzer(
            goal=goal,
            failed_nodes_list=failed_nodes_list,
            partial_results=results_str,
            topology_description=topology_description,
            attempt_history=attempt_history,
        )

        diag: HealDiagnosis = result.diagnosis

        # ── Programmatic guardrail: prevent re-weave for transient errors ──
        # If the LLM chose re-weave but ALL failed nodes have transient errors,
        # downgrade to re-route (or requires_human if re-route was already tried).
        if diag.fix_strategy == "re-weave":
            all_transient = all(is_transient_error(n.error) for n in failed_nodes_list)
            if all_transient:
                # Check if re-route was already attempted for these nodes
                reroute_tried = any(
                    a.strategy == "re-route"
                    for a in attempt_history
                    if set(a.failed_nodes) & {n.node_id for n in failed_nodes_list}
                )
                if reroute_tried:
                    logger.info(
                        "AutoHealer guardrail: transient errors persist after re-route — "
                        "escalating to requires_human instead of re-weave."
                    )
                    diag.fix_strategy = "retry"
                    diag.requires_human = True
                    diag.fix_description = (
                        f"Persistent transient errors (timeouts/rate-limits) after retry and re-route. "
                        f"The graph design is correct but the execution environment has issues. "
                        f"Original diagnosis: {diag.fix_description}"
                    )
                else:
                    logger.info("AutoHealer guardrail: downgrading re-weave to re-route for transient errors.")
                    diag.fix_strategy = "re-route"
                    diag.fix_description = (
                        f"Transient errors detected (timeouts/rate-limits). Trying alternative "
                        f"tools or approaches instead of redesigning the graph. "
                        f"Original diagnosis: {diag.fix_description}"
                    )

        return dspy.Prediction(
            fix_strategy=diag.fix_strategy,
            fix_description=diag.fix_description,
            requires_human=diag.requires_human,
            topology_modifications=diag.topology_modifications,
            confidence_score=diag.confidence_score,
            diagnosis=diag,
        )

    def rewrite_node_description(self, original_description: str, fix_description: str) -> str:
        """Use the LLM to cleanly rewrite a node's instructions based on a fix."""
        result = self.rewriter(original_description=original_description, fix_description=fix_description)
        return result.new_description
