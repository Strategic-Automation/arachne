"""Langfuse observability callbacks for browser-use agents.

Provides `create_langfuse_callbacks()` which returns (step_callback, done_callback)
suitable for passing to `browser_use.Agent`.  Returns ``(None, None)`` when Langfuse
is disabled or not installed.

Compatible with Langfuse v4 (OTel-based API).  Uses ``span.update()`` and
``span.end()`` instead of the old context-manager pattern.
"""

import contextlib
import os

from arachne.config import Settings


def create_langfuse_callbacks(task: str, settings: Settings):
    """Create step and done callbacks that send telemetry to Langfuse.

    The Langfuse client is created lazily on the first ``step_callback`` invocation
    so that its background threads are never spawned for sessions where the tool
    is not actually called.
    """
    if not settings.langfuse.enabled:
        return None, None

    try:
        from langfuse import Langfuse
    except ImportError:
        return None, None

    session_id = os.getenv("LANGFUSE_SESSION_ID")
    session_name = os.getenv("LANGFUSE_SESSION_NAME", "")

    # Shared state — populated lazily on first step.
    _state: dict = {"client": None, "root_span": None}

    def _get_or_create_span():
        """Create the Langfuse client and root span on first use."""
        if _state["root_span"] is not None:
            return _state["root_span"]

        client = Langfuse(
            public_key=settings.langfuse.public_key or None,
            secret_key=settings.langfuse.secret_key.get_secret_value() if settings.langfuse.secret_key else None,
            base_url=settings.langfuse.host or None,
        )
        _state["client"] = client

        metadata = {
            "tool": "deep_research_async",
            "browser_llm_model": settings.browser_llm_model or settings.llm_model,
        }
        if session_id:
            metadata["session_id"] = session_id
            metadata["session_name"] = session_name

        root_span = client.start_observation(
            name="deep-research",
            as_type="agent",
            input={"task": task},
            metadata=metadata,
        )
        _state["root_span"] = root_span
        return root_span

    async def step_callback(browser_state, agent_output, step_num: int) -> None:
        """Emit a child observation for each browser-use agent step."""
        try:
            root_span = _get_or_create_span()
            thinking = getattr(agent_output, "thinking", None)
            next_goal = getattr(agent_output, "next_goal", None)
            action_count = len(agent_output.action) if hasattr(agent_output, "action") and agent_output.action else 0

            # Create a child span under the root observation
            child = root_span.start_observation(
                name=f"step-{step_num}",
                as_type="span",
                input={
                    "thinking": thinking[:200] if thinking else None,
                    "next_goal": next_goal[:200] if next_goal else None,
                    "action_count": action_count,
                },
                metadata={"type": "agent_step"},
            )
            # Immediately end the child — it records the step metadata
            child.end()
        except Exception:
            pass  # Never fail the agent on telemetry error

    async def done_callback(history) -> None:
        """Finalise the root span, flush, and shut down background threads."""
        client = _state.get("client")
        root_span = _state.get("root_span")
        if client is None or root_span is None:
            return
        try:
            final_result = history.final_result() if hasattr(history, "final_result") else str(history)
            total_steps = len(history.history) if hasattr(history, "history") else 0
            root_span.update(
                output={
                    "final_result": final_result,
                    "total_steps": total_steps,
                }
            )
        except Exception:
            pass
        with contextlib.suppress(Exception):
            root_span.end()
        with contextlib.suppress(Exception):
            client.flush()

    return step_callback, done_callback
