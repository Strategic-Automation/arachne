"""MCP Server Manager -- discovers, connects, and converts MCP tools to dspy.Tool."""

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

import dspy

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server connection."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


class MCPManager:
    """Singleton MCP server manager."""

    _instance = None
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._exit_stack = AsyncExitStack()
        self._sessions: dict = {}
        self._dspy_tools: dict[str, list[dspy.Tool]] = {}
        self._initialized = False

    @classmethod
    async def instance(cls):
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, command: str, args: list[str] | None = None, env: dict | None = None) -> None:
        self._servers[name] = MCPServerConfig(name=name, command=command, args=args or [], env=env)

    async def ensure_connected(self) -> None:
        if self._initialized:
            return
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            logger.warning("mcp optional package not installed")
            return
        for name, cfg in self._servers.items():
            try:
                params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env)
                read, write = await self._exit_stack.enter_async_context(stdio_client(params))
                session = ClientSession(read, write)
                await self._exit_stack.enter_async_context(session)
                await session.initialize()
                resp = await session.list_tools()

                tools = []
                from arachne.tools.spillover import with_spillover

                for t in resp.tools:
                    raw_tool = dspy.Tool.from_mcp_tool(session, t)
                    # raw_tool.func is the callable that DSPy invokes under the hood
                    # We wrap it with spillover to protect the context window
                    validated_fn = with_spillover(t.name, raw_tool.func)

                    # Recreate the dspy.Tool with the wrapped func, preserving name and desc
                    wrapped_tool = dspy.Tool(
                        func=validated_fn, name=raw_tool.name, desc=raw_tool.desc, args=raw_tool.args
                    )
                    tools.append(wrapped_tool)

                self._sessions[name] = session
                self._dspy_tools[name] = tools
                logger.info("MCP '%s' connected: %d tools", name, len(tools))
            except Exception as e:
                logger.error("MCP '%s' failed: %s", name, e)
        self._initialized = True

    def get_tools(self, server_names: list[str]) -> list[dspy.Tool]:
        tools = []
        for n in server_names:
            tools.extend(self._dspy_tools.get(n, []))
        return tools

    async def close_all(self) -> None:
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._dspy_tools.clear()
        self._initialized = False
