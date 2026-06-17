---
type: explanation
description: Deep dive into Arachne's runtime architecture, graph lifecycle, execution model, and trust boundaries
---

# Arachne architecture

Arachne is a DSPy-native runtime for goal-driven agent graphs. A user supplies a goal, Arachne turns it into a typed topology, executes that topology in dependency-aware waves, evaluates the result, and repairs the run when quality or execution checks fail.

## System goals

Arachne is designed around five principles:

1. **Graphs over prompt chains** — agent plans are explicit directed acyclic graphs.
2. **Typed contracts** — DSPy signatures and Pydantic models define interfaces.
3. **Parallel where safe** — independent graph nodes run in topological waves.
4. **Inspectable state** — sessions, graphs, checkpoints, and outputs are persisted.
5. **Repair over restart** — failures trigger retry, re-route, or re-weave strategies.

## High-level system

```mermaid
flowchart TB
    subgraph Surface[User surface]
        CLI[Typer CLI]
        Project[Project files]
        Human[Human review]
    end

    subgraph Core[Arachne runtime]
        Intake[Goal intake]
        Weaver[GraphWeaver]
        Provision[Provisioning]
        Executor[WaveExecutor]
        Evaluator[TriangulatedEvaluator]
        Healer[AutoHealer]
    end

    subgraph ToolLayer[Tool layer]
        Resolver[ToolResolver]
        Builtins[Built-in tools]
        MCP[MCP servers]
        Skills[Skill protocols]
    end

    subgraph State[State and observability]
        Sessions[Session manager]
        Topologies[Topology cache]
        Artifacts[Outputs and checkpoints]
        Logs[Logs and traces]
    end

    CLI --> Intake
    Project --> Intake
    Human --> Intake
    Intake --> Weaver
    Weaver --> Topologies
    Weaver --> Provision
    Provision --> Executor
    Executor --> Resolver
    Resolver --> Builtins
    Resolver --> MCP
    Resolver --> Skills
    Executor --> Evaluator
    Evaluator -->|pass| Sessions
    Evaluator -->|repair needed| Healer
    Healer -->|retry or re-route| Executor
    Healer -->|re-weave| Weaver
    Executor --> Artifacts
    Executor --> Logs
```

## Execution lifecycle

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI
    participant Core as Arachne core
    participant Weaver as GraphWeaver
    participant Exec as WaveExecutor
    participant Eval as Evaluator
    participant Heal as AutoHealer
    participant Store as Session store

    User->>CLI: arachne run "goal"
    CLI->>Core: GoalDefinition
    Core->>Weaver: weave topology
    Weaver-->>Core: GraphTopology
    Core->>Store: persist graph and inputs
    Core->>Exec: execute waves
    Exec->>Store: persist node outputs and checkpoints
    Exec-->>Core: RunResult
    Core->>Eval: evaluate result
    alt acceptable result
        Eval-->>Core: pass
        Core->>Store: mark completed
        Core-->>CLI: render final output
    else failed or low confidence
        Eval-->>Core: fail
        Core->>Heal: diagnose failure
        Heal-->>Core: retry, re-route, or re-weave
        Core->>Exec: continue repaired run
    end
```

## Core components

### GraphWeaver

`GraphWeaver` transforms a goal into a `GraphTopology`. It defines nodes, dependencies, roles, inputs, outputs, required tools, and success criteria.

Responsibilities:

- convert natural-language goals into structured graph topology
- keep the graph acyclic and executable
- choose node roles such as `predict`, `chain_of_thought`, `react`, `human_in_loop`, or `recursive`
- produce topology metadata for caching and review

### WaveExecutor

`WaveExecutor` runs topology nodes in topological waves. Nodes in the same wave do not depend on each other and can run concurrently.

```mermaid
flowchart LR
    subgraph Wave1[Wave 1]
        A[Search sources]
        B[Inspect local files]
    end

    subgraph Wave2[Wave 2]
        C[Fetch documents]
        D[Summarise repository context]
    end

    subgraph Wave3[Wave 3]
        E[Synthesise answer]
    end

    A --> C
    B --> D
    C --> E
    D --> E
```

Execution rules:

- a node starts only when all upstream dependencies have completed
- wave failures prevent dependent downstream nodes from running blindly
- checkpointing captures progress after waves
- large tool outputs use the pointer pattern instead of overflowing model context

### ToolResolver

`ToolResolver` normalises access to tools from different sources.

```mermaid
flowchart TD
    Node[Node request] --> Resolver[ToolResolver]
    Resolver --> Builtins[Built-in Python tools]
    Resolver --> MCP[MCP server tools]
    Resolver --> Human[Human-in-loop tools]
    Resolver --> Skills[Skill protocol context]
