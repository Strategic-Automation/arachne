# MCP Integration: Model Context Protocol

Arachne leverages the [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol) to provide agents with standardized access to a rich ecosystem of tools.

## Key Benefits

- **Dynamic Discovery**: Agents can discover and bind tools from multiple MCP servers at runtime.
- **Tool Standard**: Unified interface for filesystem, database, browser, and custom integrations.
- **Context Management**: Prevents context window pollution by using pointers for large tool outputs.

## How it Works

1. **Server Registration**: MCP servers are defined in the `config.py` as `mcp_servers`.
2. **Provisioning**: During the weave phase, nodes are assigned to specific servers.
3. **Execution**: The `MCPClientManager` handles the connection, discovery, and conversion of MCP tools to `dspy.Tool` format.

For details on connecting to new servers, see [MCP Setup](../guides/mcp-setup.md).
