# 🗺️ Arachne Implementation Roadmap

> **Status**: Beta (v0.1.0)
> **Goal**: DSPy-native self-healing AI agent runtime.

## 👁️ Vision
Arachne is an autonomous agent runtime designed to replace brittle prompt chains with dynamic, DSPy-native agent graphs. It is built for long-running reliability, featuring autonomous self-correction, crash recovery, and strict protocol-first tool governance using the **Model Context Protocol (MCP)**.

---

## 🏗️ Core Philosophy
- **Thin Orchestration, Thick Intelligence**: Minimal structural scaffolding; all "intelligence" lives in DSPy-native modules (Weaver, Evaluator, Healer).
- **Self-Healing Initial Action**: The system automatically detects failures, diagnoses causes, and re-weaves the graph before human intervention.
- **Protocol-First Ecosystem**: Seamlessly connect to any MCP server to safely expand agent capabilities.
- **Stateful Persistence**: Every wave and node result is checkpointed to disk for recovery and observability.

---

## 🏆 Completed Milestones

### ✅ Phase 1: Foundations & Tooling
- **MCP Client**: Dynamic conversion of MCP tools to `dspy.Tool`.
- **Pointer Pattern**: Spillover protection for massive tool outputs (>30KB).
- **Security**: Strict command allowlist validation and Deno sandboxing.

### ✅ Phase 2: Orchestration & Evaluation
- **Graph Topology**: Natural language goal → DAG weaving via DSPy Module.
- **Wave Execution**: Parallel async execution of independent node waves.
- **Triangulated Verification**: Three-level evaluation (Rules → Semantic → HITL).

### ✅ Phase 3: Interactive Oversight (v0.2.5)
- **Goal Clarification**: Intelligent pre-weave intake to resolve ambiguity.
- **Interactive Healing**: Human-led failure diagnosis and repair guidance.
- **Final Approval Gates**: Verification loops to ensure user satisfaction.
- **Documentation**: Professional Diátaxis-structured engine docs.

---

## 🚧 Active Development (v0.3.0 - v0.5.0)

### 📍 Phase 4: Stability & Persistence [NEXT]
- **Wave-Level Checkpointing**: Persistence of intermediate graph states to allow resume on crash.
- **Session Resume**: Full CLI support for `arachne resume <session-id>`.
- **Semantic Topology Search**: Replace SHA256 exact matching with vector-based fuzzy reuse of successful agent graphs.
- **Input Validation**: Strict schema validation for node-to-node data passing.

### 📍 Phase 5: Observability & Streaming
- **Event Bus**: SSE streaming of `NodeStarted`, `TokenEmitted`, and `AutoHealTriggered` events.
- **CLI Progress Streaming**: Real-time visual feedback for long-running tasks.
- **Async Refactor**: Eliminating nested `asyncio.run` calls for performance.

---

## 🔭 Long-Term Vision (v1.0.0+)

### 🛠️ Advanced Tooling
- **Playwright Stealth Agent**: Autonomous browser interaction with anti-bot resilience.
- **Credential Vault**: Encrypted JIT injection of secrets into agent modules.

### 🛡️ Security & Sandboxing
- **Secure Code Execution Environments**: Implement fully isolated backend sandboxing (via Docker, E2B microVMs, or Deno) for safe evaluation of agent-generated Python and Javascript code.

### 🧠 Thick Intelligence Replacements
- **Framework-Level Automated Learning**: Wire global memory tools directly into the core engine. Auto-healer writes resolved failure lessons to memory; Weaver pre-fetches memory to avoid repeating past graph mistakes.
- **Architecture Critique**: Semantic review of the generated DAG before execution begins.
- **Just-in-Time Tool Broker**: Dynamic discovery of tools based on runtime failures.

---

## 🏗️ Technical Debt (Future GitHub Issues)
These technical improvements are prioritized for backend maintenance:
- **Dependency Injection**: Replace global `Settings` with constructor injection.
- **Service Abstraction**: Create formal interfaces for `MCPManager` and `SessionCoordinator`.
- **Logging Standardization**: Comprehensive migration to `structlog` across all modules.
- **Test Coverage**: Reach >80% coverage for core execution modules.

---

## 🤝 Community & Support
- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/Strategic-Automation/arachne/issues).
- **Security**: Report vulnerabilities to `dan@strategicautomation.com`.
- **License**: MIT (See [LICENSE](LICENSE) for details).