```

This keeps node execution code independent of whether a tool is local, protocol-backed, or human-mediated.

### TriangulatedEvaluator

The evaluator combines multiple checks rather than trusting a single LLM judgement.

```mermaid
flowchart TD
    Result[Run result] --> Rules[Level 0: deterministic rules]
    Rules --> Semantic[Level 1: semantic scoring]
    Semantic --> Confidence{Confidence high enough?}
    Confidence -->|yes| Pass[Accept output]
    Confidence -->|no| Human[Level 2: human escalation]
    Human --> Decision{Approved?}
    Decision -->|yes| Pass
    Decision -->|no| Repair[Send to AutoHealer]
```

### AutoHealer

`AutoHealer` diagnoses failed runs and chooses a repair strategy.

| Strategy | Use when | Typical action |
|---|---|---|
| Retry | transient tool or network issue | re-run the failed node |
| Re-route | node instruction or tool choice is weak | adjust route or inputs |
| Re-weave | graph structure is wrong | generate a revised topology |

Circuit breakers prevent endless repair loops.

## Data model

```mermaid
classDiagram
    class GoalDefinition {
        goal
        constraints
        success_criteria
    }

    class GraphTopology {
        graph_id
        nodes
        edges
        metadata
    }

    class NodeDef {
        id
        role
        inputs
        outputs
        tools
    }

    class EdgeDef {
        source
        target
    }

    class RunResult {
        session_id
        status
        outputs
        failures
    }

    GoalDefinition --> GraphTopology
    GraphTopology --> NodeDef
    GraphTopology --> EdgeDef
    GraphTopology --> RunResult
```

## Session layout

Each run persists enough information to inspect, resume, and audit the graph.

```mermaid
flowchart TD
    Session[session directory] --> Inputs[inputs.json]
    Session --> Graph[graph.json]
    Session --> State[state.json]
    Session --> Outputs[outputs]
    Session --> Checkpoints[checkpoints]
    Session --> Logs[logs]
```

Typical contents:

| Path | Purpose |
|---|---|
| `inputs.json` | original goal, context, and run options |
| `graph.json` | woven topology |
| `state.json` | node status and execution state |
| `outputs/` | durable node artefacts |
| `checkpoints/` | recovery snapshots |
| `logs/` | execution diagnostics |

## Configuration flow

```mermaid
flowchart TD
    Env[Shell environment and local .env] --> Settings[Settings loader]
    Project[Project arachne.yaml] --> Settings
    User[User defaults] --> Settings
    Defaults[Code defaults] --> Settings
    Settings --> Runtime[Runtime configuration]
    Runtime --> DSPy[DSPy configuration]
    Runtime --> Tools[Tool availability]
    Runtime --> Sessions[Session paths]
```

Configuration is intentionally split between private credentials and structured settings. Runtime values are merged with environment and local `.env` values taking priority.

## Trust boundaries

Arachne executes tools and model-generated plans, so trust boundaries matter.

```mermaid
flowchart LR
    UserGoal[User goal] --> Runtime[Arachne runtime]
    Runtime --> BuiltinTools[Built-in tools]
    Runtime --> MCPTools[MCP tools]
    Runtime --> Files[Local files]
    Runtime --> HumanGate[Human approval]

    classDef untrusted fill:#ffe6e6,stroke:#cc0000,color:#111;
    classDef guarded fill:#fff4cc,stroke:#cc8a00,color:#111;
    classDef trusted fill:#e6f4ea,stroke:#1f7a1f,color:#111;

    class UserGoal untrusted;
    class Runtime guarded;
    class BuiltinTools,MCPTools,Files guarded;
    class HumanGate trusted;
```

Guidelines:

- treat user goals and model-generated plans as untrusted inputs
- keep tool execution explicit and auditable
- prefer protocol-backed tools with narrow permissions
- require human approval for destructive or high-impact operations
- preserve session records for post-run review

## Source map

```text
src/arachne/
├── cli/                 # Typer CLI and terminal display
├── core.py              # Top-level Arachne module
├── execution/           # orchestration and execution manager
├── optimizers/          # DSPy optimiser support
├── runtime/             # evaluation, healing, provisioning, observability
├── sessions/            # durable session management
├── skills/              # reusable expert protocols
├── tools/               # built-in and protocol-backed tools
└── topologies/          # graph schema, weaving, node and wave execution
```

## Design patterns

### Graph-first planning

Planning output is a serialisable topology, not an opaque prompt. This makes runs inspectable and reusable.

### Pointer pattern

Large outputs are written to disk and replaced with a compact pointer plus preview. Downstream nodes can read the full artefact when needed.

### Wave execution

Topological waves provide concurrency without violating dependencies.

### Triangulated evaluation

Arachne combines deterministic, semantic, and human checks to avoid trusting a single judgement path.

### Repair loop

Failed runs are not simply restarted. The runtime chooses the smallest useful repair: retry, re-route, or re-weave.

## Related docs

- [Getting started](../tutorials/getting-started.md)
- [CLI reference](../reference/cli.md)
- [DSPy-native concepts](../key_concepts/dspy-native.md)
- [Pointer pattern](../key_concepts/pointer-pattern.md)
