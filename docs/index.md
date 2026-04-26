# Arachne Documentation

Welcome to the Arachne documentation. This site is organized using the [Diátaxis framework](https://diataxis.fr/) to help you find the right content for your needs.

## 🕸️ Our Philosophy: Stop Prompting. Start Programming.

Most agent frameworks rely on "long prompts" that are hard to debug and even harder to scale. Arachne is built on **DSPy**, which treats agent logic as **code**, not strings. We replace fragile prompting with:
- **Compiled Signatures**: Robust input/output contracts.
- **Dynamic Weaving**: Graphs that adapt to your goal.
- **Autonomous Healing**: Systems that fix themselves when they break.

## 🏗️ Documentation Structure

| Quadrant | Focus | Purpose |
|----------|-------|---------|
| **[Tutorials](tutorials/getting-started.md)** | Learning-oriented | Step-by-step guides for beginners to get running fast. |
| **[Guides](guides/developer-guide.md)** | Goal-oriented | Practical recipes for testing, tools, and advanced workflows. |
| **[Explanation](explanation/architecture.md)** | Understanding-oriented | Deep dives into the Weaver, Wave Executor, and Healing logic. |
| **[Reference](reference/cli.md)** | Information-oriented | Authoritative specs for the CLI, Schemas, and Standards. |

## Quick Links

### Tutorials
- [Getting Started](tutorials/getting-started.md) — Set up Arachne and run your first agent

### Guides
- [Developer Guide](guides/developer-guide.md) — Setup, testing, and workflow
- [Testing Guide](guides/testing.md) — Running tests and pytest configuration
- [Creating Skills](guides/creating-skills.md) — Authoring custom expert skills
- [MCP Setup](guides/mcp-setup.md) — Model Context Protocol integration

### Explanation
- [Architecture](explanation/architecture.md) — System design, components, and data flow
- [Architecture Overview](architecture/overview.md) — High-level system overview
- [Graph Orchestration](architecture/graph-orchestration.md) — Topology weaving and execution
- [MCP Integration](architecture/mcp-integration.md) — MCP server integration design
- [Self-Healing](architecture/self-healing.md) — AutoHealer and failure recovery

### Key Concepts
- [DSPy-Native](key_concepts/dspy-native.md) — Why DSPy over prompt engineering
- [Triangulated Evaluation](key_concepts/triangulated-evaluation.md) — Rules + Semantic + HITL
- [Pointer Pattern](key_concepts/pointer-pattern.md) — Large output spillover to disk

### Reference
- [CLI Reference](reference/cli.md) — Comprehensive command-line guide
- [Schema Reference](reference/schema.md) — Pydantic models and topology schemas
- [Coding Standards](reference/coding-standards.md) — Python style and conventions
- [Security Policy](reference/security.md) — Security and trust boundaries

### Other Resources
- [Configuration](configuration.md) — Environment variables and YAML settings
- [Environment Setup](environment-setup.md) — Installing dependencies
- [Troubleshooting](troubleshooting.md) — Common issues and solutions
- [Contributing](roadmap/contributing.md) — Contribution guidelines

## Related Resources

- [AGENTS.md](../AGENTS.md) — Agent instructions and project rules
- [ROADMAP.md](../ROADMAP.md) — Project vision, phases, and milestones