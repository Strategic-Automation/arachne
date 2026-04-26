import dspy
import pytest

from arachne.runtime.auto_healer import AutoHealer, FailedNodeInfo, is_transient_error
from arachne.runtime.schemas import HealDiagnosis


class MockAnalyzer:
    def __call__(self, **kwargs):
        # Return a valid HealDiagnosis object wrapped in a prediction
        diag = HealDiagnosis(
            fix_strategy="retry", fix_description="Transient error detected, retrying.", confidence_score=0.9
        )
        return dspy.Prediction(diagnosis=diag)


@pytest.mark.asyncio
async def test_auto_healer_structured_output():
    """Verify that AutoHealer returns structured Pydantic data."""
    healer = AutoHealer()
    # Mock the internal analyzer to avoid real LLM calls
    healer.analyzer = MockAnalyzer()

    goal = "Testing auto-healer"
    failed_nodes = [FailedNodeInfo(node_id="test_node", role="predict", error="Timeout")]
    partial_results = {"node_1": "success"}
    topology = "Graph: test_node(predict)"
    history = []

    prediction = healer.forward(
        goal=goal,
        failed_nodes_list=failed_nodes,
        partial_results=partial_results,
        topology_description=topology,
        attempt_history=history,
    )

    assert prediction.fix_strategy == "retry"
    assert prediction.confidence_score == 0.9
    assert isinstance(prediction.diagnosis, HealDiagnosis)


def test_failed_node_info_serialization():
    """Ensure FailedNodeInfo can be serialized correctly."""
    node = FailedNodeInfo(node_id="search", role="react", error="Mock error")
    data = node.model_dump()
    assert data["node_id"] == "search"
    assert data["role"] == "react"


def test_is_transient_error():
    """Verify classification of transient infrastructure errors."""
    assert is_transient_error("Rate limit exceeded") is True
    assert is_transient_error("Connection timeout") is True
    assert is_transient_error("429 Too Many Requests") is True
    assert is_transient_error("503 Service Unavailable") is True
    assert is_transient_error("Validation error: field missing") is False
    assert is_transient_error("Permission denied") is False


@pytest.mark.asyncio
async def test_rewrite_node_description():
    """Verify that rewrite_node_description calls the internal rewriter."""
    healer = AutoHealer()

    class MockRewriter:
        def __call__(self, **kwargs):
            return dspy.Prediction(new_description="Cleaned instruction")

    healer.rewriter = MockRewriter()

    new_desc = healer.rewrite_node_description(
        original_description="Original task", fix_description="Use better search terms"
    )
    assert new_desc == "Cleaned instruction"
