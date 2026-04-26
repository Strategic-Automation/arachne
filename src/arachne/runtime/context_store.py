"""Shared context store for DSPy agent runs.

Provides a per-task dictionary (via ContextVar) that collects user answers
from request_context tool calls, making them available to quality_reward
functions during dspy.Refine evaluation.

ContextVar is inherently per-coroutine/per-task isolated in asyncio,
so no threading.Lock is needed — following the same pattern Pydantic
uses for validation context.
"""

from __future__ import annotations

from contextvars import ContextVar

_store: ContextVar[dict[str, str] | None] = ContextVar("context_store", default=None)


def put(key: str, value: str) -> None:
    """Store a context value in the current task's context."""
    current = _store.get()
    current = {} if current is None else dict(current)
    current[key] = value
    _store.set(current)


def get_all() -> dict[str, str]:
    """Get all stored context values for the current task."""
    v = _store.get()
    return dict(v) if v else {}


def clear() -> None:
    """Clear all stored context values for the current task."""
    _store.set({})
