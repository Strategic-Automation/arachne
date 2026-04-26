"""Stealth browser visit functionality."""

import asyncio
import contextlib
import random

import dspy

MAX_CHARS = 8000

_REALISTIC_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
]

_STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.chrome = {runtime: {}, loadTimes: () => ({}), connectionInfo: "4g"};
    Object.defineProperty(navigator, 'languages', {get: () => ['en-GB', 'en-US', 'en']});
    Object.defineProperty(navigator, 'plugins', {get: () => [
        {description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
        {description: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
    ]});
    navigator.permissions.query = async (q) => ({state: 'prompt', onchange: null});
}
"""


def _clean_text(text: str) -> str:
    """Remove excess whitespace."""
    import re

    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    text = re.sub(r" {2,}", " ", text)
    return text[:MAX_CHARS]


async def _fetch_page_async(pw, url: str) -> tuple[str, str]:
    """Fetch a single page with a stealthy browser."""
    ua = random.choice(_REALISTIC_UAS)
    vp = random.choice(_VIEWPORTS)

    browser = await pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--disable-infobars", "--no-first-run"],
    )
    context = await browser.new_context(
        viewport=vp,
        user_agent=ua,
        locale="en-GB",
        timezone_id="Europe/London",
    )
    await context.add_init_script(_STEALTH_JS)
    page = await context.new_page()

    try:
        await page.goto(url.strip(), wait_until="domcontentloaded", timeout=20000)
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=5000)
        await page.wait_for_timeout(random.randint(400, 1200))

        text = await page.evaluate("""() => {
            document.querySelectorAll('script, style, noscript, iframe, svg').forEach(e => e.remove());
            return document.body.innerText;
        }""")
        return url.strip(), _clean_text(text) if text else f"No visible text at {url}"
    except Exception as exc:
        return url.strip(), f"Failed to load {url}: {exc}"
    finally:
        await browser.close()


@dspy.Tool
async def browser_visit_async(urls: str, **_kwargs) -> str:
    """Visit URLs in parallel using stealth browsers.

    Args:
        urls: Comma-separated URLs to visit.

    Returns:
        Combined text content from all pages.
    """
    from playwright.async_api import async_playwright

    url_list = [u.strip() for u in urls.split(",") if u.strip()]
    if len(url_list) == 1:
        async with async_playwright() as pw:
            _, text = await _fetch_page_async(pw, url_list[0])
            result_text = text
    else:
        async with async_playwright() as pw:
            tasks = [_fetch_page_async(pw, u) for u in url_list]
            visit_results = await asyncio.gather(*tasks, return_exceptions=True)

        parts: list[str] = []
        for result in visit_results:
            if isinstance(result, Exception):
                parts.append(f"Error: {result}")
            else:
                u, t = result
                parts.append(f"--- {u} ---\n{t}")
        result_text = "  \n\n".join(parts)

    # Persist visited content to session memory for healing/retry recovery
    from arachne.runtime.search_memory import record_search

    record_search("browser_visit_async", urls, result_text)
    return result_text
