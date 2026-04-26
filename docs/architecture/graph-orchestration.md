# Graph Orchestration: Weaver, Runner, and Evaluator

Arachne's core execution loop is driven by the interaction between the Weaver (planning), the Runner (execution), and the Evaluator (verification).

## The Graph Weaver

The Weaver is a DSPy module responsible for transforming a high-level goal into a Directed Acyclic Graph (DAG) of discrete tasks.

### Key Responsibilities

- **Goal Analysis**: Deconstructs complex goals into manageable nodes.
- **Dependency Map**: Determines the optimal order of execution.
- **Tool Assignment**: Maps required tools and MCP servers to specific nodes.
- **Fail Context Incorporation**: When re-weaving, it incorporates failure context to avoid previous pitfalls.

## The Graph Runner

The Runner executes the DAG in "waves." A wave consists of all nodes that have their dependencies satisfied and can run in parallel.

### Execution Process

1. **Wave Identification**: Find nodes with met dependencies.
2. **Parallel Execution**: Execute each node in the wave simultaneously.
3. **Context Propagation**: Pass the output of predecessor nodes as input to successor nodes.
4. **Checkpointing**: Save the state of each wave to disk immediately upon completion.

## The Triangulated Evaluator

Once the Runner completes the graph, the Evaluator performs a multi-level check on the final output.

- **Level 0 (Rules)**: Instant verification against numeric or hard constraints (e.g., "cost < $1.00").
- **Level 1 (Semantic)**: A DSPy module scores the result's confidence against the success criteria (0.0 to 1.0).
- **Level 2 (HITL)**: If confidence is below the threshold, the system flags the result for human-in-the-loop review.
