"""Tests for centralized Pydantic schemas."""

import pytest
from pydantic import ValidationError

from arachne.runtime.schemas import (
    FailedNodeInfo,
    HealAttempt,
    HealDiagnosis,
    SemanticResult,
    SkillGenResult,
    ToolGenResult,
)


class TestFailedNodeInfo:
    def test_defaults(self):
        node = FailedNodeInfo(node_id="search", role="react", error="Timeout")
        assert node.node_id == "search"
        assert node.duration_seconds == 0.0
        assert node.tools_used == []
        assert node.mcp_servers == []
        assert node.inputs == {}

    def test_full_construction(self):
        node = FailedNodeInfo(
            node_id="analyze",
            role="chain_of_thought",
            error="LLM refusal",
            duration_seconds=12.5,
            tools_used=["web_search", "read_file"],
            mcp_servers=["filesystem"],
            inputs={"query": "test"},
        )
        assert node.role == "chain_of_thought"
        assert len(node.tools_used) == 2
        assert node.inputs["query"] == "test"


class TestHealAttempt:
    def test_defaults(self):
        attempt = HealAttempt(attempt=1, strategy="retry", fix_description="Retry node")
        assert attempt.outcome == ""
        assert attempt.confidence == 0.0
        assert attempt.failed_nodes == []

    def test_extra_config_allows_unknown_fields(self):
        attempt = HealAttempt(attempt=1, strategy="retry", fix_description="test")
        # Pydantic extra=allow means we can add arbitrary fields
        attempt.model_extra["custom"] = "value"


class TestHealDiagnosis:
    def test_valid_diagnosis(self):
        diag = HealDiagnosis(
            fix_strategy="re-route",
            fix_description="Swap web_search for a new API",
            requires_human=False,
            topology_modifications='{"swap": "web_search"}',
            confidence_score=0.85,
        )
        assert diag.fix_strategy == "re-route"
        assert diag.confidence_score == 0.85

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValidationError):
            HealDiagnosis(
                fix_strategy="retry",
                fix_description="test",
                confidence_score=1.5,  # > 1.0 invalid
            )

        with pytest.raises(ValidationError):
            HealDiagnosis(
                fix_strategy="retry",
                fix_description="test",
                confidence_score=-0.1,  # < 0.0 invalid
            )


class TestSemanticResult:
    def test_valid_score(self):
        result = SemanticResult(score=0.9, issues=[], improvements=["none"])
        assert result.score == 0.9
        assert result.issues == []

    def test_invalid_score_raises(self):
        with pytest.raises(ValidationError):
            SemanticResult(score=2.0, issues=[])


class TestToolGenResult:
    def test_tool_result(self):
        result = ToolGenResult(code="def foo(): pass")
        assert result.code == "def foo(): pass"


class TestSkillGenResult:
    def test_skill_result(self):
        result = SkillGenResult(content="# My Skill\\n\\nContent here")
        assert "My Skill" in result.content
