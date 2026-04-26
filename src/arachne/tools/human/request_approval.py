"""Tool for requesting approval from human."""

import threading

from rich.console import Console
from rich.prompt import Prompt

_console = Console()
_console_lock = threading.Lock()


def request_approval(review_item: str, *, details: str = "", **kwargs) -> str:
    """Request user approval for a specific item or stage."""
    with _console_lock:
        context_parts = []
        if details:
            context_parts.append(details)

        for key, value in kwargs.items():
            if value and isinstance(value, str) and value not in context_parts:
                context_parts.append(f"\n--- {key} ---\n{value[:2000]}")

        context_text = "\n".join(context_parts)

        if context_text:
            _console.print(f"\n[bold magenta]Review Required: {review_item}[/bold magenta]")
            _console.print(context_text[:3000])
        else:
            _console.print(f"\n[bold magenta]Review Required: {review_item}[/bold magenta]")
            _console.print("[dim]No content provided for review[/dim]")

        choice = Prompt.ask("  Action", choices=["approve", "edit", "cancel"], default="approve")

        if choice == "approve":
            return "Approved"
        if choice == "edit":
            edit = Prompt.ask("  What changes would you like?")
            return f"Edit requested: {edit}"
        return "Cancelled by user"
