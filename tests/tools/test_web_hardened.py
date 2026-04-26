import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arachne.config import Settings
from arachne.tools.web.duckduckgo_search import duckduckgo_search_async
from arachne.tools.web.google_scraper import google_search_async
from arachne.tools.web.jina import jina_search_async


@pytest.mark.asyncio
async def test_jina_search_auth_failure():
    """Test Jina search returns meaningful error on 401."""
    # Mock Settings to have jina_api_key attribute
    mock_settings = MagicMock(spec=Settings)
    mock_settings.jina_api_key = None

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    # We need to mock the AsyncClient instance that is created by the context manager
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        patch("arachne.tools.web.jina.Settings", return_value=mock_settings),
    ):
        # The AsyncClient is used as: async with httpx.AsyncClient(...) as client:
        # So the __aenter__ of the return value of httpx.AsyncClient() should return the client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Call the underlying function
        func = jina_search_async.func if hasattr(jina_search_async, "func") else jina_search_async
        result = await func("test query")
        assert "Authentication Required (401)" in result


@pytest.mark.asyncio
async def test_google_search_uses_browser():
    """Test google_search_async correctly redirects to browser_search_async."""
    with patch("arachne.tools.web.google_scraper.browser_search_async") as mock_browser_search:
        mock_browser_search.return_value = "Browser Results"
        # Call the underlying function
        func = google_search_async.func if hasattr(google_search_async, "func") else google_search_async
        result = await func("test query")
        assert result == "Browser Results"
        mock_browser_search.assert_called_once_with(queries="test query")


@pytest.mark.asyncio
async def test_ddg_search_basic():
    """Test DuckDuckGo search doesn't crash."""
    try:
        # Call the underlying function
        func = duckduckgo_search_async.func if hasattr(duckduckgo_search_async, "func") else duckduckgo_search_async
        result = await func("test")
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"DDG search crashed: {e}")


if __name__ == "__main__":
    asyncio.run(test_jina_search_auth_failure())
    asyncio.run(test_google_search_uses_browser())
    print("Web tools basic hardening tests passed.")
