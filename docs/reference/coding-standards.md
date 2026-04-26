---
type: reference
description: Python coding standards, conventions, and code review checklist
---

# Arachne — Coding Standards

## Python Code Style

### General
- Target Python 3.11+
- Max line length: 120 characters (enforced by ruff)
- Double quotes for strings
- 4-space indentation

### Imports
```python
# Use absolute imports, no TYPE_CHECKING guards
from arachne.config import Settings
```
**Never** use ``.

### F-Strings Only
```python
# YES
message = f"Node {node_id} failed after {elapsed:.2f}s"

# NO
message = "Node {} failed after {:.2f}s".format(node_id, elapsed)
message = "Node %s failed" % node_id
```

### Error Handling
```python
# YES - fix root causes, raise specific errors
try:
    result = await node_mod.execute(**inputs)
except TimeoutError:
    logger.error(f"Node {node_id} timed out after {timeout}s")
    raise NodeTimeoutError(f"Node {node_id} exceeded {timeout}s") from None

# NO - never silently swallow exceptions
try:
    do_something()
except Exception:
    pass  # NEVER do this for functional code
```

### Pydantic Models
```python
from pydantic import BaseModel, Field

class NodeResult(BaseModel):
    node_id: str
    status: ResultStatus = ResultStatus.COMPLETED
    output: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
```

### DSPy Modules
```python
class GraphWeaverSignature(dspy.Signature):
    \"\"\"Docstring becomes the prompt instructions.\"\"\"
    goal: str = dspy.InputField()
    topology: GraphTopology = dspy.OutputField()

class GraphWeaver(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.weave = dspy.ChainOfThought(GraphWeaverSignature)

    def forward(self, goal: str) -> dspy.Prediction:
        with dspy.settings.context(temperature=0.1):
            return self.weave(goal=goal)
```

## Testing
- All new code must have tests
- Use descriptive test names: `test_web_search_returns_empty_string_on_no_results`
- Mock external APIs and LLM calls
- Use `pytest.mark.asyncio` decorator for async tests

## Code Review Checklist
- [ ] New code is tested
- [ ] ruff passes: `uv run ruff check src/arachne/`
- [ ] f-strings used (no .format or %)
- [ ] No TYPE_CHECKING guards (use absolute imports)
- [ ] No secrets or API keys in code
- [ ] Docstrings on all public functions
- [ ] Changes match a P0/P1 task from ROADMAP.md
