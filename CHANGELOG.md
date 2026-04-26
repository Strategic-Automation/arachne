# Arachne Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-04-26

Initial open source release.

### Added
- **Core Framework**
  - DSPy-native graph weaving with constraint awareness
  - Triangulated verification (Rules → Semantic → HITL)
  - WaveExecutor with wave-based parallel execution
  - Session persistence (inputs.json, graph.json, state.json)
  - Checkpoint and artifact management

- **Tool Ecosystem**
  - MCP client integration with `dspy.Tool.from_mcp_tool()`
  - Pointer pattern for large tool outputs (>30KB)
  - `NodeDef.mcp_servers` for requesting MCP servers
  - Built-in tools: web_search, web_fetch, shell_exec, read_file, write_file
  - Human-in-the-loop tools: request_context, request_approval
  - Lifecycle tools: save_checkpoint, load_checkpoint, list_checkpoints
  - Memory tools: write_memory, search_memory

- **Evaluation & Self-Healing**
  - GoalDefinition schema with constraints and success_criteria
  - Circuit breaker for self-healing loops (max heals, per-node retries)
  - Attempt history to prevent repeated fixes
  - AutoHealer with retry/re-route/re-weave strategies

- **Dynamic Provisioning**
  - ToolMaker and SkillMaker for runtime tool/skill generation
  - 280+ built-in skills across 20+ categories

- **Configuration**
  - Pydantic-settings based configuration
  - Langfuse observability integration
  - YAML config file support
  - Environment variable override

- **CLI**
  - `arachne run` - Weave and execute
  - `arachne weave` - Generate topology only
  - `arachne show` - Visualize a past graph
  - `arachne rerun` - Re-execute a past graph
  - `arachne resume` - Resume failed session
  - `arachne ls` - List sessions
  - `arachne clean` - Cleanup old sessions
