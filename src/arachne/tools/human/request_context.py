"""Tool for requesting context from human."""

import json
import threading

from rich.console import Console
from rich.prompt import Prompt

from arachne.runtime.context_store import put

_console = Console()
_console_lock = threading.Lock()


def request_context(questions: str = "", *, fields: list[str] | None = None) -> str:
    """Request essential information from the **user** to understand their goal."""
    from arachne.runtime.context_store import get_all

    if fields and not questions:
        existing = get_all()
        needed = [f for f in fields if f not in existing]
        if not needed:
            return json.dumps({f: existing[f] for f in fields})

        with _console_lock:
            _console.print("\n[bold yellow]Agent needs context from you:[/bold yellow]")
            answers = {}
            for field in needed:
                answer = Prompt.ask(f"  [cyan]{field}[/cyan]")
                answers[field] = answer
                put(field, answer)
            _console.print()
        return json.dumps(answers)

    if isinstance(questions, str):
        try:
            parsed = json.loads(questions)
            if isinstance(parsed, list):
                return request_context(fields=parsed)
            questions = str(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

    if questions:
        with _console_lock:
            _console.print(f"\n[bold magenta]{questions}[/bold magenta]")
            return Prompt.ask("  Your answer")

    return json.dumps(get_all() or {})
