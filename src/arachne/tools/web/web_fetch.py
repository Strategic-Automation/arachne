"""Fetch full webpage content — local httpx first, Jina Reader as fallback."""

from __future__ import annotations

import re

import dspy
import httpx

MAX_CHARS = 8000

# Realistic browser headers to avoid bot-detection on direct fetches
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}


async def _fetch_via_httpx(url: str, client: httpx.AsyncClient) -> str:
    """Fetch raw HTML with realistic browser fingerprints."""
    resp = await client.get(url.strip(), headers=_BROWSER_HEADERS, timeout=15.0, follow_redirects=True)
    return resp.text


def _extract_text(html: str) -> str:
    """Extract readable text from HTML, trying multiple strategies."""
    # Strategy 1: html2text
    try:
        import html2text as h2t

        conv = h2t.HTML2Text()
        conv.ignore_links = False
        conv.ignore_images = True
        conv.body_width = 0
        return conv.handle(html).strip()
    except ImportError:
        pass

    # Strategy 2: readability-lxml
    try:
        from readability import Document  # type: ignore[import-untyped]

        doc = Document(html)
        text = re.sub(r"<[^>]+>", " ", doc.summary())
        return text.strip()
    except ImportError:
        pass

    # Strategy 3: dumb regex strip
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<[^>]+>", " ", text).strip()


async def _fetch_via_jina(url: str, client: httpx.AsyncClient) -> str | None:
    """Try Jina Reader API. Returns clean text or None on failure."""
    try:
        resp = await client.get(
            f"https://r.jina.ai/{url.strip()}",
            headers={"Accept": "text/plain", "X-Return-Format": "text", "X-No-Cache": "true"},
            timeout=25.0,
            follow_redirects=True,
        )
        if resp.status_code != 200 or not resp.text.strip() or resp.text.startswith("Error"):
            return None
        lines = resp.text.strip().splitlines()
        clean = [line for line in lines if not line.startswith("[LINK]") and not line.startswith("[BUTTON]")]
        text = " ".join(clean).strip()
        return text[:MAX_CHARS] if len(text) > 200 else None
    except Exception:
        return None


async def web_fetch(url: str, client: httpx.AsyncClient | None = None) -> str:
    """Internal helper — fetch full page content. Use ``web_fetch_async`` as the agent tool."""
    _own_client = client is None
    if _own_client:
        client = httpx.AsyncClient()

    try:
        # Strategy 1: Local fetch + text extraction (fast, free)
        try:
            html = await _fetch_via_httpx(url, client)
            text = _extract_text(html).strip()[:MAX_CHARS]
            if len(text) > 200:
                return text
        except Exception:
            pass

        # Strategy 2: Jina Reader (handles JS-heavy / bot-protected pages)
        content = await _fetch_via_jina(url, client)
        if content:
            return content

        return f"No readable content found at {url}"

    finally:
        if _own_client:
            await client.aclose()


@dspy.Tool
async def web_fetch_async(url: str, **_kwargs) -> str:
    """Fetch the complete text content of a specific webpage URL.

    Use this AFTER a search tool has returned results to read the full content of a
    page that looks relevant. Do NOT call this on every search result — only fetch
    pages that are directly useful for the current research task.

    Strategy: local httpx (fast) → Jina Reader fallback (for JS-heavy / paywalled pages).

    Args:
        url: The full URL of the page to fetch (e.g. ``https://example.com/about``).

    Returns:
        The readable text content of the page, up to 8000 characters.
    """
    result = await web_fetch(url)

    # Persist fetched content to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("web_fetch_async", url, result)

    return result
