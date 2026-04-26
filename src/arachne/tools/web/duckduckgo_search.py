"""DuckDuckGo search tool — returns result URLs and snippets."""

from __future__ import annotations

import dspy
from pydantic import BaseModel, Field

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


class DuckDuckGoSearchInput(BaseModel):
    """Input for DuckDuckGo search."""

    query: str = Field(description="The search query for DuckDuckGo.")
    max_results: int = Field(default=5, description="Number of results to return.")


@dspy.Tool
async def duckduckgo_search_async(query: str, max_results: int = 5, **_kwargs) -> str:
    """Search DuckDuckGo and return a ranked list of results with titles, URLs, and short snippets.

    Returns search result metadata only — NOT the full page content.
    After reviewing the results, call ``web_fetch_async`` with the most relevant URL(s)
    to retrieve complete page content for deeper analysis.

    Use this for an initial broad search to identify which pages are worth reading.
    """
    try:
        ddgs = DDGS()
        search_results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"DuckDuckGo search failed: {e}"

    if not search_results:
        return f"No DuckDuckGo results found for '{query}'."

    parts: list[str] = []
    for i, r in enumerate(search_results, 1):
        parts.append(f"### {i}. {r.get('title', '')}\n**URL**: {r.get('href', '')}\n\n{r.get('body', '')}")

    result_text = "\n\n---\n\n".join(parts)

    # Persist search result to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("duckduckgo_search_async", query, result_text)

    return result_text
