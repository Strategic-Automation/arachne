# Troubleshooting Guide

Common issues and how to resolve them.

## LLM Configuration Errors

### "API key not found" or "Invalid API key"

Ensure your `.env` file is properly configured:
```bash
ARACHNE_LLM_API_KEY=your_api_key_here
ARACHNE_LLM_BACKEND=openrouter  # Options: openrouter, openai, anthropic
```

Verify the key works with your provider directly before troubleshooting Arachne.

### Model not found or invalid model

Check the model name matches the provider's format. For OpenRouter, use format like `qwen/qwen3.6-plus:free`. See [Configuration Reference](configuration.md) for defaults.

## MCP Connection Errors

### MCP server fails to start

1. **Check command is in PATH**: Ensure the MCP server command (e.g., `npx`, `python3`, `uvx`) is available in your system PATH.
```bash
which npx
which python3
```

2. **Verify ALLOWED_MCP_COMMANDS**: Check that your command is listed in `ALLOWED_MCP_COMMANDS` in `topologies/tool_resolver.py`.

3. **Test server manually**: Run the MCP server command directly to verify it works.
```bash
npx -y @modelcontextprotocol/server-filesystem /tmp
```

### MCP tools not available

Ensure the MCP server configuration matches the format in your `.env` file or `config.py`:
```bash
ARACHNE_MCP_SERVERS='{"filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]}}'
```

## Missing Tools

### Built-in tools not discovered

Run `uv run arachne --list-tools` to verify that your built-in and custom tools are discovered correctly.

### Custom tools not loading

Check that custom tools follow the expected structure in `~/.local/share/arachne/tools/custom/`.

## Execution Errors

### Session fails immediately

1. Check the goal is specific and actionable
2. Review session logs in `~/.local/share/arachne/sessions/<session_id>/logs/`
3. Try with `--max-retries 0` to see the raw error

### Cost limit exceeded

Reduce the scope of your goal or adjust limits in `.env`:
```bash
ARACHNE_COST_DEFAULT_MAX_USD=5.0
ARACHNE_COST_DEFAULT_MAX_TOKENS=100000
```

## Performance Issues

### Slow execution

- Use a faster LLM model
- Reduce graph complexity by making goals more focused
- Check network latency to LLM provider

### Context window overflow

Use the pointer pattern for large outputs. Ensure `tools/spillover.py` is working correctly for tool outputs > 30KB.

## Getting Help

- Check [GitHub Issues](https://github.com/Strategic-Automation/arachne/issues) for known bugs
- Review [Architecture Documentation](explanation/architecture.md) for system details
- Enable Langfuse logging to trace execution