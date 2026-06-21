from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arachne.tools.web.browser_search import browser_search_async
from arachne.tools.web.browser_visit import browser_visit_async
from arachne.tools.web.crawl4ai_fetch import _extract_markdown, crawl4ai_fetch, crawl4ai_fetch_async
from arachne.tools.web.deep_research import deep_research_async


@pytest.fixture
def mock_playwright_context():
    """Mock the entire playwright async_api context structure."""
    with patch("playwright.async_api.async_playwright") as mock_pw:
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = "Mocked page content."
        mock_page.query_selector_all.return_value = []
        mock_page.inner_text.return_value = "Mocked Text"

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        pw_context = MagicMock()
        pw_context.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw.return_value.__aenter__.return_value = pw_context
        yield mock_page


@pytest.mark.asyncio
async def test_browser_visit_single_url(mock_playwright_context):
    """Test visiting a single URL."""
    # Call underlying function
    func = browser_visit_async.func if hasattr(browser_visit_async, "func") else browser_visit_async
    result = await func("https://example.com")
    assert "Mocked page content." in result


@pytest.mark.asyncio
async def test_browser_search_logic(mock_playwright_context):
    """Test the browser search logic (redirected from google_search)."""
    # mock_page.query_selector_all is already mocked in fixture
    # We want it to return some links
    mock_link = AsyncMock()
    mock_link.get_attribute.return_value = "https://found.com"
    mock_link.inner_text.return_value = "Found Title"
    mock_playwright_context.query_selector_all.return_value = [mock_link]

    result = await browser_search_async("test query")
    assert "Found Title" in result
    assert "https://found.com" in result


@pytest.mark.asyncio
async def test_deep_research_basic_mock():
    """Test deep_research_async initialization and agent run (mocked)."""
    mock_history = MagicMock()
    mock_history.final_result.return_value = "Research Success"

    with (
        patch("arachne.tools.web.deep_research.Agent") as mock_agent,
        patch("arachne.tools.web.deep_research.ChatOpenAI"),
        patch("arachne.tools.web.deep_research.get_settings") as mock_settings_cls,
    ):
        # Setup settings mock to have api keys
        mock_settings = MagicMock()
        mock_settings.llm_model = "test-model"
        mock_settings.llm_api_key.get_secret_value.return_value = "test-key"
        mock_settings.browser_llm_model = None
        mock_settings_cls.return_value = mock_settings

        mock_agent_instance = mock_agent.return_value
        mock_agent_instance.run = AsyncMock(return_value=mock_history)

        func = deep_research_async.func if hasattr(deep_research_async, "func") else deep_research_async
        result = await func(task="Find something")
        assert "Research Success" in result


@pytest.mark.asyncio
async def test_browser_visit_timeout(mock_playwright_context):
    """Test handling of page load timeouts."""
    mock_playwright_context.goto.side_effect = Exception("Timeout 20000ms exceeded.")
    func = browser_visit_async.func if hasattr(browser_visit_async, "func") else browser_visit_async
    result = await func("https://slow.com")
    assert "Failed to load https://slow.com" in result


@pytest.mark.asyncio
async def test_crawl4ai_fetch_missing_dependency():
    """Crawl4AI tool should fail softly when optional dependency is absent."""
    with patch.dict("sys.modules", {"crawl4ai": None}):
        result = await crawl4ai_fetch("https://example.com")

    assert "Crawl4AI is not installed" in result
    assert "uv sync --extra crawl" in result


@pytest.mark.asyncio
async def test_crawl4ai_fetch_rejects_non_web_urls():
    """Crawl4AI tool should not expose local-file crawling to graph nodes."""
    result = await crawl4ai_fetch("file:///etc/passwd")

    assert result == "Crawl4AI fetch only supports absolute http:// or https:// URLs."


def test_crawl4ai_extracts_current_markdown_result_shape():
    """Crawl4AI 0.8.x can expose markdown as an object with fit/raw fields."""
    result = SimpleNamespace(
        markdown=SimpleNamespace(
            fit_markdown="## Fit Markdown",
            raw_markdown="## Raw Markdown",
        )
    )

    assert _extract_markdown(result) == "## Fit Markdown"


@pytest.mark.asyncio
async def test_crawl4ai_fetch_reports_crawler_exceptions():
    """Crawler runtime failures should be returned as agent-readable text."""
    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(side_effect=RuntimeError("browser crashed"))
    mock_crawler.__aenter__.return_value = mock_crawler
    mock_crawler.__aexit__.return_value = None

    fake_crawl4ai = SimpleNamespace(AsyncWebCrawler=MagicMock(return_value=mock_crawler))

    with patch.dict("sys.modules", {"crawl4ai": fake_crawl4ai}):
        result = await crawl4ai_fetch("https://example.com")

    assert result == "Crawl4AI failed to fetch https://example.com: browser crashed"


@pytest.mark.asyncio
async def test_crawl4ai_fetch_reports_unsuccessful_extraction():
    """Crawl4AI error messages should be surfaced when no Markdown is available."""
    mock_result = SimpleNamespace(markdown="", success=False, error_message="blocked by robots")

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=mock_result)
    mock_crawler.__aenter__.return_value = mock_crawler
    mock_crawler.__aexit__.return_value = None

    fake_crawl4ai = SimpleNamespace(AsyncWebCrawler=MagicMock(return_value=mock_crawler))

    with patch.dict("sys.modules", {"crawl4ai": fake_crawl4ai}):
        result = await crawl4ai_fetch("https://example.com")

    assert result == "Crawl4AI could not extract readable content from https://example.com: blocked by robots"


@pytest.mark.asyncio
async def test_crawl4ai_fetch_success_records_markdown():
    """Crawl4AI result markdown is returned and truncated through the tool wrapper."""
    mock_result = MagicMock()
    mock_result.markdown = "## Example\n\nContent"

    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=mock_result)
    mock_crawler.__aenter__.return_value = mock_crawler
    mock_crawler.__aexit__.return_value = None

    fake_crawl4ai = SimpleNamespace(AsyncWebCrawler=MagicMock(return_value=mock_crawler))

    with (
        patch.dict("sys.modules", {"crawl4ai": fake_crawl4ai}),
        patch("arachne.runtime.search_memory.record_search") as mock_record,
    ):
        func = crawl4ai_fetch_async.func if hasattr(crawl4ai_fetch_async, "func") else crawl4ai_fetch_async
        result = await func("https://example.com")

    assert result == "## Example\n\nContent"
    mock_record.assert_called_once_with("crawl4ai_fetch_async", "https://example.com", result)
