# MCP Setup: Connecting New Servers

Arachne can connect to any MCP-compatible server to expand its capabilities.

## Configuration

MCP servers are defined in `src/arachne/config.py` under the `mcp_servers` section of the `Settings` class.

### Adding a Server

1. **Edit `config.py`**:
   Add your server configuration to the `mcp_servers` list.
   ```python
   mcp_servers = [
       {
           "name": "filesystem",
           "command": "npx",
           "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
       },
       {
           "name": "sqlite",
           "command": "uvx",
           "args": ["mcp-server-sqlite", "--db-path", "/path/to/database.db"],
       }
   ]
   ```

2. **Verify Connectivity**:
   When you run `arachne`, the `MCPClientManager` will attempt to connect to the configured servers and discover their tools.

### Official Servers

You can find a list of official and community-maintained MCP servers at the [MCP Specification Repository](https://github.com/modelcontextprotocol/servers).
