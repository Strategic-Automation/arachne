# Self-Healing: The AutoHealer and Circuit Breakers

Arachne is designed for reliability in autonomous execution. The system features self-healing capabilities that detect, diagnose, and recover from failures without manual intervention.

## The AutoHealer

The AutoHealer is a specialized DSPy module that activates when a node fails or a verification check is unsatisfied.

### Diagnosis & Strategy

1. **Failure Analysis**: Investigates error logs, tools used, and node context.
2. **Strategy Selection**: Proposes one of the following recovery strategies:
    - **Retry**: Re-run the node with the same parameters (useful for transient errors).
    - **Re-Route**: Adjust node description or tool assignment to bypass the issue.
    - **Re-Weave**: Completely regenerate the graph topology to avoid the failure path.
3. **Outcome Execution**: Applies the selected strategy and resumes execution.

## Circuit Breakers

To prevent infinite loops and runaway costs, Arachne implements strict circuit breakers.

- **Max Global Heals**: Default limit of 10 healing attempts per sessions.
- **Max Node Retries**: Default limit of 3 retries per individual node.
- **Attempt History**: A structured history of all previous failures and healing attempts is maintained to avoid repeating strategies that have already failed.

For MCP Integration details, see [MCP Integration](./mcp-integration.md).
