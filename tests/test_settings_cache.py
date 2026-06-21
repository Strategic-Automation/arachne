from arachne import config


def test_get_settings_returns_isolated_nested_models() -> None:
    config._get_settings_cached.cache_clear()

    first = config.get_settings()
    first.mcp.servers["demo"] = {"command": "run"}

    second = config.get_settings()

    assert second.mcp.servers == {}
    assert first.mcp is not second.mcp
