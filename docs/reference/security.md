---
type: reference
description: Security model, trust boundaries, and implemented security measures
---

# Arachne Security Policy

## 🚨 Reporting Security Issues

**Do not report security vulnerabilities through public GitHub issues.**

Instead, please send details to the maintainers through a private channel or email.

---

## 🔐 Security Model

### Trust Boundaries

| Component | Trust Level | Justification |
| :--- | :--- | :--- |
| User Goal Input | Untrusted | Can contain malicious prompts |
| LLM-Generated Code | Untrusted | DSPy can generate arbitrary code/tools |
| MCP Server Commands | Semi-trusted | Admin-defined but executed as process |
| Shell Exec Tool | High Risk | Executes arbitrary shell commands |
| Custom Tools (Python) | High Risk | Runs in process memory |
| Session Data | Internal | Stored locally, not exposed |

---

## 🛡️ Implemented Security Measures

### 2. Pointer Pattern (Context Isolation)
Large tool outputs (>30KB) are written to disk instead of kept in memory:
```
tools/spillover.py: SPILLOVER_THRESHOLD = 30000
```

### 3. Session Isolation
Each run gets isolated session directory:
```
~/.local/share/arachne/sessions/run_{timestamp}/
├── inputs.json
├── graph.json
├── state.json
├── checkpoints/
├── outputs/
└── logs/
```

---

## ⚠️ Known Security Risks

### 1. shell_exec Tool (HIGH RISK)
**Location:** `src/arachne/tools/system/shell.py`

The `shell_exec` tool uses `shell=False` with `shlex.split()`:
```python
r = subprocess.run(command_list, shell=False, capture_output=True, text=True, timeout=30)
```

**Risk:** Commands are split via `shlex.split()` and run without shell injection vectors. However, custom commands could still exhaust resources or access the filesystem.

**Mitigation:**
- 30-second timeout prevents long-running commands
- `shell=False` prevents injection via shell metacharacters
- Commands are passed as arg lists, not raw strings

### 2. MCP Server Commands (MEDIUM RISK - UNPATCHED)
**Location:** `src/arachne/topologies/tool_resolver.py`

MCP server commands are parsed but not validated:
```python
parts = shlex.split(server_cmd)
```

**Risk:** User could specify malicious commands in `NodeDef.mcp_servers`.

**Recommendation:** Add allowlist validation:
```python
ALLOWED_MCP_COMMANDS = {"npx", "python3", "uvx", "deno", "node"}
```

### 3. Python Custom Tools (HIGH RISK)
**Location:** `src/arachne/tools/__init__.py`

Custom Python tools run in-process:
```python
spec.loader.exec_module(mod)
```

**Risk:** Malicious tool code has full process access.

**Recommendation:** Document that custom Python tools should only be from trusted sources.

### 4. LLM Prompt Injection (MEDIUM RISK)
**Risk:** Adversarial goals could attempt to extract system prompts or manipulate behavior.

**Mitigation:** DSPy Signatures provide some structure, but ultimate defense is treating LLM output as untrusted.

---

## 🔒 Security Checklist for Production

Before deploying Arachne in production:

- [ ] Review and limit MCP server configurations
- [ ] Consider disabling `shell_exec` tool or running in container
- [ ] Audit custom tools in `~/.local/share/arachne/tools/custom/`
- [ ] Set appropriate resource limits (cost, tokens, time)
- [ ] Enable Langfuse for audit logging
- [ ] Review session directory permissions

---

## 📋 Security-Related Code Locations

| File | Risk | Description |
| :--- | :--- | :--- |
| `tools/__init__.py` | HIGH | Custom Python tool execution (sandboxed via import) |
| `topologies/tool_resolver.py` | MEDIUM | MCP command validation |
| `core.py` | LOW | Langfuse env vars (internal) |

---

## 🔑 Credential Handling

### Environment Variables
API keys stored in environment variables (via `.env`):
- `LLM_API_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_PUBLIC_KEY`

### Vault (Future - Phase 6)
Planned: Dynamic `{{vault.key}}` injection with redaction.

---

## 📝 Security Logging

Currently minimal. Recommended additions:
- Log all shell_exec invocations
- Log MCP server startup/shutdown
- Log custom tool loading
- Audit trail for session access
