"""End-to-end MCP integration test for Arachne.

Requires the `mcp` package. Run with: uv run pytest -k mcp
"""

import pytest

# Skip if mcp not installed (it's in .venv but not system)
pytest.importorskip("mcp")

import asyncio
import os
from contextlib import AsyncExitStack

import dspy

# Setup env before imports
for k in ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASE_URL"]:
    os.environ[k] = ""


# MCP server script for testing
MCP_SERVER_SCRIPT = '''
from mcp.server.fastmcp import FastMCP
mcp = FastMCP(name="MathServer")
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b
@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b
if __name__ == "__main__":
    mcp.run()
'''


@pytest.mark.asyncio
async def test_mcp_tool_discovery_and_call():
    """Test MCP tool discovery, conversion to dspy.Tool, and execution."""
    import platform
    if platform.system() == "Windows":
        pytest.skip("MCP stdio transport not supported on Windows")

    import tempfile
    from pathlib import Path

    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    with dspy.context(allow_tool_async_sync_conversion=True):
        with tempfile.NamedTemporaryFile(suffix="_mcp_server.py", delete=False, mode="w") as f:
            f.write(MCP_SERVER_SCRIPT)
            server_path = f.name

        exit_stack = AsyncExitStack()
        params = StdioServerParameters(command="python3", args=[server_path])
        transports = await exit_stack.enter_async_context(stdio_client(params))
        read, write = transports
        session = ClientSession(read, write)
        await exit_stack.enter_async_context(session)
        await session.initialize()

        # Discover tools
        tools_resp = await session.list_tools()
        assert len(tools_resp.tools) == 2
        names = {t.name for t in tools_resp.tools}
        assert "add" in names
        assert "multiply" in names

        # Convert to DSPy tools
        dspy_tools = [dspy.Tool.from_mcp_tool(session, t) for t in tools_resp.tools]
        assert len(dspy_tools) == 2

        # Test add tool
        result = await dspy_tools[0].acall(a=42, b=58)
        assert "100" in str(result)

        # Test multiply tool
        result2 = await dspy_tools[1].acall(a=6, b=7)
        assert "42" in str(result2)

        # Cleanup
        await exit_stack.aclose()
        Path(server_path).unlink(missing_ok=True)
        print("All MCP integration tests passed!")


if __name__ == "__main__":
    asyncio.run(test_mcp_tool_discovery_and_call())
