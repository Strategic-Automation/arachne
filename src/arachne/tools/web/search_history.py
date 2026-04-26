"""Search history tool — lets agents recall previous searches from the current session."""

import dspy


@dspy.Tool
def get_previous_searches(query: str = "", tool_name: str = "", limit: int = 10, **_kwargs) -> str:
    """Retrieve results from previous web searches in the current session.

    Use this BEFORE performing a new search to avoid repeating work that was
    already done in an earlier attempt. This is especially useful after a
    healing/retry cycle, where previous search results are preserved even
    though the node was re-created.

    Args:
        query: Optional text to filter previous searches by query or result content.
        tool_name: Optional tool name to filter (e.g. ``duckduckgo_search_async``).
        limit: Maximum number of previous searches to return (default 10).
    """
    from arachne.runtime.search_memory import get_store

    store = get_store()
    if store is None:
        return "No search history available (no active session store)."

    return store.get_previous_searches(
        query=query or None,
        tool=tool_name or None,
        limit=limit,
    )
