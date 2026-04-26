# Error Recovery Protocol

When encountering a failed node or unexpected output:

1. **Isolate** — Identify the first node that failed. Don't skip ahead.
2. **Diagnose** — Read the error message and check if the input was malformed or missing.
3. **Retry** — If the failure seems transient (rate limit, network error), retry with increased timeout.
4. **Refine** — If the output was incorrect, use ChainOfThought to re-reason with explicit constraints.
5. **Escalate** — If retries fail 3+ times, mark the node as FAILED and let the evolver redesign the topology.

**Never silently swallow errors.** Always propagate them to the failure evaluator.
