"""ToolResolver -- unified tool/MCP resolution for graph nodes.

Consolidates built-in tool lookup (via resolve_tool) and MCP server
tool discovery into a single reusable class with security validation.
"""

import dspy

from arachne.config import Settings
from arachne.runtime.mcp_manager import MCPManager
from arachne.tools import resolve_tool

# Security: Only these binaries may be spawned as MCP server processes.
ALLOWED_MCP_COMMANDS = {"npx", "python3", "uvx"}


class ToolResolver:
    """Resolves tool names and MCP server declarations to dspy.Tool objects."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def resolve(self, tool_names: list[str], mcp_servers: list[str] | None = None) -> list[dspy.Tool]:
        """Resolve built-in tools and MCP tools into a flat list of dspy.Tool."""
        tools: list[dspy.Tool] = []

        for name in tool_names:
            wrapped = resolve_tool(name, settings=self.settings)
            if wrapped is not None:
                tools.append(wrapped)

        if mcp_servers:
            tools.extend(await self._resolve_mcp(mcp_servers))

        return tools

    # ------------------------------------------------------------------
    # MCP resolution
    # ------------------------------------------------------------------

    async def _resolve_mcp(self, server_names: list[str]) -> list[dspy.Tool]:
        """Validate and connect to MCP servers, returning their tools."""
        self._validate_mcp_commands(server_names)

        mgr = await MCPManager.instance()
        await mgr.ensure_connected()
        return mgr.get_tools(server_names)

    def _validate_mcp_commands(self, server_names: list[str]) -> None:
        """Raise ValueError if any requested MCP server uses a disallowed command."""
        invalid = []
        for server_name, server_cfg in self.settings.mcp.servers.items():
            if server_name in server_names and server_cfg.command not in ALLOWED_MCP_COMMANDS:
                invalid.append(f"{server_name}: {server_cfg.command}")

        if invalid:
            raise ValueError(
                f"MCP commands not in allowed list: {', '.join(invalid)}. "
                f"Allowed commands: {', '.join(sorted(ALLOWED_MCP_COMMANDS))}"
            )
