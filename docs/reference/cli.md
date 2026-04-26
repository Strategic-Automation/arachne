# CLI Reference

Arachne provides a powerful suite of CLI commands for weaving, executing, and auditing agent graphs.

## Core Commands

### `run`
Weave a graph from a natural language goal and execute it immediately.
- **Usage**: `arachne run [GOAL] [OPTIONS]`
- **Interactive**: If `[GOAL]` is omitted, you will be prompted to enter it.
- **Options**:
    - `--interactive` / `-i`: Review the generated graph before execution.
    - `--max-retries` / `-r`: Number of times the system will try to "self-heal" (default: 3).
    - `--max-tokens`: Override the global token limit for this run.

### `weave`
Generate and visualize an agent graph without executing it.
- **Usage**: `arachne weave [GOAL] [OPTIONS]`
- **Interactive**: Prompts for goal if omitted.
- **Options**:
    - `--output` / `-o`: Save the graph topology to a `.json` file.

---

## History & Retrieval

### `ls`
List all historical sessions.
- **Usage**: `arachne ls [OPTIONS]`
- **Columns**:
    - `Session ID`: Unique ID for each execution.
    - `Created`: Human-friendly relative timestamp.
    - `Goal`: Truncated goal string.
    - `Graph ID`: Hash indicating which cached topology was used.
    - `Status`: Current execution state (Completed, Failed, Running).
- **Options**:
    - `--limit` / `-n`: Limit the number of sessions shown.

### `cat`
View the final result (e.g. report or code fix) of a past session.
- **Usage**: `arachne cat [SESSION_ID]`
- **Default**: Use `last` (or omit) to see the absolute latest result.
- **Function**: Automatically identifies "sink" nodes in the graph and renders their outputs in Markdown.

### `graphs`
List all unique topologies stored in the local cache.
- **Usage**: `arachne graphs`
- **Utility**: Allows you to identify strategies that have worked well in the past and retrieve their **Graph ID** for re-execution.

---

## Reuse & Recovery

### `show`
Visualize the topology of a specific session or cached graph.
- **Usage**: `arachne show [ID]`
- **ID Type**: Accepts either a `Session ID` (e.g. `run_20260405_...`) or a `Graph ID` (SHA256 hash).

### `rerun`
Execute a fresh session using an existing topology.
- **Usage**: `arachne rerun [ID] [OPTIONS]`
- **ID Type**: Accepts `Session ID` (re-uses that run's goal and graph) or `Graph ID` (uses the cached graph).
- **Options**:
    - `--goal`: Override the goal while keeping the graph structure.
    - `--interactive`: Edit the graph before rerunning.

### `resume`
Resume a failed session with auto-healing.
- **Usage**: `arachne resume [SESSION_ID]`
- **Function**: Loads the point of failure, diagnoses the issue, and re-executes using cached intermediate states.

---

### `compile-weaver`
Compile the GraphWeaver module with DSPy optimizers to improve topology generation quality.
- **Usage**: `arachne compile-weaver [OPTIONS]`
- **Options**:
    - `--trainset`: Path to a JSON file of training examples.
    - `--optimizer`: DSPy optimizer to use (default: `BootstrapFewShot`).
    - `--output`: Save the compiled module to a file.
