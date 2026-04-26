"""Tests for token management and stability logic."""

import unittest.mock as mock

from arachne.runtime.token_manager import (
    ModelLimits,
    compress_payload,
    compress_trajectory,
    count_tokens,
    fetch_ollama_limits,
    fetch_openrouter_limits,
)


@mock.patch("litellm.token_counter")
def test_count_tokens(mock_counter):
    """Verify token counting handles strings and falls back gracefully."""
    mock_counter.side_effect = Exception("LiteLLM failed")
    # Falling back to character-based heuristic: ~4 chars per token
    assert count_tokens("aaaa", "gpt-4") == 1
    assert count_tokens("", "gpt-4") == 0
    long_str = "a" * 1000
    assert count_tokens(long_str, "unknown-model") == 250


def test_model_limits():
    """Verify ModelLimits properties."""
    limits = ModelLimits(context_window=10000, stability_floor=2000)
    assert limits.safe_input_limit == 8000


@mock.patch("requests.get")
def test_fetch_openrouter_limits(mock_get):
    """Test OpenRouter limit resolution with mocked API."""
    mock_get.return_value.json.return_value = {
        "data": [
            {
                "id": "meta-llama/llama-3-70b-instruct",
                "context_length": 131072,
                "top_provider": {"max_completion_tokens": 4096},
            }
        ]
    }
    mock_get.return_value.status_code = 200

    limits = fetch_openrouter_limits("meta-llama/llama-3-70b-instruct")
    assert limits is not None
    assert limits.context_window == 131072
    assert limits.max_output == 4096


@mock.patch("requests.post")
def test_fetch_ollama_limits(mock_post):
    """Test Ollama limit resolution with mocked API."""
    mock_post.return_value.json.return_value = {
        "parameters": "num_ctx                        8192\n",
        "model_info": {"llama.context_length": 8192},
    }
    mock_post.return_value.status_code = 200

    limits = fetch_ollama_limits("llama3", "http://localhost:11434")
    assert limits is not None
    assert limits.context_window == 8192


def test_compress_trajectory_no_compression_needed():
    """Verify trajectory is returned as-is if within limit."""
    history = [{"role": "user", "content": "hi"}]
    compressed = compress_trajectory(history, "gpt-4", 1000, lambda x: "summary")
    assert compressed == history


def test_compress_trajectory_middle_out():
    """Verify Middle-Out strategy protects head and tail."""
    history = [
        {"role": "system", "content": "system prompt"},  # Head 0
        {"role": "user", "content": "goal prompt"},  # Head 1
        {"role": "assistant", "content": "middle 1"},
        {"role": "user", "content": "middle 2"},
        {"role": "assistant", "content": "tail 1"},  # Tail 0
        {"role": "user", "content": "tail 2"},  # Tail 1
    ]

    def mock_summarizer(text):
        return "summary of middle"

    # Set limit very low to trigger compression
    compressed = compress_trajectory(history, "gpt-4", 2, mock_summarizer)

    assert len(compressed) == 5  # Head(2) + Summary(1) + Tail(2)
    assert compressed[0]["content"] == "system prompt"
    assert compressed[1]["content"] == "goal prompt"
    assert "[CONCISE TRAJECTORY SUMMARY" in compressed[2]["content"]
    assert compressed[3]["content"] == "tail 1"
    assert compressed[4]["content"] == "tail 2"


def test_compress_payload_semantic():
    """Verify massive payload fields are semantically compressed."""
    kwargs = {"small": "tiny value", "massive": "a" * 5000}

    def mock_summarizer(text):
        return "concise summary"

    # Budget is small
    compressed = compress_payload(kwargs, "gpt-4", 100, mock_summarizer)

    assert compressed["small"] == "tiny value"
    assert "[SEMANTIC SUMMARY]" in compressed["massive"]
    assert compressed["massive"] == "[SEMANTIC SUMMARY]\nconcise summary"


def test_compress_payload_slicing_fallback():
    """Verify slicing fallback if summarizer fails."""
    kwargs = {"massive": "a" * 5000}

    def failing_summarizer(text):
        raise ValueError("LLM down")

    compressed = compress_payload(kwargs, "gpt-4", 100, failing_summarizer)

    assert "... [TRUNCATED] ..." in compressed["massive"]
    assert "aaaaa" in compressed["massive"]  # Head/Tail preserved
