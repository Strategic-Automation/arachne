"""OutputPort -- abstraction decoupling core domain from terminal I/O.

Provides a Protocol that all core modules use for user-facing output
and interaction, plus concrete implementations for terminal (Rich)
and headless (logging-only) environments.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from arachne.topologies.schema import GraphTopology, NodeDef

logger = logging.getLogger(__name__)


@runtime_checkable
class OutputPort(Protocol):
    """Interface for all user-facing output and interaction.

    Inject this into core modules instead of importing rich/questionary
    directly, so that Arachne can operate in headless environments
    (web servers, batch processors, test harnesses).
    """

    def status(self, message: str, level: str = "info") -> None:
        """Display a status message to the user."""
        ...

    def display_topology(self, topology: GraphTopology, title: str = "") -> None:
        """Render a graph topology visualization."""
        ...

    def display_outputs(self, run_result: Any, topology: GraphTopology) -> None:
        """Display execution results to the user."""
        ...

    def ask_user(self, node_def: NodeDef, inputs: dict[str, Any]) -> str:
        """Prompt the user for input and return their response."""
        ...


class RichTerminalOutput:
    """Concrete OutputPort using Rich + Questionary for terminal interaction."""

    def __init__(self) -> None:
        from rich.console import Console

        self._console = Console()

    @property
    def console(self):
        return self._console

    def status(self, message: str, level: str = "info") -> None:
        color = "cyan" if level == "info" else "red" if level == "error" else "yellow"
        self._console.print(f"\n[bold {color}]{message}[/bold {color}]")

    def display_topology(self, topology: GraphTopology, title: str = "") -> None:
        from arachne.cli.display import display_topology

        display_topology(topology, title=title or "[bold]Graph[/bold]")

    def display_outputs(self, run_result: Any, topology: GraphTopology) -> None:
        from arachne.cli.display import display_outputs

        display_outputs(run_result, topology)

    def ask_user(self, node_def: NodeDef, inputs: dict[str, Any]) -> str:
        import questionary

        from arachne.topologies.schema import QuestionType

        q_obj = getattr(node_def, "question", None)
        if not q_obj:
            return questionary.text("  Please provide input:").ask()

        # Robust extraction for both Pydantic models and plain dictionaries
        if isinstance(q_obj, dict):
            prompt_text = q_obj.get("query", str(q_obj))
            q_type = q_obj.get("type", QuestionType.TEXT)
            choices = q_obj.get("choices", [])
            default = q_obj.get("default", "")
        else:
            prompt_text = getattr(q_obj, "query", str(q_obj))
            q_type = getattr(q_obj, "type", QuestionType.TEXT)
            choices = getattr(q_obj, "choices", [])
            default = getattr(q_obj, "default", "")

        # Safe placeholder substitution (no str.format parsing)
        def _substitute(text: str, values: dict[str, Any]) -> str:
            result = text
            for key, value in values.items():
                result = result.replace(f"{{{key}}}", str(value))
            return result

        prompt_text = _substitute(prompt_text, inputs)
        choices = [_substitute(str(c), inputs) for c in choices]
        default = _substitute(str(default), inputs) if default else default

        if q_type == QuestionType.SELECT and choices:
            return questionary.select(prompt_text, choices=choices, default=default or choices[0]).ask()
        if q_type == QuestionType.CONFIRM:
            val = questionary.confirm(prompt_text, default=str(default).lower() == "true" if default else True).ask()
            return str(val)

        return questionary.text(prompt_text, default=str(default)).ask()


class HeadlessOutput:
    """Concrete OutputPort for non-interactive / headless environments.

    All output goes to structured logging; ask_user raises RuntimeError
    to prevent blocking on missing user input.
    """

    def status(self, message: str, level: str = "info") -> None:
        log_level = logging.INFO if level == "info" else logging.ERROR if level == "error" else logging.WARNING
        logger.log(log_level, "[arachne] %s", message)

    def display_topology(self, topology: GraphTopology, title: str = "") -> None:
        logger.debug("[arachne] Topology: %s (%d nodes)", topology.name, len(topology.nodes))

    def display_outputs(self, run_result: Any, topology: GraphTopology) -> None:
        logger.debug("[arachne] Run complete: success=%s", getattr(run_result, "success", "?"))

    def ask_user(self, node_def: NodeDef, inputs: dict[str, Any]) -> str:
        raise RuntimeError(
            "HeadlessOutput cannot prompt for user input. "
            "Use an interactive OutputPort or provide pre-collected answers."
        )
