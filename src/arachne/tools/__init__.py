"""Tool registry -- built-in tools and dynamic custom tools."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import dspy

if TYPE_CHECKING:
    from arachne.core import Settings

# 1. System
# 2. Execution
from arachne.tools.execution.python_sandbox import python_sandbox
from arachne.tools.human.request_approval import request_approval

# 5. Human
from arachne.tools.human.request_context import request_context

# 7. Lifecycle
from arachne.tools.lifecycle.checkpoints import list_checkpoints, load_checkpoint, save_checkpoint

# 3. Math
from arachne.tools.math.calculator import evaluate_math

# 6. Memory
from arachne.tools.memory.operations import clear_memory, search_memory, write_memory
from arachne.tools.session.list_files import list_session_files
from arachne.tools.session.read_file import read_session_file

# 8. Session
from arachne.tools.session.status import get_session_status, list_sessions
from arachne.tools.skills.get_details import get_skill_details
from arachne.tools.skills.list_categories import list_skill_categories

# 9. Skills
from arachne.tools.skills.search import search_skills

# For tool spillover protection
from arachne.tools.spillover import with_spillover
from arachne.tools.system.file_read import read_file
from arachne.tools.system.file_write import write_local_file
from arachne.tools.system.shell import shell_exec
from arachne.tools.system.system_time import get_current_time

# 4. Web
from arachne.tools.web.arxiv_search import arxiv_search_async
from arachne.tools.web.browser_visit import browser_visit_async
from arachne.tools.web.deep_research import deep_research_async
from arachne.tools.web.duckduckgo_search import duckduckgo_search_async
from arachne.tools.web.google_scraper import google_search_async
from arachne.tools.web.jina import jina_search_async
from arachne.tools.web.screenshot import take_screenshot_async
from arachne.tools.web.search_history import get_previous_searches
from arachne.tools.web.wikipedia_search import wikipedia_search_async

# ── Registry ─────────────────────────────────────────────────────────

_BUILTIN_TOOLS: dict[str, object] = {
    # System
    "read_file": read_file,
    "write_file": write_local_file,
    "write_local_file": write_local_file,
    "shell_exec": shell_exec,
    "get_current_time": get_current_time,
    # Execution
    "python_sandbox": python_sandbox,
    # Math
    "evaluate_math": evaluate_math,
    # Web & Browser (Triangulated & Agentic)
    "google_search_async": google_search_async,
    "duckduckgo_search_async": duckduckgo_search_async,
    "wikipedia_search_async": wikipedia_search_async,
    "arxiv_search_async": arxiv_search_async,
    "deep_research_async": deep_research_async,
    "browser_visit_async": browser_visit_async,
    "jina_search_async": jina_search_async,
    "take_screenshot_async": take_screenshot_async,
    "get_previous_searches": get_previous_searches,
    # Human-in-the-loop
    "request_context": request_context,
    "request_approval": request_approval,
    # Long-term Memory
    "write_memory": write_memory,
    "search_memory": search_memory,
    "clear_memory": clear_memory,
    # Session & Graph introspection
    "list_sessions": list_sessions,
    "get_session_status": get_session_status,
    "list_session_files": list_session_files,
    "read_session_file": read_session_file,
    # Crash recovery (Lifecycle)
    "save_checkpoint": save_checkpoint,
    "load_checkpoint": load_checkpoint,
    "list_checkpoints": list_checkpoints,
    # Skill Discovery
    "search_skills": search_skills,
    "get_skill_details": get_skill_details,
    "list_skill_categories": list_skill_categories,
}

_CUSTOM_TOOL_DIR: Path = Path.home() / ".local" / "share" / "arachne" / "tools" / "custom"


def initialize(tool_dir: Path | None = None) -> None:
    """Initialize custom tool directory."""
    global _CUSTOM_TOOL_DIR
    if tool_dir:
        _CUSTOM_TOOL_DIR = tool_dir
    _CUSTOM_TOOL_DIR.mkdir(parents=True, exist_ok=True)


def resolve_tool(name: str, settings: Settings | None = None) -> dspy.Tool | None:
    """Look up a tool by name. Checks built-ins first, then custom files.

    Args:
        name: Tool name to resolve.
        settings: Optional Settings instance (reserved for future use).
    """

    fn = _BUILTIN_TOOLS.get(name)
    if fn is not None:
        # Wrap it if it's not already wrapped, and if it's meant to be wrapped.
        # Actually `resolve_tool` wraps them anyway, as done in the previous implementation.
        return dspy.Tool(with_spillover(name, fn))

    # Check custom Python tools
    custom_path_py = _CUSTOM_TOOL_DIR / f"{name}.py"
    if custom_path_py.exists():
        spec = importlib.util.spec_from_file_location(name, custom_path_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, name, None) or getattr(mod, "run", None)
        if fn:
            return dspy.Tool(with_spillover(name, fn))

    return None


def exists(name: str) -> bool:
    """Check if a tool with this name exists (builtin or custom)."""
    if name in _BUILTIN_TOOLS:
        return True
    custom_path_py = _CUSTOM_TOOL_DIR / f"{name}.py"
    return custom_path_py.exists()


def is_builtin(name: str) -> bool:
    """Check if a tool is a built-in Arachne tool."""
    return name in _BUILTIN_TOOLS


def save_tool(name: str, code: str, description: str, ext: str = "py") -> Path:
    """Persist a new custom tool as a Python file."""
    _CUSTOM_TOOL_DIR.mkdir(parents=True, exist_ok=True)
    target = _CUSTOM_TOOL_DIR / f"{name}.{ext}"
    header = f'"""\n{description}\nAuto-generated by Arachne ToolMaker.\n"""\n'
    target.write_text(header + code)
    return target


# Tool availability checks: map tool name to a callable that takes Settings and returns bool.
_TOOL_AVAILABILITY_CHECKS: dict[str, Any] = {
    "google_search_async": lambda s: bool(s.serpapi_api_key or os.getenv("BRAVE_SEARCH_API_KEY")),
    "deep_research_async": lambda s: any(
        [
            s.browser_llm_api_key and s.browser_llm_api_key.get_secret_value(),
            s.llm_api_key and s.llm_api_key.get_secret_value(),
            os.getenv("BROWSER_LLM_API_KEY"),
            os.getenv("OPENROUTER_API_KEY"),
            os.getenv("OPENAI_API_KEY"),
        ]
    ),
}


def list_tools(settings: Settings | None = None) -> list[str]:
    """List all registered tool names (builtin + custom) that are currently available.

    Args:
        settings: Optional Settings instance to check tool availability.
    """
    if settings is None:
        from arachne.config import Settings as ConfigSettings

        settings = ConfigSettings()

    names = set()
    for name in _BUILTIN_TOOLS:
        check_fn = _TOOL_AVAILABILITY_CHECKS.get(name)
        if check_fn and not check_fn(settings):
            continue
        names.add(name)

    if _CUSTOM_TOOL_DIR.exists():
        for f in _CUSTOM_TOOL_DIR.iterdir():
            if f.suffix == ".py" and not f.name.startswith("_"):
                names.add(f.stem)
    return sorted(names)
