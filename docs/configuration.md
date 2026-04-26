# Configuration Reference

Arachne uses Pydantic Settings for centralized configuration via environment variables or a `.env` file.

## Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ARACHNE_LOG_LEVEL` | Logging verbosity | `INFO` |

## LLM Configuration

Configure your primary LLM via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ARACHNE_LLM_BACKEND` | LLM provider | `openrouter` |
| `ARACHNE_LLM_MODEL` | Model name | `qwen/qwen3.6-plus:free` |
| `ARACHNE_LLM_API_KEY` | API key | (empty) |
| `ARACHNE_LLM_BASE_URL` | API base URL | `https://openrouter.ai/api/v1/` |
| `ARACHNE_LLM_TEMPERATURE` | Sampling temperature | `0.7` |
| `ARACHNE_LLM_MAX_TOKENS` | Max output tokens | `4096` |
| `ARACHNE_LLM_CONTEXT_LIMIT` | Context window limit | `131072` |
| `ARACHNE_LLM_CACHE` | Enable DSPy response cache | `false` |

## Cost & Safety

| Variable | Description | Default |
|----------|-------------|---------|
| `ARACHNE_COST_DEFAULT_MAX_USD` | Max cost per run (USD) | `10.0` |
| `ARACHNE_COST_DEFAULT_MAX_TOKENS` | Max tokens per run | `500000` |
| `ARACHNE_COST_HARD_STOP_ENABLED` | Hard stop on cost limit | `true` |

## MCP Servers

Configure Model Context Protocol servers in your `.env` file:

```bash
ARACHNE_MCP_SERVERS='{"filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]}}'
```

## Directory Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ARACHNE_SESSION_DIRECTORY` | Session storage | `~/.local/share/arachne/sessions` |
| `ARACHNE_CHECKPOINT_DIRECTORY` | Checkpoint storage | `~/.local/share/arachne/checkpoints` |
| `ARACHNE_SKILL_DIRECTORY` | Skills storage | `~/.local/share/arachne/skills` |
| `ARACHNE_LOG_DIRECTORY` | Log storage | `~/.local/share/arachne/logs` |