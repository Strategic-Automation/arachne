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
    wiki = Wikipedia(
        user_agent="ArachneAgent/1.0 (https://github.com/Strategic-Automation/arachne)",
        language=language,
    )

    page = wiki.page(query)
    if page.exists():
        # Return summary and link
        result = f"## {page.title}\n{page.summary[:4000]}\n\n**Source**: {page.fullurl}"
    else:
        # If exact match fails, try a search (though wikipedia-api is primarily for retrieval)
        # For now, if it doesn't exist, we'll return a failure
        result = f"Wikipedia page for '{query}' not found. Try a more specific or common title."

    # Persist search result to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("wikipedia_search_async", query, result)
    return result
