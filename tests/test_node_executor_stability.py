"""Tests for NodeExecutor context stability logic."""

import unittest.mock as mock

import dspy
import pytest

from arachne.runtime.token_manager import ModelLimits
from arachne.topologies.node_executor import NodeExecutor
from arachne.topologies.schema import NodeDef, NodeRole


@pytest.fixture
def mock_node():
    return NodeDef(
        id="test-node",
        name="Stability Test Node",
        description="Verify context management",
        role=NodeRole.PREDICT,
        output="result",
    )


@pytest.mark.asyncio
@mock.patch("arachne.topologies.node_executor.get_model_limits")
@mock.patch("dspy.LM")
async def test_node_executor_actual_max_calculation(mock_lm_class, mock_limits, mock_node, settings):
    """Verify that actual_max tokens are calculated correctly and capped."""
    # Mock limits: 10k context, 4k max_output, 2k stability floor
    mock_limits.return_value = ModelLimits(context_window=10000, max_output=4096, stability_floor=2000)

    executor = NodeExecutor(mock_node, settings)

    # Large input: ~5000 chars (approx 1250 tokens)
    large_input = "a" * 5000

    # We want to check if the logic in execute() sets max_tokens correctly
    with mock.patch("dspy.asyncify") as mock_asyncify:
        mock_callable = mock.AsyncMock(return_value=dspy.Prediction(result="ok"))
        mock_asyncify.return_value = mock_callable

        await executor.execute(input_data=large_input)

        # Check that dspy.LM was called with expected max_tokens
        # Input tokens: ~1250
        # Overhead: ~1000
        # Remaining: 10000 - 1250 - 1000 = 7750
        # Capped by ModelLimits.max_output (4096)
        # So it should be 4096.

        _args, kwargs = mock_lm_class.call_args_list[-1]
        assert kwargs["max_tokens"] <= 4096
        assert kwargs["max_tokens"] >= 1024


@pytest.mark.asyncio
@mock.patch("arachne.topologies.node_executor.compress_payload")
@mock.patch("arachne.topologies.node_executor.get_model_limits")
async def test_node_executor_triggers_compression(mock_limits, mock_compress_payload, mock_node, settings):
    """Verify that compression is triggered when input is massive."""
    mock_limits.return_value = ModelLimits(context_window=1000, stability_floor=100)
    mock_compress_payload.return_value = {"data": "compressed"}

    executor = NodeExecutor(mock_node, settings)

    # Massive input relative to context
    massive_input = "a" * 5000

    with mock.patch("dspy.asyncify") as mock_async:
        mock_async.return_value = mock.AsyncMock(return_value=dspy.Prediction(result="ok"))
        await executor.execute(data=massive_input)

        # Verify compress_payload was called
        assert mock_compress_payload.called
