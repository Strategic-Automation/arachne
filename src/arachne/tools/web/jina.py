"""Jina search tool — returns result URLs and snippets."""

from __future__ import annotations

import asyncio

import dspy
import httpx
from pydantic import BaseModel, Field

from arachne.config import Settings


class JinaSearchInput(BaseModel):
    """Input for Jina search."""

    query: str = Field(description="Search query for Jina.")
    max_results: int = Field(default=3, description="Number of results to retrieve.")


@dspy.Tool
async def jina_search_async(query: str, max_results: int = 3, **_kwargs) -> str:
    """Search the web using Jina and return a ranked list of results with titles, URLs, and snippets.

    Returns search result metadata only — NOT the full page content.
    After reviewing the results, call ``web_fetch_async`` with the most relevant URL(s)
    to retrieve complete page content for deeper analysis.

    Supports comma-separated queries to run multiple searches in parallel
    (e.g. ``"CEO name, company history, pricing"``).
    """
    settings = Settings()
    api_key = settings.jina_api_key.get_secret_value() if settings.jina_api_key else None

    queries = [q.strip() for q in query.split(",") if q.strip()] or [query]

    async def _search_one(q: str) -> str:
        try:
            headers = {"Accept": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get("https://s.jina.ai/", params={"q": q}, headers=headers)

            if resp.status_code == 401:
                return f"Jina Search failed for '{q}': Authentication Required (401). Set a valid JINA_API_KEY in .env."
            if resp.status_code != 200:
                return f"Jina Search failed for '{q}' with status {resp.status_code}: {resp.text[:200]}"

            data = resp.json()
            items = data.get("data", [])[:max_results]
            if not items:
                return f"Jina returned no results for: {q}"

            entries: list[str] = []
            for i, item in enumerate(items, 1):
                title = item.get("title", "").strip()
                url = item.get("url", "").strip()
                snippet = item.get("content", "").strip()[:500]
                entries.append(f"### {i}. {title}\n**URL**: {url}\n\n{snippet}")

            return f"Results for '{q}':\n\n" + "\n\n---\n\n".join(entries)

        except Exception as e:
            return f"Jina Search error for '{q}': {e}"

    results = await asyncio.gather(*[_search_one(q) for q in queries])
    result_text = "\n\n====\n\n".join(results)

    # Persist search result to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("jina_search_async", query, result_text)
    return result_text
