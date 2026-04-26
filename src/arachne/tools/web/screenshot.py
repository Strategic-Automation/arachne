import dspy


@dspy.Tool
async def take_screenshot_async(url: str, full_page: bool = False, **_kwargs) -> str:
    """Take a screenshot of a webpage and return the path to the saved image.

    Args:
        url: The URL to visit and screenshot.
        full_page: Whether to screenshot the entire scrollable page (default: False).

    Returns:
        A message containing the path to the saved screenshot, or an error.
    """
    import os
    import tempfile
    import time

    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled", "--no-first-run"]
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            await page.goto(url.strip(), wait_until="domcontentloaded", timeout=20000)
            # Wait a moment for dynamic content and animations to settle
            await page.wait_for_timeout(2000)

            # Create a temp file path for the screenshot
            temp_dir = tempfile.gettempdir()
            timestamp = int(time.time())
            safe_url = "".join([c if c.isalnum() else "_" for c in url])[:30]
            screenshot_path = os.path.join(temp_dir, f"screenshot_{safe_url}_{timestamp}.png")

            await page.screenshot(path=screenshot_path, full_page=full_page)
            await browser.close()

            return f"Screenshot successfully saved to: {screenshot_path}"
    except Exception as e:
        return f"Failed to take screenshot of {url}: {e}"
