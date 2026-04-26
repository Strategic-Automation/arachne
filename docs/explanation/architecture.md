---
type: explanation
description: Deep dive into Arachne's system architecture, components, and design patterns
---

# Arachne Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                Arachne CLI                                  │
│  (run, weave, resume, clean, ls)                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Arachne Core                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │   Weaver   │───▶│  Provision │───▶│   Runner    │───▶│  Evaluator │   │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘   │
│        │                                        │                │           │
│        │                                        ▼                │           │
│        │                               ┌─────────────────┐        │           │
│        └──────────────────────────────│  AutoHealer    │◀───────┘           │
│                                        │ (Self-Healing) │                    │
│                                        └─────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Sessions Layer                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  Session Manager                                                  │    │
│  │  ├── inputs.json    (goal, context)                              │    │
│  │  ├── graph.json     (woven topology)                             │    │
│  │  ├── state.json     (node results, status)                       │    │
│  │  ├── checkpoints/  (wave-level snapshots)                       │    │
│  │  ├── outputs/      (node artifacts)                              │    │
│  │  └── logs/         (execution logs)                              │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Execution Flow

```
Goal → Weaver(LLM) → GraphTopology → GraphRunner → Evaluate → [Fail?] → AutoHealer → Re-weave/Re-route/Retry
                                                                        ↓ [Pass]
                                                                  Return Results
```

## Core Components

### 1. GraphWeaver (`topologies/weaver.py`)

**Responsibility:** Transforms natural language goals into DSPy-native graph topologies.

- DSPy `Module` using `dspy.ChainOfThought` for topology generation
- Low temperature (0.1) for deterministic structured output
- Uses `TopologyEvaluator` as reward_fn with `N=3, threshold=0.8`
- Constraints from `GoalDefinition` injected into prompt

### 2. WaveExecutor (`topologies/wave_executor.py`)

**Responsibility:** Executes graph topologies with wave-based parallelism.

- `topological_waves()` splits graph into independent execution waves
- Each wave runs concurrently via `dspy.asyncify` + `asyncio.gather`
- `_NodeModule` wraps `NodeDef` into role-specific DSPy modules
- Nodes executed via DSPy module wrapping with role-specific logic
- MCP tools resolved per-node via `MCPClientManager`
- Checkpointed after every wave via `Session.save_state()`

**Roles:** `predict`, `chain_of_thought`, `react`, `human_in_loop`, `recursive`

### 3. TriangulatedEvaluator (`runtime/evaluator.py`)

- **Level 0**: Rule-based constraint checking (cost, time limits)
- **Level 1**: Semantic evaluation via `dspy.ChainOfThought` scoring (0.0–1.0)
- **Level 2**: Human escalation flag when confidence < threshold

### 4. AutoHealer (`runtime/auto_healer.py`)

- `dspy.ChainOfThought` module diagnosing failures
- Strategies: `retry`, `re-route`, `re-weave`
- Circuit breaker: max 10 global heals, max 3 per-node retries

### 5. Core (`core.py`)

- `Arachne(dspy.Module)` composes Weaver → Runner → Evaluator
- Self-healing loop with strategy pattern application
- Topology caching by SHA-256 goal hash

## Data Flow

### Goal → Execution

```
1. CLI: arachne run "Find me..."
         │
         ▼
2. Arachne.weave(goal)
         │
    ┌────┴────┐
    ▼         ▼
GraphWeaver  GoalDefinition
    │         │
    ▼         ▼
GraphTopology ◀────────────── (constraints, success_criteria)
    │
    ▼
3. provision_graph() - Create missing tools/skills
    │
    ▼
4. WaveExecutor.execute() - Run waves
    │
    ▼
5. TriangulatedEvaluator.evaluate() - Verify output
    │
    ▼
6. Check results:
   - Success → Return RunResult
   - Failure → AutoHealer → Retry/Re-Route/Re-Weave
```

### Context Propagation

```
Goal/Inputs
    │
    ▼
Wave N: Node A ──output: "x"──▶ all_results["a"] = {...}
                              all_results["output_field"] = "x"
    │
    ▼
Wave N+1: Node B ──input: "output_field"──▶ all_results.get("output_field")
```

## Module Dependencies

