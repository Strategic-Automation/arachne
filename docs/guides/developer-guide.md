---
type: guide
description: How to set up, develop, test, and contribute to Arachne
---

# Developer Guide

This guide covers working with the Arachne project in Google Antigravity and agent-first IDEs.

## Repository Overview

| Directory | Description |
|-----------|-------------|
| `src/arachne/` | Main package code — runtime, tools, topologies |
| `tests/` | Unit and integration tests |
| `docs/` | Architecture docs, guides, articles |

## Initial Setup

```bash
# Clone and enter
cd ~/arachne

# Activate venv (if not already active)
source .venv/bin/activate

# Install dependencies
uv sync

# Run tests
uv run pytest

# Quickstart (interactive setup)
./quickstart.sh
```

## Agent-First Development

### Using Google Antigravity
Arachne is configured for Google Antigravity's agent-first workflow:
- **.agent/mcp_config.json** — MCP server definitions for the IDE
- **ROADMAP.md** — Prioritized task list

### How Agents Should Work This Codebase
1. **Read AGENTS.md first** — contains coding standards, conventions, and safety rules
2. **Read ROADMAP.md** — understand current priorities and known issues
3. **Read architecture docs** (`docs/explanation/architecture.md`) before modifying components
4. **Always branch** — create a feature branch before any changes
5. **Always test** — run `uv run pytest` before committing
6. **Always lint** — run `uv run ruff check src/arachne/` and `uv run ruff format src/arachne/`

## Code Conventions
- Python 3.11+, strict typing
- Pydantic `BaseModel` for all data models
- `pydantic-settings` for configuration
- f-strings only (no `.format()` or `%`)
- `TYPE_CHECKING` guards (no ``)
- ruff for linting/formatting
- pytest for testing
- `uv` for all execution (never bare `python`)

## Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_config.py

# Run with verbose output
uv run pytest -v

# Run with coverage (requires pytest-cov)
uv pip install pytest-cov
uv run pytest --cov=src/arachne --cov-report=term-missing
```

## Linting & Formatting
```bash
# Check for issues
uv run ruff check src/arachne/

# Auto-fix fixable issues
uv run ruff check --fix src/arachne/

# Format all files
uv run ruff format src/arachne/
```

## Working with Multi-Agent IDEs
- **Branch discipline**: Agents working in parallel must stay on their feature branches
- **Scope awareness**: When editing, stay in the scoped files for your task
- **Context files**: `AGENTS.md`, `ROADMAP.md`, and `docs/explanation/architecture.md` provide project context
- **Safety**: Never switch branches, modify worktrees, or drop stashes without explicit request

## Common Gotchas

### ⚠️ Type Hinting Rules
Arachne uses strict type hinting but with a specific project rule: **Never** use ``. 
Instead, always use `TYPE_CHECKING` guards from the `typing` module for type-only imports and use string forward references if necessary. This is enforced during code review and will eventually be automated by ruff.

### 🔒 Security-First Tools
If you are developing or modifying tools (especially `shell_exec` or MCP integrations), ensure you are not using `shell=True` and that you are validating all external inputs. Consult `docs/reference/security.md` before making any changes to the execution runtime.

## PR Process
1. Create branch: `git checkout -b issue/{number}-{short-description}`
2. Make changes, test, lint
3. Commit: `git commit -m "type: description"`
4. Push and open PR

## Known Issues & Roadmap
See `ROADMAP.md` for the full prioritized issue tracker and implementation roadmap.
