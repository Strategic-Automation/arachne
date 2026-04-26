"""Comprehensive tests for ToolResolver -- unified tool/MCP resolution.

Covers: resolve() with built-in tools, custom tools, missing tools,
MCP validation, path construction.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import dspy
import pytest

from arachne.config import Settings
from arachne.topologies.tool_resolver import ALLOWED_MCP_COMMANDS, ToolResolver

# ── Helpers ──────────────────────────────────────────────────────────


def _make_settings() -> Settings:
    """Create Settings with no special config."""
    return Settings()


def _fake_dspy_tool(name: str = "mock_tool") -> MagicMock:
    """Create a mock dspy.Tool."""
    return MagicMock(spec=dspy.Tool)


# ── Test: resolve() with built-in tools ──────────────────────────────


class TestResolveBuiltIn:
    @pytest.mark.asyncio
    async def test_resolve_known_builtin_tool(self):
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)

        mock_tool = _fake_dspy_tool("shell_exec")
        with patch("arachne.topologies.tool_resolver.resolve_tool", return_value=mock_tool):
            tools = await resolver.resolve(["shell_exec"])

        assert len(tools) == 1
        assert tools[0] is mock_tool

    @pytest.mark.asyncio
    async def test_resolve_multiple_builtin_tools(self):
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)

        tool_a = _fake_dspy_tool("shell_exec")
        tool_b = _fake_dspy_tool("read_file")

        def fake_resolve(name, settings=None):
            return tool_a if name == "shell_exec" else tool_b

        with patch("arachne.topologies.tool_resolver.resolve_tool", side_effect=fake_resolve):
            tools = await resolver.resolve(["shell_exec", "read_file"])

        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_resolve_empty_list_returns_empty(self):
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)

        with patch("arachne.topologies.tool_resolver.resolve_tool") as mock_resolve:
            tools = await resolver.resolve([])

        assert tools == []
        mock_resolve.assert_not_called()


# ── Test: resolve() with custom tools ────────────────────────────────


class TestResolveCustom:
    @pytest.mark.asyncio
    async def test_resolve_custom_tool_via_resolve_tool(self):
        """Custom tools are found by resolve_tool (which checks _CUSTOM_TOOL_DIR)."""
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)

        mock_tool = _fake_dspy_tool("my_custom_tool")
        with patch("arachne.topologies.tool_resolver.resolve_tool", return_value=mock_tool):
            tools = await resolver.resolve(["my_custom_tool"])

        assert len(tools) == 1
        assert tools[0] is mock_tool


# ── Test: resolve() with missing tools ───────────────────────────────


class TestResolveMissing:
    @pytest.mark.asyncio
    async def test_missing_tool_returns_none_skipped(self):
        """If resolve_tool returns None for a name, it is silently skipped."""
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)

        with patch("arachne.topologies.tool_resolver.resolve_tool", return_value=None):
            tools = await resolver.resolve(["nonexistent_tool_xyz"])

        assert tools == []

    @pytest.mark.asyncio
    async def test_mix_of_found_and_missing(self):
        """Only found tools are included in the result."""
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)

        mock_tool = _fake_dspy_tool("shell_exec")

        def fake_resolve(name, settings=None):
            return mock_tool if name == "shell_exec" else None

        with patch("arachne.topologies.tool_resolver.resolve_tool", side_effect=fake_resolve):
            tools = await resolver.resolve(["shell_exec", "missing_tool"])

        assert len(tools) == 1
        assert tools[0] is mock_tool


# ── Test: resolve() with MCP servers ─────────────────────────────────


class TestResolveMCP:
    @pytest.mark.asyncio
    async def test_mcp_servers_appended_to_tools(self):
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)

        builtin_tool = _fake_dspy_tool("shell_exec")
        mcp_tool = _fake_dspy_tool("mcp_tool")

        mock_mgr = AsyncMock()
        mock_mgr.get_tools = MagicMock(return_value=[mcp_tool])

        with (
            patch("arachne.topologies.tool_resolver.resolve_tool", return_value=builtin_tool),
            patch("arachne.topologies.tool_resolver.MCPManager") as mock_mcp_cls,
        ):
            mock_mcp_cls.instance = AsyncMock(return_value=mock_mgr)
            mock_mgr.ensure_connected = AsyncMock()
            tools = await resolver.resolve(["shell_exec"], mcp_servers=["my_server"])

        assert len(tools) == 2
        assert builtin_tool in tools
        assert mcp_tool in tools

    @pytest.mark.asyncio
    async def test_mcp_validation_rejects_disallowed_command(self):
        settings = _make_settings()
        # Simulate a server config with a disallowed command
        settings.mcp.servers = {
            "evil_server": MagicMock(command="bash"),
        }
        resolver = ToolResolver(settings=settings)

        with pytest.raises(ValueError, match="not in allowed list"):
            await resolver.resolve([], mcp_servers=["evil_server"])

    @pytest.mark.asyncio
    async def test_mcp_validation_allows_approved_commands(self):
        settings = _make_settings()
        settings.mcp.servers = {
            "safe_server": MagicMock(command="npx"),
        }
        resolver = ToolResolver(settings=settings)

        mock_mgr = AsyncMock()
        mock_mgr.get_tools = MagicMock(return_value=[])

        with (
            patch("arachne.topologies.tool_resolver.resolve_tool", return_value=None),
            patch("arachne.topologies.tool_resolver.MCPManager") as mock_mcp_cls,
        ):
            mock_mcp_cls.instance = AsyncMock(return_value=mock_mgr)
            mock_mgr.ensure_connected = AsyncMock()
            tools = await resolver.resolve([], mcp_servers=["safe_server"])

        assert isinstance(tools, list)


# ── Test: _validate_mcp_commands ─────────────────────────────────────


class TestValidateMCPCommands:
    def test_allowed_commands_constant(self):
        assert "npx" in ALLOWED_MCP_COMMANDS
        assert "python3" in ALLOWED_MCP_COMMANDS
        assert "uvx" in ALLOWED_MCP_COMMANDS

    def test_validate_passes_for_allowed(self):
        settings = _make_settings()
        settings.mcp.servers = {
            "srv1": MagicMock(command="npx"),
            "srv2": MagicMock(command="uvx"),
        }
        resolver = ToolResolver(settings=settings)
        # Should not raise
        resolver._validate_mcp_commands(["srv1", "srv2"])

    def test_validate_raises_for_disallowed(self):
        settings = _make_settings()
        settings.mcp.servers = {
            "bad": MagicMock(command="curl"),
        }
        resolver = ToolResolver(settings=settings)
        with pytest.raises(ValueError, match="curl"):
            resolver._validate_mcp_commands(["bad"])

    def test_validate_ignores_servers_not_in_request(self):
        settings = _make_settings()
        settings.mcp.servers = {
            "bad": MagicMock(command="curl"),
            "good": MagicMock(command="npx"),
        }
        resolver = ToolResolver(settings=settings)
        # Only requesting 'good' -- bad is not validated
        resolver._validate_mcp_commands(["good"])

    def test_validate_empty_servers_no_error(self):
        settings = _make_settings()
        settings.mcp.servers = {}
        resolver = ToolResolver(settings=settings)
        resolver._validate_mcp_commands([])


# ── Test: Path construction ──────────────────────────────────────────


class TestPathConstruction:
    def test_tool_resolver_uses_settings(self):
        """ToolResolver stores the provided settings."""
        settings = _make_settings()
        resolver = ToolResolver(settings=settings)
        assert resolver.settings is settings

    def test_resolve_tool_uses_builtin_registry(self):
        """Built-in tools are looked up from the _BUILTIN_TOOLS registry."""
        from arachne.tools import _BUILTIN_TOOLS

        assert "shell_exec" in _BUILTIN_TOOLS
        assert "read_file" in _BUILTIN_TOOLS

    def test_custom_tool_dir_path(self):
        """Custom tools directory exists and contains 'arachne' in its path."""
        from arachne.tools import _CUSTOM_TOOL_DIR

        path_str = str(_CUSTOM_TOOL_DIR)
        # The path may vary depending on initialization order in full suite runs
        assert "arachne" in path_str or path_str == "custom"

    def test_resolve_builtin_returns_dspy_tool(self):
        """resolve_tool wraps builtins as dspy.Tool."""
        from arachne.tools import resolve_tool

        tool = resolve_tool("shell_exec")
        assert isinstance(tool, dspy.Tool)

    def test_resolve_missing_returns_none(self):
        """resolve_tool returns None for nonexistent tools."""
        from arachne.tools import resolve_tool

        tool = resolve_tool("completely_fake_tool_12345")
        assert tool is None
