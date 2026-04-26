# Arachne — AI Coding Assistant Context

This document provides context for AI coding assistants (Claude Code, Gemini CLI, GitHub Copilot, Cursor, etc.) to understand the Arachne project and assist with development.

## Project Overview

Arachne is a DSPy-native, code-first runtime harness for building, executing, and evolving production AI agents. Unlike traditional agent frameworks that rely on fixed prompts, Arachne treats agentic tasks as dynamic execution graphs (Topologies) that are "woven" on demand from natural language goals. It features a robust self-healing loop that can diagnose execution failures, repair graphs, and re-execute until a goal is met or human intervention is required.

### Key Components

-   **Arachne (Core)** - The top-level `dspy.Module` that orchestrates the entire lifecycle: Intake -> Weave -> Provision -> Execute -> Evaluate -> Heal.
-   **GraphWeaver** - The "Loom" of the system. A DSPy module that analyzes natural language goals and generates a `GraphTopology` (a Directed Acyclic Graph of specialized nodes).
-   **ExecutionManager** - The orchestration engine. It manages the parallel execution of graph nodes, monitors for failures, and triggers the healing process.
-   **WaveExecutor** - Handles the low-level async execution of nodes in "waves" (parallel groups of independent nodes) to maximize efficiency.
-   **NodeExecutor** - Executes individual nodes. Each node is a miniature DSPy module that can use specific tools and follow expert protocols (Skills).
-   **ToolResolver** - Unified interface for resolving tools, including built-in Python functions and MCP (Model Context Protocol) servers.
-   **TriangulatedEvaluator** - A multi-layered verification system that combines deterministic rules, semantic checks, and Human-in-the-Loop (HITL) gates.
-   **AutoHealer** - A failure diagnosis engine that analyzes errors and proposes repair strategies (retry, re-route, or re-weave).

### How Arachne Works (Lifecycle)

Each task execution in Arachne follows a structured lifecycle:

1.  **Goal Intake & Analysis**: Arachne analyzes the user's natural language goal for ambiguity. In interactive mode, it may ask clarifying questions before proceeding.
2.  **Topology Weaving**: The `GraphWeaver` generates a `GraphTopology` (DAG). This defines which nodes are needed, their roles, inputs, outputs, and the skills/tools required.
3.  **Graph Provisioning**: Arachne automatically initializes the tools and expert skills requested by the topology.
4.  **Interactive Review (Optional)**: If enabled, the user can inspect the planned graph and provide feedback or modifications before execution begins.
5.  **Wave-Based Execution**: Nodes are executed in parallel waves. A node only runs once all its upstream dependencies are satisfied.
6.  **Evaluation & Self-Healing**: Once a sink node completes, the `TriangulatedEvaluator` checks the results. If a failure or low-quality output is detected:
    *   The `AutoHealer` diagnoses the issue.
    *   Arachne applies a fix strategy: **Retry** (transient errors), **Re-route** (instruction tweaks), or **Re-weave** (structural graph redesign).
    *   The process repeats until success or a circuit breaker is triggered.

## Project Architecture

### Source Structure (`src/arachne/`)

-   `core.py`: Main entry point (`Arachne` class).
-   `execution/`: Orchestration logic (`ExecutionManager`).
-   `topologies/`: Graph definition, schema, and weaving (`GraphWeaver`, `WaveExecutor`, `NodeExecutor`, `ToolResolver`).
-   `optimizers/`: DSPy optimizer modules — build-time compilation tools (`BootstrapFewShot` compiler, training demos). Separate from `topologies/` to keep runtime and optimization concerns distinct.
-   `runtime/`: Post-execution logic (`TriangulatedEvaluator`, `AutoHealer`, `Provisioning`).
-   `sessions/`: State persistence (file-based `Session` management).
-   `tools/`: Built-in and MCP tool ecosystem.
-   `skills/`: Expert protocol library (Markdown-based instructions for nodes).
-   `config.py`: Settings and model capability detection (`pydantic-settings`).

