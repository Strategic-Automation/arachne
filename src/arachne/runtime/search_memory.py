"""Session-scoped search memory — persists web search results across healing iterations.

When a react-based node performs web searches and then fails, the self-healing loop
recreates NodeExecutors from scratch, losing all intermediate search results. This
module provides a persistent search memory that:

1. Automatically records search tool results to the session directory.
2. Survives across healing iterations within the same session.
3. Provides lookup tools so agents can recall previous searches.
4. Injects previous search context into node inputs on retry.

Storage format: ``<session_dir>/searches.jsonl`` (one JSON object per line).
"""

import json
import time
from contextvars import ContextVar
from pathlib import Path

from pydantic import BaseModel, Field


class SearchRecord(BaseModel):
    """A single persisted search result."""

    tool: str = Field(description="Name of the search tool used (e.g. duckduckgo_search_async)")
    query: str = Field(description="The search query or URL")
    result: str = Field(description="The search result text")
    timestamp: float = Field(default_factory=lambda: time.time())
    node_id: str = Field(default="", description="Node that performed the search, if known")
    tags: list[str] = Field(default_factory=list, description="Categorisation tags")


class SearchMemoryStore:
    """Persistent, session-scoped store for web search results.

    Usage::

        store = SearchMemoryStore(session_dir)
        store.record("duckduckgo_search_async", "AI safety", "Found 5 results...")
        store.record("web_fetch_async", "https://example.com", "Page content...")

        # Later, in a healing iteration:
        prior = store.get_previous_searches("AI safety")
    """

    def __init__(self, session_dir: Path | None = None) -> None:
        self._session_dir = session_dir
        self._records: list[SearchRecord] = []
        self._file_path: Path | None = None

        if session_dir is not None:
            self._file_path = session_dir / "searches.jsonl"
            self._load_existing()

        # Set the ContextVar so tools can access the store
        _search_memory.set(self)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_existing(self) -> None:
        """Load previously saved search records from the session file."""
        if self._file_path is None or not self._file_path.exists():
            return
        with open(self._file_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._records.append(SearchRecord.model_validate(data))
                except (json.JSONDecodeError, Exception):
                    continue

    def _append_to_file(self, record: SearchRecord) -> None:
        """Append a single record to the JSONL file."""
        if self._file_path is None:
            return
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        tool: str,
        query: str,
        result: str,
        node_id: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Record a search result and persist it.

        Returns a brief confirmation string (useful when called as a tool).
        """
        rec = SearchRecord(
            tool=tool,
            query=query,
            result=result,
            node_id=node_id,
            tags=tags or [],
        )
        self._records.append(rec)
        self._append_to_file(rec)
        return f"Search result recorded ({tool}: {query[:60]}{'...' if len(query) > 60 else ''})"

    def get_previous_searches(self, query: str | None = None, tool: str | None = None, limit: int = 10) -> str:
        """Retrieve previous search results, optionally filtered by query text or tool name.

        This is the agent-facing lookup: returns a formatted string summarising
        past searches so the agent can reuse prior work instead of re-searching.
        """
        if not self._records:
            return "No previous search results found in this session."

        matches = self._records
        if query:
            q_lower = query.lower()
            matches = [r for r in matches if q_lower in r.query.lower() or q_lower in r.result.lower()]
        if tool:
            matches = [r for r in matches if r.tool == tool]

        # Most recent first
        matches = sorted(matches, key=lambda r: r.timestamp, reverse=True)[:limit]

        if not matches:
            return f"No previous searches matching '{query}'" + (f" via {tool}" if tool else "")

        lines = [f"Previous search results ({len(matches)} found in this session):"]
        for i, r in enumerate(matches, 1):
            ts = time.strftime("%H:%M:%S", time.localtime(r.timestamp))
            node_info = f" (node: {r.node_id})" if r.node_id else ""
            lines.append(f"\n### Previous Search {i} [{r.tool}] at {ts}{node_info}")
            lines.append(f"**Query**: {r.query}")
            # Truncate very long results for context efficiency
            result_text = r.result
            if len(result_text) > 2000:
                result_text = result_text[:1500] + "\n... [TRUNCATED - use the URL to re-fetch if needed]"
            lines.append(f"**Result**:\n{result_text}")

        return "\n".join(lines)

    def get_all_records(self) -> list[SearchRecord]:
        """Return all stored records (for context injection)."""
        return list(self._records)

    def get_summary_for_context(self, max_chars: int = 4000) -> str:
        """Generate a concise summary of all prior searches for injection into node context.

        This is used to tell a healing/retry node what searches were already performed
        so it doesn't repeat them unnecessarily.
        """
        if not self._records:
            return ""

        lines = ["## Previous Search History (from earlier attempts in this session)"]
        lines.append(
            "The following searches were already performed. Use these results instead of re-searching when possible.\n"
        )

        for i, r in enumerate(self._records, 1):
            ts = time.strftime("%H:%M:%S", time.localtime(r.timestamp))
            # Concise format for context injection
            result_preview = r.result[:500] if len(r.result) > 500 else r.result
            if len(r.result) > 500:
                result_preview += "..."
            lines.append(f'{i}. [{r.tool}] Query: "{r.query}" (at {ts})')
            lines.append(f"   Result preview: {result_preview}")
            lines.append("")

        summary = "\n".join(lines)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 100] + "\n\n... [Additional searches truncated]"
        return summary

    def count(self) -> int:
        """Return the number of stored search records."""
        return len(self._records)


# ContextVar for async-safe access across the execution lifecycle.
# NOTE: Must be defined AFTER SearchMemoryStore class to avoid forward-reference NameError.
_search_memory: ContextVar[SearchMemoryStore | None] = ContextVar("search_memory", default=None)


# ------------------------------------------------------------------
# Module-level convenience functions (ContextVar-backed)
# ------------------------------------------------------------------


def get_store() -> SearchMemoryStore | None:
    """Get the active SearchMemoryStore from the current async context."""
    return _search_memory.get()


def set_store(store: SearchMemoryStore) -> None:
    """Set the active SearchMemoryStore for the current async context."""
    _search_memory.set(store)


def record_search(tool: str, query: str, result: str, node_id: str = "") -> str:
    """Record a search result using the active store (if any).

    Safe to call even when no store is active — returns empty string.
    """
    store = _search_memory.get()
    if store is None:
        return ""
    return store.record(tool=tool, query=query, result=result, node_id=node_id)