```
cli/main.py
  │
  ├─▶ core.py (Arachne)
  │     │
  │     ├─▶ config.py (Settings)
  │     │
  │     ├─▶ topologies/weaver.py (GraphWeaver)
  │     │
  │     ├─▶ topologies/wave_executor.py (WaveExecutor)
  │     │     ├── tools/system/shell.py (resolve_tool)
  │     │     ├── runtime/mcp_manager.py
  │     │     └── skills/registry.py
  │     │
  │     ├─▶ runtime/evaluator.py
  │     ├─▶ runtime/auto_healer.py
  │     └─▶ sessions/manager.py
```

## File Map

```
src/arachne/
├── cli/main.py         # Typer CLI: run, weave, resume, ls, clean, graphs, compile-weaver
├── cli/display.py      # CLI display utilities
├── core.py             # Arachne top-level module
├── config.py           # Pydantic settings (LLM, Langfuse, cost, MCP...)
├── topologies/
│   ├── schema.py       # All graph topology Pydantic models
│   ├── weaver.py       # GraphWeaver -- goal → topology
│   ├── wave_executor.py # WaveExecutor -- wave-based execution
│   ├── tool_resolver.py # ToolResolver -- tool/MCP resolution
│   └── node_executor.py # NodeExecutor -- per-node execution
├── runtime/
│   ├── evaluator.py    # TriangulatedEvaluator
│   ├── auto_healer.py  # AutoHealer
│   ├── provision.py    # Auto-generate missing tools/skills
│   ├── mcp_manager.py  # MCP per-session manager
│   ├── knowledge_store.py # Persistent knowledge store
│   └── context_store.py   # Thread-local context store
├── tools/
│   ├── web/
│   │   ├── duckduckgo_search.py  # DuckDuckGo search
│   │   └── web_fetch.py          # Web content fetch
│   ├── system/
│   │   ├── shell.py              # Shell command execution
│   │   ├── file_read.py          # Read files
│   │   └── file_write.py         # Write files
│   ├── human/
│   │   ├── request_context.py    # Request context from user
│   │   └── request_approval.py   # Request approval from user
│   ├── lifecycle/
│   │   └── checkpoints.py        # Checkpoint save/load/list
│   ├── memory/
│   │   └── operations.py         # Write/search memory
│   └── spillover.py              # Pointer pattern wrapper
├── sessions/
│   └── manager.py      # Session class
```

## Key Design Patterns

### Pointer Pattern

Tool outputs > 30KB are truncated with a preview and saved to disk. Downstream nodes can `read_file()` the full result. Prevents context window overflow.

### Wave Execution

Graphs split into topological waves via Kahn's algorithm. Independent nodes in the same wave execute concurrently. Failure in a wave skips all downstream nodes.

### Self-Evaluation

Nodes use `dspy.ChainOfThought` for self-evaluation with scoring. The `SelfEvaluator` module scores quality, and the system auto-retries if below threshold.

### Topology Caching

Previously woven graphs cached by SHA-256 hash of goal. Identical goals reuse cached topologies without LLM calls.

### Trust Boundaries

| Component | Trust Level |
|-----------|-------------|
| User Goal Input | Untrusted |
| LLM-Generated Code | Untrusted |
| MCP Server Commands | Semi-trusted |
| Shell Exec | CRITICAL RISK (shell=True) |
| Custom Tools (Python) | High Risk |
| Session Data | Internal |

## Configuration

Arachne uses a dual-file hierarchy (highest to lowest priority):

1. **Environment Variables**: Shell environment and `.env` file for **secrets** (API keys).
2. **YAML Config (`arachne.yaml`)**: Structured, versioned **settings** (budgets, model IDs).
3. **Global Config (`~/.arachne/config.yaml`)**: User-level defaults.
4. **Code Defaults**: Built-in fallback values.

The `quickstart.sh` script generates both files and ensures secrets are kept out of the YAML file.

## Known Architecture Issues

See `ROADMAP.md` and `SECURITY.md` for prioritized improvements.

- Remediate systemic violation of `` rule
- Extract `_execute()` monolith into Strategy pattern classes
- Unify MCP managers (drop per-session if singleton is better, or vice versa)
- Add `_validate_topology()` to GraphTopology (input validation)
