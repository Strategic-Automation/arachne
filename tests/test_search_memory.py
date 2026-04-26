"""Tests for session-scoped search memory — persistence across healing iterations."""

import json
from pathlib import Path

import pytest

from arachne.runtime.search_memory import (
    SearchMemoryStore,
    SearchRecord,
    _search_memory,
    get_store,
    record_search,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_context_var():
    """Ensure the ContextVar is reset between tests."""
    _search_memory.set(None)
    yield
    _search_memory.set(None)


@pytest.fixture
def tmp_session(tmp_path: Path) -> Path:
    """Create a temporary session directory."""
    session_dir = tmp_path / "session_test"
    session_dir.mkdir()
    return session_dir


@pytest.fixture
def store(tmp_session: Path) -> SearchMemoryStore:
    """Create a SearchMemoryStore with a temporary session directory."""
    return SearchMemoryStore(tmp_session)


# ── SearchRecord ──────────────────────────────────────────────────────


class TestSearchRecord:
    def test_creation_with_defaults(self):
        rec = SearchRecord(tool="duckduckgo_search_async", query="AI safety", result="5 results found")
        assert rec.tool == "duckduckgo_search_async"
        assert rec.query == "AI safety"
        assert rec.result == "5 results found"
        assert rec.node_id == ""
        assert rec.tags == []
        assert rec.timestamp > 0

    def test_serialization_roundtrip(self):
        rec = SearchRecord(
            tool="web_fetch_async",
            query="https://example.com",
            result="Page content here",
            node_id="research_node",
            tags=["fetch", "important"],
        )
        json_str = rec.model_dump_json()
        restored = SearchRecord.model_validate_json(json_str)
        assert restored.tool == rec.tool
        assert restored.query == rec.query
        assert restored.result == rec.result
        assert restored.node_id == rec.node_id
        assert restored.tags == rec.tags


# ── SearchMemoryStore ─────────────────────────────────────────────────


class TestSearchMemoryStore:
    def test_init_sets_context_var(self, tmp_session: Path):
        store = SearchMemoryStore(tmp_session)
        assert get_store() is store

    def test_init_without_session_dir(self):
        store = SearchMemoryStore(session_dir=None)
        assert store.count() == 0
        assert get_store() is store

    def test_record_persists_to_file(self, store: SearchMemoryStore, tmp_session: Path):
        store.record("duckduckgo_search_async", "AI safety", "5 results about AI safety")

        searches_file = tmp_session / "searches.jsonl"
        assert searches_file.exists()

        lines = searches_file.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["tool"] == "duckduckgo_search_async"
        assert data["query"] == "AI safety"
        assert "AI safety" in data["result"]

    def test_record_returns_confirmation(self, store: SearchMemoryStore):
        msg = store.record("duckduckgo_search_async", "test query", "results")
        assert "duckduckgo_search_async" in msg
        assert "test query" in msg

    def test_record_truncates_long_query_in_confirmation(self, store: SearchMemoryStore):
        long_query = "x" * 100
        msg = store.record("tool", long_query, "results")
        assert "..." in msg

    def test_multiple_records_append(self, store: SearchMemoryStore, tmp_session: Path):
        store.record("duckduckgo_search_async", "query1", "result1")
        store.record("web_fetch_async", "https://example.com", "page content")
        store.record("wikipedia_search_async", "Python", "Python is...")

        assert store.count() == 3

        lines = (tmp_session / "searches.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3

    def test_loads_existing_records_from_file(self, tmp_session: Path):
        searches_file = tmp_session / "searches.jsonl"
        records = [
            SearchRecord(tool="tool1", query="q1", result="r1"),
            SearchRecord(tool="tool2", query="q2", result="r2"),
        ]
        with open(searches_file, "w") as f:
            for rec in records:
                f.write(rec.model_dump_json() + "\n")

        store = SearchMemoryStore(tmp_session)
        assert store.count() == 2

    def test_handles_corrupt_jsonl_gracefully(self, tmp_session: Path):
        searches_file = tmp_session / "searches.jsonl"
        searches_file.write_text("not json\n\ncorrupt{data\n")

        store = SearchMemoryStore(tmp_session)
        assert store.count() == 0

    def test_handles_mixed_valid_corrupt(self, tmp_session: Path):
        searches_file = tmp_session / "searches.jsonl"
        valid = SearchRecord(tool="tool", query="q", result="r")
        searches_file.write_text(f"bad line\n{valid.model_dump_json()}\nalso bad\n")

        store = SearchMemoryStore(tmp_session)
        assert store.count() == 1


# ── get_previous_searches ─────────────────────────────────────────────


class TestGetPreviousSearches:
    def test_no_records(self, store: SearchMemoryStore):
        result = store.get_previous_searches()
        assert "No previous search results" in result

    def test_returns_all_records(self, store: SearchMemoryStore):
        store.record("tool1", "query1", "result1")
        store.record("tool2", "query2", "result2")

        result = store.get_previous_searches()
        assert "2 found" in result
        assert "query1" in result
        assert "query2" in result

    def test_filter_by_query(self, store: SearchMemoryStore):
        store.record("tool", "AI safety research", "AI safety results")
        store.record("tool", "climate change", "climate results")

        result = store.get_previous_searches(query="AI safety")
        assert "1 found" in result
        assert "AI safety research" in result
        assert "climate" not in result

    def test_filter_by_tool(self, store: SearchMemoryStore):
        store.record("duckduckgo_search_async", "q1", "r1")
        store.record("web_fetch_async", "https://example.com", "page")

        result = store.get_previous_searches(tool="web_fetch_async")
        assert "1 found" in result
        assert "web_fetch_async" in result

    def test_no_matching_results(self, store: SearchMemoryStore):
        store.record("tool", "query", "result")

        result = store.get_previous_searches(query="nonexistent")
        assert "No previous searches matching" in result

    def test_respects_limit(self, store: SearchMemoryStore):
        for i in range(20):
            store.record("tool", f"query_{i}", f"result_{i}")

        result = store.get_previous_searches(limit=5)
        assert "5 found" in result

    def test_truncates_long_results(self, store: SearchMemoryStore):
        long_result = "x" * 5000
        store.record("tool", "query", long_result)

        result = store.get_previous_searches()
        assert "TRUNCATED" in result


# ── get_summary_for_context ──────────────────────────────────────────


class TestGetSummaryForContext:
    def test_empty_store(self, store: SearchMemoryStore):
        assert store.get_summary_for_context() == ""

    def test_generates_summary(self, store: SearchMemoryStore):
        store.record("duckduckgo_search_async", "AI safety", "5 results found")
        store.record("web_fetch_async", "https://example.com", "Page content")

        summary = store.get_summary_for_context()
        assert "Previous Search History" in summary
        assert "AI safety" in summary
        assert "https://example.com" in summary

    def test_truncates_long_summaries(self, store: SearchMemoryStore):
        for i in range(50):
            store.record("tool", f"query_{i}", "result " * 200)

        summary = store.get_summary_for_context(max_chars=500)
        assert len(summary) <= 600  # Allow some margin for truncation footer
        assert "truncated" in summary.lower()

    def test_preview_truncation(self, store: SearchMemoryStore):
        long_result = "x" * 1000
        store.record("tool", "query", long_result)

        summary = store.get_summary_for_context()
        assert "..." in summary
        assert len(summary) < len(long_result)


# ── ContextVar functions ─────────────────────────────────────────────


class TestContextVarFunctions:
    def test_get_store_returns_none_when_unset(self):
        _search_memory.set(None)
        assert get_store() is None

    def test_set_store(self, tmp_session: Path):
        store = SearchMemoryStore(tmp_session)
        assert get_store() is store

    def test_record_search_noop_without_store(self):
        _search_memory.set(None)
        result = record_search("tool", "query", "result")
        assert result == ""

    def test_record_search_with_store(self, store: SearchMemoryStore):
        result = record_search("tool", "test query", "test result")
        assert "tool" in result
        assert store.count() == 1


# ── Persistence across healing iterations (integration) ──────────────


class TestPersistenceAcrossHealing:
    """Simulates the key scenario: search results survive across healing iterations."""

    def test_results_survive_store_recreation(self, tmp_session: Path):
        """Simulate: first attempt records searches, then store is recreated for retry."""
        store1 = SearchMemoryStore(tmp_session)
        store1.record("duckduckgo_search_async", "AI safety breakthroughs", "Found 5 papers...")
        store1.record("web_fetch_async", "https://arxiv.org/paper1", "Full paper content...")
        assert store1.count() == 2

        _search_memory.set(None)

        # Second attempt — new store loads from file
        store2 = SearchMemoryStore(tmp_session)
        assert store2.count() == 2

        summary = store2.get_summary_for_context()
        assert "AI safety breakthroughs" in summary
        assert "arxiv.org" in summary

    def test_new_searches_added_during_retry(self, tmp_session: Path):
        """Searches from attempt 1 AND attempt 2 are all available."""
        store1 = SearchMemoryStore(tmp_session)
        store1.record("duckduckgo_search_async", "initial query", "initial results")
        _search_memory.set(None)

        store2 = SearchMemoryStore(tmp_session)
        store2.record("web_fetch_async", "https://new-url.com", "new content")

        assert store2.count() == 2
        all_searches = store2.get_previous_searches()
        assert "initial query" in all_searches
        assert "new-url.com" in all_searches

    def test_summary_for_context_includes_all_attempts(self, tmp_session: Path):
        """Context injection includes searches from all prior attempts."""
        store1 = SearchMemoryStore(tmp_session)
        store1.record("duckduckgo_search_async", "climate data", "Climate results...")
        _search_memory.set(None)

        store2 = SearchMemoryStore(tmp_session)
        summary = store2.get_summary_for_context()
        assert "climate data" in summary
        assert "Previous Search History" in summary

        store2.record("web_fetch_async", "https://nasa.gov/data", "NASA datasets...")
        _search_memory.set(None)

        store3 = SearchMemoryStore(tmp_session)
        assert store3.count() == 2
        summary3 = store3.get_summary_for_context()
        assert "climate data" in summary3
        assert "nasa.gov" in summary3


# ── get_previous_searches tool integration ────────────────────────────


class TestGetPreviousSearchesTool:
    def test_tool_returns_no_history_without_store(self):
        from arachne.tools.web.search_history import get_previous_searches

        _search_memory.set(None)
        result = get_previous_searches(query="test")
        assert "No search history available" in result

    def test_tool_returns_results_with_store(self, store: SearchMemoryStore):
        from arachne.tools.web.search_history import get_previous_searches

        store.record("duckduckgo_search_async", "AI safety", "5 results")

        result = get_previous_searches(query="AI safety")
        assert "1 found" in result
        assert "AI safety" in result

    def test_tool_registered_in_builtin_tools(self):
        from arachne.tools import _BUILTIN_TOOLS

        assert "get_previous_searches" in _BUILTIN_TOOLS
