from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from pydantic import SecretStr

from arachne.tools.web.deep_research import deep_research_async


@pytest.mark.asyncio
async def test_deep_research_uses_browser_settings():
    """Verify that deep_research_async uses browser-specific settings if provided."""
    mock_settings = MagicMock()
    mock_settings.llm_model = "main-model"
    mock_settings.llm_api_key = SecretStr("main-key")
    mock_settings.llm_base_url = "https://main.api"
    mock_settings.browser_llm_model = "browser-model"
    mock_settings.browser_llm_api_key = SecretStr("browser-key")
    mock_settings.browser_llm_base_url = "https://browser.api"
    mock_settings.browser_llm_fallback_model = None
    mock_settings.langfuse.enabled = False

    mock_history = MagicMock()
    mock_history.final_result.return_value = "Success"

    func_to_test = deep_research_async.func if hasattr(deep_research_async, "func") else deep_research_async

    with (
        # Patch Settings where deep_research imports it
        patch("arachne.tools.web.deep_research.Settings", return_value=mock_settings),
        patch("arachne.tools.web.deep_research.ChatOpenAI") as mock_chat,
        patch("arachne.tools.web.deep_research.Agent") as mock_agent,
        patch("arachne.tools.web.deep_research.Browser"),
    ):
        mock_agent_instance = mock_agent.return_value
        mock_agent_instance.run = AsyncMock(return_value=mock_history)

        await func_to_test(task="test task")

    # The function creates two ChatOpenAI instances: primary + fallback.
    # Both should use the browser settings when available.
    expected_call = call(
        model="browser-model",
        api_key="browser-key",
        base_url="https://browser.api",
        temperature=0.0,
        seed=42,
    )
    assert expected_call in mock_chat.call_args_list, (
        f"Expected ChatOpenAI to be called with browser settings. Got: {mock_chat.call_args_list}"
    )


@pytest.mark.asyncio
async def test_deep_research_fallback_to_main_settings():
    """Verify that deep_research_async falls back to main settings if browser settings are None."""
    mock_settings = MagicMock()
    mock_settings.llm_model = "main-model"
    mock_settings.llm_api_key = SecretStr("main-key")
    mock_settings.llm_base_url = "https://main.api"
    mock_settings.browser_llm_model = None
    mock_settings.browser_llm_api_key = None
    mock_settings.browser_llm_base_url = None
    mock_settings.browser_llm_fallback_model = None
    mock_settings.langfuse.enabled = False

    mock_history = MagicMock()
    mock_history.final_result.return_value = "Success"

    func_to_test = deep_research_async.func if hasattr(deep_research_async, "func") else deep_research_async

    with (
        patch("arachne.tools.web.deep_research.Settings", return_value=mock_settings),
        patch("arachne.tools.web.deep_research.ChatOpenAI") as mock_chat,
        patch("arachne.tools.web.deep_research.Agent") as mock_agent,
        patch("arachne.tools.web.deep_research.Browser"),
    ):
        mock_agent_instance = mock_agent.return_value
        mock_agent_instance.run = AsyncMock(return_value=mock_history)

        await func_to_test(task="test task")

    # Both primary and fallback should use main settings when browser settings are absent.
    expected_call = call(
        model="main-model",
        api_key="main-key",
        base_url="https://main.api",
        temperature=0.0,
        seed=42,
    )
    assert expected_call in mock_chat.call_args_list, (
        f"Expected ChatOpenAI to be called with main settings. Got: {mock_chat.call_args_list}"
    )
