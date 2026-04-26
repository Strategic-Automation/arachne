from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arachne.tools.web.browser_search import browser_search_async
from arachne.tools.web.browser_visit import browser_visit_async
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
        patch("arachne.tools.web.deep_research.Settings") as mock_settings_cls,
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
