"""Stealth browser search functionality."""

import asyncio
import random

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


async def _extract_google_links(page) -> list[str]:
    """Extract and decode Google search result links (async)."""
    from urllib.parse import parse_qs, unquote

    results: list[str] = []
    try:
        elements = await page.query_selector_all("a[jsname]")
        if not elements:
            elements = await page.query_selector_all(".g a")
        for el in elements[:5]:
            href = await el.get_attribute("href") or ""
            if href.startswith("/url?") and "q=" in href:
                href = unquote(parse_qs(href.split("?")[1])["q"][0])
            title = await el.inner_text()
            if title and href.startswith("http"):
                results.append(f"{title}\n{href}")
    except Exception:
        pass
    return results


async def _search_google_async(pw, query: str) -> str:
    """Search Google with stealth browser and return results."""
    ua = random.choice(_REALISTIC_UAS)
    vp = random.choice(_VIEWPORTS)

    browser = await pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
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
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(random.uniform(800, 1500))
        results = await _extract_google_links(page)
        if not results:
            # Use active session path if available, otherwise fallback to scratch
            from arachne.sessions.manager import active_session_path

            session_dir = active_session_path.get()
            if session_dir:
                diag_dir = session_dir / "diagnostics"
                diag_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = diag_dir / "google_fail.png"
            else:
                screenshot_path = "scratch/google_fail.png"

            await page.screenshot(path=str(screenshot_path))
            # Also check for common "blocked" strings
            content = await page.content()
            if "captcha" in content.lower() or "unusual traffic" in content.lower():
                return f"### Search Blocked\nGoogle detected unusual traffic/CAPTCHA for '{query}'. Consider using DDG or an API key."

        # Format results to Markdown
        body = "\n\n".join(results) if results else "No results found (Structure may have changed or blocked)."
        return f"## Query: {query}\n{body}"
    except Exception as e:
        return f"### Search Error\nSearch failed for '{query}': {e}"
    finally:
        await browser.close()


async def browser_search_async(queries: str) -> str:
    """Search Google in parallel using stealth browsers.

    Args:
        queries: Comma-separated search queries.

    Returns:
        Combined search results.
    """
    from playwright.async_api import async_playwright
    from rich.console import Console

    console = Console()
    query_list = [q.strip() for q in queries.split(",") if q.strip()]

    for q in query_list:
        console.print(f'    [cyan]🌐 Browser Search for:[/cyan] [bold]"{q}"[/bold]')

    async with async_playwright() as pw:
        tasks = [_search_google_async(pw, q) for q in query_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    parts: list[str] = []
    for r in results:
        if isinstance(r, Exception):
            parts.append(f"### Search Error\n{r}")
        else:
            parts.append(r)
    return "\n\n".join(parts)
