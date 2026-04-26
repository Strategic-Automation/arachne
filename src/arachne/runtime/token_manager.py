"""Token counting and trajectory management logic."""

import logging
from typing import Any

import litellm
import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelLimits(BaseModel):
    """Container for model-specific constraints and capabilities."""

    context_window: int = Field(default=128000)
    max_output: int = Field(default=4096)
    stability_floor: int = Field(default=4096)
    source: str = Field(default="default")
    supports_function_calling: bool = Field(
        default=True, description="Whether the model supports native function calling"
    )
    supports_structured_output: bool = Field(
        default=True, description="Whether the model supports structured output (response_format, JSON mode)"
    )

    @property
    def safe_input_limit(self) -> int:
        """Maximum tokens allowed for input while preserving the stability floor.

        Safeguard: The floor is capped at 50% of the total window for small models
        to ensure there's still room for input context.
        """
        effective_floor = min(self.stability_floor, self.context_window // 2)
        return self.context_window - effective_floor


def count_tokens(text: str, model: str) -> int:
    """Accurately count tokens for a given model using LiteLLM."""
    try:
        # litellm handles model name normalization
        return litellm.token_counter(model=model, text=text)
    except Exception:
        # Fallback to character-based heuristic: ~4 chars per token
        return len(text) // 4


def fetch_openrouter_limits(model_id: str) -> ModelLimits | None:
    """Fetch runtime limits directly from OpenRouter API."""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for m in data.get("data", []):
            if m.get("id") == model_id:
                # Check for function calling support in supported_parameters
                supported_params = m.get("supported_parameters", [])
                supports_fc = "functions" in supported_params or "tools" in supported_params

                # Check for structured output support (response_format, JSON mode)
                # Most OpenAI-compatible models support this
                supports_structured = "response_format" in supported_params or any(
                    p in supported_params for p in ["json_schema", "structured_outputs"]
                )

                # Heuristic: if model architecture is known to support structured output
                architecture = m.get("architecture", "")
                if not supports_structured and architecture:
                    # Most modern models support structured output
                    supports_structured = True

                return ModelLimits(
                    context_window=m.get("context_length", 128000),
                    max_output=m.get("top_provider", {}).get("max_completion_tokens", 4096),
                    supports_function_calling=supports_fc,
                    supports_structured_output=supports_structured,
                )
    except Exception as e:
        logger.debug(f"OpenRouter metadata fetch failed: {e}")
    return None


def fetch_ollama_limits(model_id: str, base_url: str) -> ModelLimits | None:
    """Fetch runtime limits from Ollama's /api/show endpoint."""
    try:
        # Strip provider prefix if present
        bare_model = model_id.split("/")[-1] if "/" in model_id else model_id

        # Normalize base_url
        server_url = base_url.rstrip("/")
        if server_url.endswith("/v1"):
            server_url = server_url[:-3].rstrip("/")

        resp = requests.post(f"{server_url}/api/show", json={"name": bare_model}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            limits = ModelLimits()

            # 1. Check for function calling support (tools in Modelfile)
            details = data.get("details", {})
            supports_fc = details.get("supports_function_calling", True)  # Default to True for Ollama

            # Check for structured output support (Ollama 0.2+ supports json output)
            supports_structured = details.get("supports_structured_output", True)  # Default to True

            # 2. Check Modelfile parameters (explicit user setting)
            modelfile = data.get("modelfile", "")
            parameters = data.get("parameters", "")
            params = parameters or modelfile
            if "num_ctx" in params:
                for line in params.split("\n"):
                    if "num_ctx" in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                limits.context_window = int(parts[-1])
                                break
                            except ValueError:
                                pass

            # 3. Check GGUF metadata fallback
            if limits.context_window == 128000:  # Still default
                model_info = data.get("model_info", {})
                for key, value in model_info.items():
                    if "context_length" in key and isinstance(value, int | float):
                        limits.context_window = int(value)
                        break

            limits.supports_function_calling = supports_fc
            limits.supports_structured_output = supports_structured
            return limits
    except Exception as e:
        logger.debug(f"Ollama limits fetch failed: {e}")
    return None


def compress_trajectory(
    history: list[dict[str, str]], model: str, limit: int, summarizer_fn: Any
) -> list[dict[str, str]]:
    """
    Compress a conversation history using the Middle-Out strategy.

    Protects:
    - Head (System/Goal)
    - Tail (Last 2 turns)
    Summarizes the middle turns if total tokens > limit.
    """
    total_tokens = sum(count_tokens(m["content"], model) for m in history)
    if total_tokens <= limit:
        return history

    logger.info(f"Trajectory compression triggered: {total_tokens} > {limit}")

    # Head: System prompt and first goal
    head = history[:2] if len(history) >= 2 else history[:1]
    # Tail: Last 2 turns (usually the latest tool result and thought)
    tail = history[-2:] if len(history) >= 4 else []

    middle = history[len(head) : -len(tail)] if tail else history[len(head) :]

    if not middle:
        return head + tail

    # Summarize the middle turns
    middle_text = "\n".join([f"{m['role']}: {m['content']}" for m in middle])
    summary = summarizer_fn(middle_text)

    summary_msg = {"role": "user", "content": f"[CONCISE TRAJECTORY SUMMARY of intermediate steps]\n{summary}"}

    return [*head, summary_msg, *tail]


def compress_payload(kwargs: dict[str, Any], model: str, budget: int, summarizer_fn: Any) -> dict[str, Any]:
    """
    Compress individual input fields semantically if they exceed the budget.
    """
    current_tokens = sum(count_tokens(str(v), model) for v in kwargs.values())
    if current_tokens <= budget:
        return kwargs

    logger.info(f"Payload compression triggered: {current_tokens} > {budget}")

    alpha = budget / current_tokens
    compressed = {}

    for k, v in kwargs.items():
        if not isinstance(v, str):
            compressed[k] = v
            continue

        v_tokens = count_tokens(v, model)
        # Only compress fields that take up more than their fair share
        if v_tokens > (budget // max(1, len(kwargs))):
            try:
                # Attempt semantic summary
                prompt = (
                    "Summarize the following technical data concisely while preserving "
                    f"key identifiers, errors, and structural cues:\n\n{v}"
                )
                summary = summarizer_fn(prompt)
                compressed[k] = f"[SEMANTIC SUMMARY]\n{summary}"
            except Exception:
                # Fallback to head/tail slicing if summarization fails
                char_cap = int(len(v) * alpha * 0.9)
                head = v[: char_cap // 2]
                tail = v[-char_cap // 2 :]
                compressed[k] = f"{head}\n\n... [TRUNCATED] ...\n\n{tail}"
        else:
            compressed[k] = v

    return compressed
