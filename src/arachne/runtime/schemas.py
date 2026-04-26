"""Centralized Pydantic schemas for Arachne runtime operations.

All non-topology schemas live here -- healing, evaluation, provisioning.
Topology schemas (GraphTopology, NodeDef, etc.) remain in topologies/schema.py
as they serve a different domain (graph definition vs runtime operations).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── FixStrategy ──────────────────────────────────────────────────────


class FixStrategy(StrEnum):
    """Autonomous repair strategies available to the AutoHealer."""

    RETRY = "retry"
    REROUTE = "re-route"
    REWEAVE = "re-weave"


# ── AutoHealer Schemas ───────────────────────────────────────────────


class FailedNodeInfo(BaseModel):
    """Structured info about a single failed node."""

    node_id: str = Field(..., description="The failing node's unique identifier")
    role: str = Field(..., description="DSPy module role (predict, react, chain_of_thought, etc.)")
    error: str = Field(..., description="Error message or traceback")
    duration_seconds: float = Field(default=0.0, description="How long the node ran before failing")
    tools_used: list[str] = Field(default_factory=list, description="Tool names the node tried to call")
    mcp_servers: list[str] = Field(default_factory=list, description="MCP server connection strings")
    inputs: dict[str, str] = Field(default_factory=dict, description="Inputs the node received")


class HealAttempt(BaseModel):
    """Record of a previous healing attempt on this goal."""

    model_config = ConfigDict(extra="allow")

    attempt: int = Field(..., description="Sequential attempt number")
    strategy: str = Field(..., description="Strategy used (retry, re-route, re-weave)")
    fix_description: str = Field(..., description="What the fix described")
    outcome: str = Field(default="", description="What happened after applying (success, same error, new error)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score of the fix")
    failed_nodes: list[str] = Field(default_factory=list, description="Node IDs that failed")


class HealDiagnosis(BaseModel):
    """Structured output from the AutoHealer diagnostic module."""

    fix_strategy: Literal["retry", "re-route", "re-weave"] = Field(
        default="retry",
        description="The chosen repair strategy: retry, re-route, or re-weave",
    )
    fix_description: str = Field(
        default="Failed to diagnose automatically.",
        description="Precise, actionable description of what to change and why",
    )
    requires_human: bool = Field(
        default=False,
        description="True if the failure cannot be resolved autonomously and needs HITL",
    )
    topology_modifications: str = Field(
        default="",
        description="If re-weave: JSON describing topology changes. Empty string otherwise.",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence this fix will succeed (0.0-1.0)",
    )


# ── Evaluator Schemas ────────────────────────────────────────────────


class SemanticResult(BaseModel):
    """Structured output from the semantic evaluation module."""

    score: float | None = Field(default=None, ge=0.0, le=1.0, description="Evaluation confidence 0.0-1.0")
    issues: list[str] = Field(default_factory=list, description="Specific issues or failures found")
    improvements: list[str] = Field(
        default_factory=list, description="Concrete suggestions for re-weaving to fix issues"
    )

    def get_score(self, default: float = 1.0) -> float:
        """Get score with fallback for when LLM doesn't provide one."""
        return self.score if self.score is not None else default


# ── Provision Schemas ────────────────────────────────────────────────


class ToolGenResult(BaseModel):
    """Pydantic output for generated tool code."""

    code: str = Field(description="Python source code for the tool function")


class SkillGenResult(BaseModel):
    """Pydantic output for generated skill content."""

    content: str = Field(description="Markdown content for the skill")
