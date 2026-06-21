"""Fetch LLM-ready Markdown with Crawl4AI when the optional package is installed."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import dspy

MAX_CHARS = 12000
ALLOWED_SCHEMES = {"http", "https"}


def _validate_web_url(url: str) -> str | None:
    """Return an error message when a URL is not safe for browser crawling."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
        return "Crawl4AI fetch only supports absolute http:// or https:// URLs."
    return None


def _extract_markdown(result: Any) -> str:
    """Normalize Crawl4AI result objects across minor API variations."""
    markdown = getattr(result, "markdown", None)
    if isinstance(markdown, str) and markdown.strip():
        return markdown.strip()

    for candidate in (
        getattr(markdown, "fit_markdown", None),
        getattr(markdown, "raw_markdown", None),
        getattr(result, "fit_markdown", None),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    markdown_v2 = getattr(result, "markdown_v2", None)
    if markdown_v2 is not None:
        for candidate in (
            getattr(markdown_v2, "fit_markdown", None),
            getattr(markdown_v2, "raw_markdown", None),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    extracted_content = getattr(result, "extracted_content", None)
    if isinstance(extracted_content, str) and extracted_content.strip():
        return extracted_content.strip()

    return ""


async def crawl4ai_fetch(url: str, max_chars: int = MAX_CHARS) -> str:
    """Fetch a URL through Crawl4AI and return LLM-ready Markdown."""
    validation_error = _validate_web_url(url)
    if validation_error:
        return validation_error

    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError:
        return "Crawl4AI is not installed. Install it with `uv sync --extra crawl` and run `uv run crawl4ai-setup`."

    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url.strip())
    except Exception as exc:
        return f"Crawl4AI failed to fetch {url}: {exc}"

    markdown = _extract_markdown(result)
    if not markdown:
        success = getattr(result, "success", None)
        error_message = getattr(result, "error_message", None)
        if success is False and error_message:
            return f"Crawl4AI could not extract readable content from {url}: {error_message}"
        return f"Crawl4AI could not extract readable content from {url}"

    return markdown[:max_chars]


@dspy.Tool
async def crawl4ai_fetch_async(url: str, **_kwargs: Any) -> str:
    """Fetch a webpage as clean Markdown with Crawl4AI.

    Use this when a page needs browser-rendered, LLM-ready Markdown for RAG,
    agent context, or structured extraction. It requires the optional
    ``crawl4ai`` package and its browser setup to be installed.

    Args:
        url: The full URL of the page to fetch.

    Returns:
        Clean Markdown content, or an actionable setup/error message.
    """
    result = await crawl4ai_fetch(url)

    from arachne.runtime.search_memory import record_search

    record_search("crawl4ai_fetch_async", url, result)
    return result
