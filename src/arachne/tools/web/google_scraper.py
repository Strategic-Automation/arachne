import os

import aiohttp
import dspy
from pydantic import BaseModel, Field

from arachne.config import Settings
from arachne.tools.web.browser_search import browser_search_async


class GoogleSearchInput(BaseModel):
    """Input for Google search."""

    query: str = Field(description="The search query for Google.")
    num_results: int = Field(default=5, description="Number of results to return.")


async def _serpapi_search(query: str, api_key: str, num_results: int = 5) -> str:
    """Fallback to SerpApi if configured."""
    url = "https://serpapi.com/search.json"
    params = {"q": query, "api_key": api_key, "engine": "google", "num": num_results}
    async with aiohttp.ClientSession() as session, session.get(url, params=params) as resp:
        if resp.status == 200:
            data = await resp.json()
            results = []
            for res in data.get("organic_results", [])[:num_results]:
                results.append(f"### {res.get('title')}\n**URL**: {res.get('link')}\n\n{res.get('snippet')}\n")
            return "\n".join(results) if results else "No results found via SerpApi."
    return f"SerpApi request failed with status {resp.status}"


async def _brave_search(query: str, api_key: str, num_results: int = 5) -> str:
    """Fallback to Brave Search if configured."""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    params = {"q": query, "count": num_results}
    async with aiohttp.ClientSession() as session, session.get(url, headers=headers, params=params) as resp:
        if resp.status == 200:
            data = await resp.json()
            results = []
            for res in data.get("web", {}).get("results", [])[:num_results]:
                results.append(f"### {res.get('title')}\n**URL**: {res.get('url')}\n\n{res.get('description')}\n")
            return "\n".join(results) if results else "No results found via Brave Search."
    return f"Brave Search request failed with status {resp.status}"


@dspy.Tool
async def google_search_async(query: str, num_results: int = 5, **_kwargs) -> str:
    """Search Google and return a list of result URLs and snippets.

    This tool first attempts to use SerpApi or Brave Search if keys are provided.
    Otherwise, it falls back to a stealth headless browser.
    """
    settings = Settings()

    # 1. Try SerpApi (Gold Standard for Search APIs)
    if settings.serpapi_api_key:
        result = await _serpapi_search(query, settings.serpapi_api_key, num_results)
    # 2. Try Brave Search (Excellent privacy-preserving fallback)
    elif os.getenv("BRAVE_SEARCH_API_KEY"):
        result = await _brave_search(query, os.getenv("BRAVE_SEARCH_API_KEY"), num_results)
    else:
        # 3. Fallback to Stealth Browser (High risk of CAPTCHA/Blocks)
        result = await browser_search_async(queries=query)

    # Persist search result to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("google_search_async", query, result)
    return result


def is_available(settings: Settings | None = None) -> bool:
    """Google search is only 'available' if a reliable API key is provided.
    The headless browser fallback is too unreliable to be exposed as a primary tool.
    """
    if settings is None:
        settings = Settings()
    return bool(settings.serpapi_api_key or os.getenv("BRAVE_SEARCH_API_KEY"))
