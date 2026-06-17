import asyncio
import time
from typing import Any

import arxiv
import dspy
from pydantic import BaseModel, Field
from rich.console import Console

console = Console()

_ARXIV_REQUEST_INTERVAL_SECONDS = 3.0
_arxiv_request_lock = asyncio.Lock()
_last_arxiv_request_started_at = 0.0


class ArXivSearchInput(BaseModel):
    """Input for ArXiv search."""

    query: str = Field(description="Search query for academic papers (e.g. 'Deep Learning agents').")
    max_results: int = Field(default=3, description="Maximum number of papers to retrieve.")


async def _queued_arxiv_results(client: arxiv.Client, search_obj: arxiv.Search) -> list[Any]:
    """Run an arXiv search off-loop while keeping requests serial."""
    global _last_arxiv_request_started_at

    async with _arxiv_request_lock:
        elapsed = time.monotonic() - _last_arxiv_request_started_at
        wait_seconds = _ARXIV_REQUEST_INTERVAL_SECONDS - elapsed
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        _last_arxiv_request_started_at = time.monotonic()
        return await asyncio.to_thread(_fetch_arxiv_results, client, search_obj)


def _fetch_arxiv_results(client: arxiv.Client, search_obj: arxiv.Search) -> list[Any]:
    return list(client.results(search_obj))


@dspy.Tool
async def arxiv_search_async(query: str, max_results: int = 3, **_kwargs) -> str:
    """Search ArXiv for scientific and technical papers.

    Use this for technical research, understanding state-of-the-art AI, physics, or computer science.
    """
    console.print(f'    [cyan]🔬 Searching ArXiv for:[/cyan] [bold]"{query}"[/bold]')
    client = arxiv.Client()
    search_obj = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance)

    results = []

    search_results = await _queued_arxiv_results(client, search_obj)

    for i, res in enumerate(search_results, 1):
        summary = res.summary.replace("\n", " ")
        results.append(
            f"### {i}. {res.title}\n"
            f"**Authors**: {', '.join(a.name for a in res.authors)} | **Date**: {res.published.strftime('%Y-%m-%d')}\n\n"
            f"{summary[:1000]}...\n\n"
            f"**Link**: {res.pdf_url}\n"
        )

    result = f"No ArXiv papers found for '{query}'." if not results else "\n".join(results)

    # Persist search result to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("arxiv_search_async", query, result)
    return result
