import asyncio

import dspy
from pydantic import BaseModel, Field
from rich.console import Console
from wikipediaapi import Wikipedia

console = Console()


class WikipediaSearchInput(BaseModel):
    """Input for Wikipedia search."""

    query: str = Field(description="The topic or entity to search for on Wikipedia.")
    language: str = Field(default="en", description="Wikipedia language code (e.g. 'en', 'de', 'fr').")


@dspy.Tool
async def wikipedia_search_async(query: str, language: str = "en", **_kwargs) -> str:
    """Search Wikipedia and return the summary of the most relevant page.

    Use this for high-quality, factual background information, history, and entity definitions.
    """
    console.print(f'    [cyan]📚 Searching Wikipedia for:[/cyan] [bold]"{query}"[/bold]')
    def _fetch_wiki():
        wiki = Wikipedia(
            user_agent="ArachneAgent/1.0 (https://github.com/Strategic-Automation/arachne)",
            language=language,
        )
        page = wiki.page(query)
        if page.exists():
            return f"## {page.title}\n{page.summary[:4000]}\n\n**Source**: {page.fullurl}"
        else:
            return f"Wikipedia page for '{query}' not found. Try a more specific or common title."

    # Execute synchronous search in a thread pool to avoid blocking the asyncio event loop
    result = await asyncio.to_thread(_fetch_wiki)

    # Persist search result to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("wikipedia_search_async", query, result)
    return result