### Test Structure (`tests/`)

-   `tests/`: Flat test directory with all tests.
    -   `tests/tools/`: Tests for built-in tools.

### Documentation (`docs/`)

Arachne uses the [Diátaxis framework](https://diataxis.fr/) for documentation. Use the table below to find relevant technical context:

| Category | Purpose | Primary Entry Point |
| :--- | :--- | :--- |
| **Tutorials** | Learning-oriented onboarding | [getting-started.md](docs/tutorials/getting-started.md) |
| **Guides** | Task-oriented recipes (Testing, Skills, MCP) | [developer-guide.md](docs/guides/developer-guide.md) |
| **Explanation** | Understanding-oriented deep dives | [architecture.md](docs/explanation/architecture.md) |
| **Reference** | Information-oriented technical specs | [coding-standards.md](docs/reference/coding-standards.md) |

**Key Deep-Dive Resources:**
-   [Documentation Root](docs/index.md) — Central entry point for all project docs.
-   [Architecture Overview](docs/architecture/overview.md) — Detailed graph and orchestration logic.
-   [Key Concepts](docs/key_concepts/dspy-native.md) — Logic behind DSPy-native execution and Triangulated Evaluation.
-   [CLI Reference](docs/reference/cli.md) — Comprehensive command list and arguments.

## Development Setup

### Requirements
- Python 3.11+ (Required for modern type hinting and performance)
- `uv` package manager (Required for fast, consistent dependency management)

### Setup Instructions
```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies and dev tools
uv sync --all-groups
```

## Running Arachne

### CLI Commands
Arachne provides a powerful CLI via `typer`:

```bash
# Weave and execute a goal immediately
uv run arachne run "Research recent AI safety breakthroughs"

# Just weave and visualize a graph (dry run)
uv run arachne weave "Goal description" --output graph.json

# Resume a failed or partial session
uv run arachne resume run_20260424_090000

# Manage sessions
uv run arachne ls      # List recent runs
uv run arachne cat     # View output of the last run
uv run arachne rm ID   # Delete a session
```

## Style Guides

### Python Style Guide
- **Line Length**: 120 characters maximum.
- **Indentation**: 4 spaces.
- **Formatter/Linter**: `ruff`. Run `uv run ruff format` and `uv run ruff check` before committing.
- **Type Hinting**: Required on all function signatures. Use string annotations (e.g., `"ClassName | None"`) for forward references.
- **Imports**: 
    - Use **absolute imports** for both source and tests (e.g., `from arachne.core import Arachne`).
    - Organize imports: Standard Library -> Third-party -> Local `arachne` modules.
- **String Formatting**: **Always use f-strings.** Never use `%` formatting, `str.format()`, or string concatenation for building strings. This is a hard rule — no exceptions.
- **Data Models**: Use Pydantic `BaseModel` with `Field()` for all structured data.

### Testing Philosophy
- **Real Code Over Mocks**: Use real Arachne components (Weaver, Evaluator) in tests. Mock only the LLM responses and external network/API calls.
- **Coverage**: Maintain >80% coverage.
- **Async**: Use `pytest-asyncio` for all graph and tool execution tests.

## Commit Message Format
Strictly follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat(scope): ...`
- `fix(scope): ...`
- `docs(scope): ...`
- `refactor(scope): ...`

## Python Tips for Arachne
- **DSPy Integration**: Use `dspy.Predict` or `dspy.ChainOfThought` for node logic. Always use `dspy.configure(adapter=dspy.ChatAdapter())` when structured output is required.
- **Pydantic Validation**: Leverage `model_validate()` and `model_dump(mode="json")` for robust serialization of topologies and results.
- **Error Handling**: Catch specific exceptions. In `ExecutionManager`, use the `AutoHealer` to turn exceptions into actionable repair strategies.

