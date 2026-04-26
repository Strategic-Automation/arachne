"""Integration tests for the context7 MCP server via Arachne's MCPManager.

Requires npx and @upstash/context7-mcp to be available.
Run with: uv run pytest -m integration tests/test_mcp_context7.py
"""

import shutil

import dspy
import pytest

from arachne.runtime.mcp_manager import MCPManager

# ── Helpers ────────────────────────────────────────────────────────────────


def _check_npx_available() -> bool:
    """Check if npx is available."""
    return shutil.which("npx") is not None


async def _connect_context7() -> MCPManager:
    """Register and connect the context7 MCP server, return manager."""
    mgr = await MCPManager.instance()
    mgr.register(
        name="context7",
        command="npx",
        args=["@upstash/context7-mcp"],
    )
    try:
        await mgr.ensure_connected()
    except Exception as e:
        await mgr.close_all()
        pytest.skip(f"Failed to connect to context7 MCP server: {e}")
    return mgr


def _get_tool_by_name(tools: list[dspy.Tool], name: str) -> dspy.Tool | None:
    """Find a tool by its name."""
    for t in tools:
        if t.name == name:
            return t
    return None


def _extract_library_id(text: str) -> str | None:
    """Extract a Context7-compatible library ID from text.

    Looks for patterns like /org/project or /org/project/version.
    """
    import re

    matches = re.findall(r"/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)?", text)
    if matches:
        return matches[0]
    return None


# ── Test: Tool List ────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context7_tool_list():
    """Connect and list all available tools from the context7 server.

    Verify that resolve-library-id and query-docs are in the list.
    """
    if not _check_npx_available():
        pytest.skip("npx not available")

    mgr = await _connect_context7()
    try:
        tools = mgr.get_tools(["context7"])
        assert len(tools) > 0, "Expected at least one tool from context7"

        tool_names = {t.name for t in tools}
        assert "resolve-library-id" in tool_names, f"resolve-library-id not found in tools: {tool_names}"
        assert "query-docs" in tool_names, f"query-docs not found in tools: {tool_names}"
    finally:
        await mgr.close_all()


# ── Test: Resolve Library ID ───────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context7_resolve_library():
    """Connect to context7, call resolve-library-id for 'DSPy'.

    Verify we get back valid library IDs.
    """
    if not _check_npx_available():
        pytest.skip("npx not available")

    mgr = await _connect_context7()
    try:
        tools = mgr.get_tools(["context7"])
        assert _get_tool_by_name(tools, "resolve-library-id") is not None, "resolve-library-id tool not found"

        # Call the tool directly via the MCP session (async-safe)
        session = mgr._sessions["context7"]
        result = await session.call_tool(
            "resolve-library-id",
            arguments={"query": "How to create a DSPy module?", "libraryName": "DSPy"},
        )

        # Extract text content from the MCP result
        content_texts = _extract_texts(result)
        assert len(content_texts) > 0, "Expected text content in resolve-library-id result"

        full_text = "\n".join(content_texts)
        assert "DSPy" in full_text or "dspy" in full_text.lower(), (
            f"Expected result to reference DSPy, got: {full_text[:500]}"
        )

        # Verify library IDs are present in /org/project format
        lib_id = _extract_library_id(full_text)
        assert lib_id is not None, f"Expected library ID in /org/project format, got: {full_text[:500]}"
    finally:
        await mgr.close_all()


# ── Test: Query Docs ───────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context7_query_docs():
    """After resolving a library ID, call query-docs for a DSPy question.

    Verify we get back documentation content.
    """
    if not _check_npx_available():
        pytest.skip("npx not available")

    mgr = await _connect_context7()
    try:
        tools = mgr.get_tools(["context7"])
        assert _get_tool_by_name(tools, "query-docs") is not None, "query-docs tool not found"

        session = mgr._sessions["context7"]

        # Step 1: Resolve the library ID
        resolve_result = await session.call_tool(
            "resolve-library-id",
            arguments={"query": "How to create a DSPy module?", "libraryName": "DSPy"},
        )
        resolve_texts = _extract_texts(resolve_result)
        full_resolve = "\n".join(resolve_texts)

        lib_id = _extract_library_id(full_resolve)
        if not lib_id:
            # Fallback to known DSPy library ID
            lib_id = "/stanfordnlp/dspy"

        # Step 2: Query docs with the resolved library ID
        doc_result = await session.call_tool(
            "query-docs",
            arguments={
                "libraryId": lib_id,
                "query": "How to create a DSPy module?",
            },
        )
        doc_texts = _extract_texts(doc_result)
        assert len(doc_texts) > 0, "Expected text content in query-docs result"

        full_doc = "\n".join(doc_texts)
        doc_lower = full_doc.lower()
        assert any(term in doc_lower for term in ["dspy", "module", "signature", "predict"]), (
            f"Expected documentation content about DSPy, got: {full_doc[:500]}"
        )
    finally:
        await mgr.close_all()


# ── Helpers ────────────────────────────────────────────────────────────────


def _extract_texts(result) -> list[str]:
    """Extract text strings from an MCP CallToolResult."""
    texts = []
    for item in result.content:
        if hasattr(item, "text"):
            texts.append(item.text)
    return texts
