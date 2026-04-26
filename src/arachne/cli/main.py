import contextlib
import json as _json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import questionary
import typer
import yaml
from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from arachne.cli.display import display_results, display_topology, show_banner
from arachne.config import Settings, configure_dspy
from arachne.core import Arachne
from arachne.tools import is_builtin as is_tool_builtin
from arachne.tools import list_tools as get_tool_names
from arachne.topologies.schema import GoalDefinition, GraphTopology
from arachne.utils import goal_hash

# Search for .env: first current dir, then the arachne project directory
_env_paths = [Path.cwd() / ".env", Path(__file__).parent.parent.parent.parent / ".env"]
_vals = {}
for p in _env_paths:
    if p.exists():
        _vals = dotenv_values(p)
        break

# Map LANGFUSE_HOST -> LANGFUSE_BASE_URL
if _vals.get("LANGFUSE_HOST") and not _vals.get("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_BASE_URL"] = _vals["LANGFUSE_HOST"]

for _k in ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASE_URL", "LANGFUSE_HOST"]:
    if _vals.get(_k):
        os.environ[_k] = _vals[_k]

if not os.environ.get("LANGFUSE_BASE_URL") and not os.environ.get("LANGFUSE_HOST"):
    os.environ["LANGFUSE_BASE_URL"] = "https://cloud.langfuse.com"

app = typer.Typer(
    name="arachne",
    help="Runtime harness for production AI agents -- describe your goal, Arachne weaves the graph.",
    add_completion=False,
)

console = Console()


def _setup_logging() -> None:
    """Silence noisy third-party loggers."""
    # Loggers to suppress entirely (set to CRITICAL, only show critical failures)
    silent_loggers = [
        # HTTP/network libraries
        "primp",
        "ddgs",
        "httpcore",
        "httpx",
        "urllib3",
        # Search engine scrapers
        "google_scraper",
        "duckduckgo_search",
        "wikipedia_search",
        "arxiv_search",
        # DSPy framework
        "dspy",
        # Browser automation stack
        "playwright",
        "playwright.async_api",
        "playwright.async_api._impl",
        "PIL",
        "browser_use",
        "browser_use.agent",
        "browser_use.agent.service",
        "browser_use.agent.message_manager",
        "browser_use.agent.prompts",
        "browser_use.browser",
        "browser_use.browser.context",
        "browser_use.browser.page",
        "browser_use.tools",
        "browser_use.dom",
        "browser_use.dom.service",
        "browser_use.dom.serializer",
        "browser_use.dom.enhanced_snapshot",
        "browser_use.llm",
        "browser_use.llm.openai",
        "browser_use.llm.google",
        "browser_use.observability",
        # browser_use cross-platform dependencies
        "bubus",
        "cdp_use",
        "cdp_use.client",
        "cdp_use.cdp",
        "cdp_use.cdp.registry",
        "websockets",
        "websockets.client",
        "websockets.protocol",
        # MCP integration
        "mcp",
        "mcp.server",
        "mcp.client",
        "mcp.server.fastmcp",
        # Langfuse telemetry
        "langfuse",
        "langfuse.client",
        # Agent/BrowserSession aliases used by browser_use
        "Agent",
        "BrowserSession",
    ]
    for logger_name in silent_loggers:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)

    # Loggers to reduce to WARNING (still show errors/warnings)
    warning_loggers = [
        "openai",  # API errors still visible, but not debug/info
        "dspy.modules",
    ]
    for logger_name in warning_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Silence arachne's own loggers — status is shown via Rich UI, not raw logging
    for logger_name in [
        "arachne.execution.manager",
        "arachne.topologies.weaver",
        "arachne.topologies.node_executor",
        "arachne.topologies.wave_executor",
        "arachne.runtime.evaluator",
        "arachne.runtime.auto_healer",
        "arachne.runtime.provision",
        "arachne.runtime.token_manager",
        "arachne.core",
    ]:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)

    # Configure root logger
    logging.basicConfig(level=logging.WARNING, format="%(message)s")


# Logging is configured on first use via _ensure_logging(), not at import time.
# This prevents library consumers from having their loggers silenced.
_logging_initialized: bool = False


def _ensure_logging() -> None:
    """Configure logging lazily on first CLI invocation (not at import time)."""
    global _logging_initialized
    if _logging_initialized:
        return
    _logging_initialized = True
    _setup_logging()


def human_ts(ts: float) -> str:
    diff = int(time.time() - ts)
    if diff < 60:
        return f"{diff}s ago"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def display_session_info(settings: Settings) -> None:
    """Display resolved model limits and backend source in a clean panel."""
    from arachne.config import get_model_limits

    limits = get_model_limits(settings.llm_model, settings)

    # Format capability badges
    fc_badge = "[green]✓ Native FC[/green]" if limits.supports_function_calling else "[dim]✗ Native FC[/dim]"
    so_badge = "[green]✓ JSON Out[/green]" if limits.supports_structured_output else "[dim]✗ JSON Out[/dim]"

    table = Table(box=None, padding=(0, 2))
    table.add_column("Type", style="bold cyan")
    table.add_column("Model ID", style="bold green")
    table.add_column("Backend", style="cyan")
    table.add_column("Context Window", style="yellow")
    table.add_column("Capabilities", style="magenta")
    table.add_column("Detection", style="dim italic")

    table.add_row(
        "Main",
        settings.llm_model,
        settings.llm_backend,
        f"{limits.context_window:,}",
        f"{fc_badge} {so_badge}",
        limits.source,
    )

    # Weaver demos row
    from arachne.optimizers.weaver_compiler import has_compiled_demos

    demos_badge = "[green]✓ Loaded[/green]" if has_compiled_demos() else "[dim]—[/dim]"
    table.add_row(
        "Weaver",
        "BootstrapFewShot",
        "dsp.save/load",
        "",
        demos_badge,
        "compiled" if has_compiled_demos() else "uncompiled",
    )

    if settings.browser_llm_model:
        browser_limits = get_model_limits(settings.browser_llm_model, settings)
        b_fc_badge = (
            "[green]✓ Native FC[/green]" if browser_limits.supports_function_calling else "[dim]✗ Native FC[/dim]"
        )
        b_so_badge = (
            "[green]✓ JSON Out[/green]" if browser_limits.supports_structured_output else "[dim]✗ JSON Out[/dim]"
        )

        table.add_row(
            "Browsing",
            settings.browser_llm_model,
            settings.browser_llm_backend or settings.llm_backend,
            f"{browser_limits.context_window:,}",
            f"{b_fc_badge} {b_so_badge}",
            browser_limits.source,
        )

    console.print(Panel(table, title="[bold]Session Configuration[/bold]", border_style="blue"))


@app.command()
def weave(
    goal: str | None = typer.Argument(None, help="The natural language goal to weave"),
    yaml_config: str = typer.Option("arachne.yaml", "--config", "-c", help="Path to config file"),
    max_tokens: int | None = typer.Option(None, "--max-tokens", help="Override max generation tokens"),
    output: str | None = typer.Option(None, "--output", "-o", help="Save topology to JSON file"),
) -> None:
    if not goal:
        goal = questionary.text("Describe your goal to weave:").ask()
        if not goal:
            return

    console.print(Panel(f"[bold]Goal:[/bold] {goal}", style="bold yellow"))

    settings = Settings.from_yaml(yaml_config)
    if max_tokens:
        settings.llm_max_tokens = max_tokens

    _ensure_logging()
    configure_dspy(settings)
    display_session_info(settings)
    from arachne.ports import RichTerminalOutput

    arachne = Arachne(settings=settings, output=RichTerminalOutput())

    with console.status("[bold cyan]Weaving agent graph...", spinner="dots"):
        topology = arachne.weave(goal=goal)

    display_topology(topology, title="[bold]Generated Agent Graph[/bold]")

    if output:
        with open(output, "w") as f:
            _json.dump(topology.model_dump(mode="json"), f, indent=2)
        console.print(f"[dim]Saved topology to {output}[/dim]")


@app.command()
def run(
    goal: str | None = typer.Argument(None, help="The natural language goal to execute"),
    yaml_config: str = typer.Option("arachne.yaml", "--config", "-c", help="Path to config file"),
    max_tokens: int | None = typer.Option(None, "--max-tokens", help="Override max generation tokens"),
    goal_yaml: str | None = typer.Option(None, "--goal-yaml", help="Path to detailed goal YAML with constraints"),
    max_retries: int = typer.Option(3, "--max-retries", "-r", help="Max failure retries for auto-healing"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Review graph before execution"),
    confidence_threshold: float = typer.Option(
        0.8, "--confidence", "-c", help="Minimum semantic confidence before HITL"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
    fresh: bool = typer.Option(False, "--fresh", help="Start a new session even if a previous one exists"),
) -> None:
    if not goal:
        goal = questionary.text("Describe your goal to execute:").ask()
        if not goal:
            return

    console.print(Panel(f"[bold]Goal:[/bold] {goal}", style="bold yellow"))

    settings = Settings.from_yaml(yaml_config)
    if max_tokens:
        settings.llm_max_tokens = max_tokens

    _ensure_logging()
    configure_dspy(settings)
    display_session_info(settings)

    goal_definition = None
    if goal_yaml:
        with open(goal_yaml) as f:
            goal_data = yaml.safe_load(f)

        # Fallback objective from CLI arg if not present in YAML
        if "objective" not in goal_data:
            goal_data["objective"] = goal

        goal_definition = GoalDefinition.model_validate(goal_data)
        console.print(
            f"[dim]Loaded goal with {len(goal_definition.constraints)} constraint(s) and {len(goal_definition.success_criteria)} success criteria.[/dim]"
        )

    arachne = Arachne(
        settings=settings,
        goal_definition=goal_definition,
        max_retries=max_retries,
        interactive=interactive,
        confidence_threshold=confidence_threshold,
    )

    # Weave the graph once and pass it to forward() to avoid redundant LLM calls
    pre_woven_topology = None
    if not interactive:
        with console.status("[bold cyan]Weaving agent graph...", spinner="dots"):
            pre_woven_topology = arachne.weave(goal=goal)
        display_topology(pre_woven_topology, title="[bold]Planned Graph[/bold]")
        console.print("[dim]Executing graph...[/dim]")

    try:
        result = arachne(goal=goal, topology=pre_woven_topology, fresh=fresh)
        run_result = result.run_result
        topology = getattr(result, "topology", None)

        if json_output:
            print(_json.dumps(run_result.model_dump(mode="json"), indent=2))
        else:
            display_results(run_result, topology)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    finally:
        try:
            if settings.langfuse.enabled:
                from langfuse import get_client

                get_client().flush()
        except Exception:
            pass


@app.command("rm")
def delete_session(session_id: str) -> None:
    """Delete a specific Arachne session."""
    from arachne.sessions import default_session_dir

    session_path = default_session_dir() / session_id
    if not session_path.exists():
        console.print(f"[red]Session '{session_id}' not found.[/red]")
        return

    if typer.confirm(f"Are you sure you want to delete session '{session_id}'?"):
        shutil.rmtree(session_path)
        console.print(f"[green]Session '{session_id}' deleted.[/green]")


@app.command("clean")
def clean_sessions(
    older_than_days: int = typer.Option(None, "--older-than", "-d", help="Delete sessions older than N days"),
    failed_only: bool = typer.Option(False, "--failed", "-f", help="Only delete failed sessions"),
) -> None:
    """Delete old or failed sessions to free up disk space."""
    from arachne.sessions import default_session_dir

    base = default_session_dir()
    if not base.exists():
        console.print("[dim]No sessions found.[/dim]")
        return

    cutoff = time.time() - (older_than_days * 86400) if older_than_days else 0

    for session_dir in sorted(base.iterdir()):
        if not session_dir.is_dir():
            continue

        state_path = session_dir / "state.json"
        is_failed = True
        if state_path.exists():
            try:
                state = _json.loads(state_path.read_text())
                results = state.get("node_results", [])
                is_failed = any(r.get("status") == "failed" for r in results)
            except Exception:
                is_failed = False

        mtime = session_dir.stat().st_mtime
        too_old = mtime < cutoff if older_than_days else False

        if (failed_only and is_failed) or (older_than_days and too_old):
            console.print(f"  Deleting [yellow]{session_dir.name}[/yellow]...")
            shutil.rmtree(session_dir)

    console.print("[green]Cleanup complete.[/green]")


@app.command("ls")
def ls_sessions(limit: int = typer.Option(None, "--limit", "-n", help="Limit number of sessions shown")) -> None:
    """List all Arachne sessions with their status."""
    from arachne.sessions import default_session_dir

    base = default_session_dir()
    if not base.exists():
        console.print("[dim]No sessions found.[/dim]")
        return

    sessions = sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    if limit:
        sessions = sessions[:limit]

    table = Table(show_header=True)
    table.add_column("Session ID")
    table.add_column("Created")
    table.add_column("Goal")
    table.add_column("Graph ID", style="dim")
    table.add_column("Status")
    table.add_column("Nodes")

    for s in sessions:
        sid, goal, graph_id, status, total = s.name, "?", "?", "?", 0
        created = human_ts(s.stat().st_mtime)

        inputs_path = s / "inputs.json"
        if inputs_path.exists():
            try:
                inputs = _json.loads(inputs_path.read_text())
                goal = inputs.get("goal", "?")[:40]
                # Graph ID: shorter (12 chars) for display; same normalisation as cache filenames
                graph_id = goal_hash(goal, length=12)
            except Exception:
                pass

        state_path = s / "state.json"
        if state_path.exists():
            try:
                state = _json.loads(state_path.read_text())
                results = state.get("node_results", [])
                total = len(results)
                if results:
                    statuses = [r.get("status", "") for r in results]
                    if all(st == "completed" for st in statuses):
                        status = "[green]completed[/green]"
                    elif any(st == "failed" for st in statuses):
                        status = "[red]failed[/red]"
                    else:
                        status = "[blue]running[/blue]"
            except Exception:
                pass

        graph_path = s / "graph.json"
        if graph_path.exists():
            with contextlib.suppress(Exception):
                # Ensure the graph file is at least valid JSON
                _json.loads(graph_path.read_text())

        table.add_row(sid, created, goal, graph_id, status, str(total))

    console.print(table)
    console.print(
        "\n[dim]Use [bold white]arachne graphs[/bold white] to see cached topologies, "
        "[bold white]arachne show <id>[/bold white] to visualize, "
        "[bold white]arachne cat <id>[/bold white] to view output, "
        "or [bold white]arachne rerun <id>[/bold white] to execute again.[/dim]"
    )


@app.command()
def resume(
    session_id: str = typer.Argument(..., help="The session ID to resume (e.g., 'run_20260405_101545')"),
    max_retries: int = typer.Option(3, "--max-retries", "-r", help="Max failure retries for auto-healing"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Review graph before resuming"),
    confidence_threshold: float = typer.Option(
        0.8, "--confidence", "-c", help="Minimum semantic confidence before HITL"
    ),
) -> None:
    """Resume a previously failed or partial session with auto-healing."""
    from arachne.sessions import default_session_dir
    from arachne.sessions.manager import Session

    base = default_session_dir() / session_id
    if not base.exists():
        console.print(f"[bold red]Error:[/bold red] Session '{session_id}' not found.")
        sys.exit(1)

    graph_path = base / "graph.json"
    if not graph_path.exists():
        console.print("[bold red]Error:[/bold red] No 'graph.json' found in session.")
        sys.exit(1)

    try:
        topology = GraphTopology.model_validate(_json.loads(graph_path.read_text()))
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to load graph: {e}")
        sys.exit(1)

    display_topology(topology, title=f"[bold]Resuming Session: {session_id}[/bold]")

    settings = Settings.from_yaml()
    _ensure_logging()
    configure_dspy(settings)
    from arachne.ports import RichTerminalOutput

    arachne = Arachne(
        settings=settings,
        max_retries=max_retries,
        interactive=interactive,
        confidence_threshold=confidence_threshold,
        output=RichTerminalOutput(),
    )
    arachne._session = Session(session_id, settings.session.directory)

    if interactive:
        choice = questionary.select("  Action", choices=["Resume", "Cancel", "Edit"]).ask()
        if choice == "Cancel":
            return
        if choice == "Edit":
            mods = questionary.text("What changes?").ask()
            topology = arachne.weave(goal=arachne._session.load_inputs().get("goal", ""), modifications=mods)

    try:
        goal = arachne._session.load_inputs().get("goal", "Resumed goal")
        result = arachne._execute(goal, topology)
        display_results(result.run_result, topology)
    except Exception as e:
        console.print(f"\n[bold red]Error during resume:[/bold red] {e}")
        sys.exit(1)


@app.command("graphs")
def list_graphs() -> None:
    """List all cached topologies that have been woven and validated."""
    settings = Settings.from_yaml()
    # Cache dir logic matching core.py
    cache_dir = settings.session.directory.parent / "topology-cache"
    if not cache_dir.exists():
        console.print("[dim]No cached graphs found.[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("Graph ID (Hash)", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Objective/Goal")
    table.add_column("Nodes", justify="right")

    for p in cache_dir.iterdir():
        if p.suffix != ".json":
            continue
        try:
            topo = GraphTopology.model_validate(_json.loads(p.read_text()))
            table.add_row(
                p.stem,
                topo.name,
                topo.objective[:60] + "..." if len(topo.objective) > 60 else topo.objective,
                str(len(topo.nodes)),
            )
        except Exception:
            continue

    console.print(table)
    console.print("\n[dim]Use [bold white]arachne show <graph-id>[/bold white] to view details.[/dim]")


@app.command()
def show(id_or_sid: str = typer.Argument(..., help="Session ID (run_...) or Graph ID (hash)")) -> None:
    """Visualize a graph topology from a session or the cache."""
    from arachne.sessions import default_session_dir

    settings = Settings.from_yaml()
    cache_dir = settings.session.directory.parent / "topology-cache"

    path = None
    # 1. Check if it's a session
    session_path = default_session_dir() / id_or_sid
    if session_path.exists():
        path = session_path / "graph.json"

    # 2. Check if it's a cached graph
    if not path or not path.exists():
        cache_path = cache_dir / f"{id_or_sid}.json"
        if cache_path.exists():
            path = cache_path

    if not path or not path.exists():
        console.print(f"[bold red]Error:[/bold red] '{id_or_sid}' not found as session or cached graph.")
        sys.exit(1)

    try:
        topology = GraphTopology.model_validate(_json.loads(path.read_text()))
        display_topology(topology, title=f"[bold]Topology: {id_or_sid}[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to load graph: {e}")
        sys.exit(1)


@app.command()
def rerun(
    id_or_sid: str = typer.Argument(..., help="Session ID or Graph ID to rerun"),
    goal: str | None = typer.Option(None, "--goal", help="Override goal for this graph"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Review before execution"),
) -> None:
    """Execute a fresh run using a specific graph (from session or cache)."""
    from arachne.sessions import default_session_dir

    settings = Settings.from_yaml()
    cache_dir = settings.session.directory.parent / "topology-cache"

    topology_path = None
    input_goal = goal

    # Resolve topology and goal
    session_path = default_session_dir() / id_or_sid
    if session_path.exists():
        topology_path = session_path / "graph.json"
        if not input_goal:
            inputs_path = session_path / "inputs.json"
            if inputs_path.exists():
                input_goal = _json.loads(inputs_path.read_text()).get("goal")

    if not topology_path or not topology_path.exists():
        cache_path = cache_dir / f"{id_or_sid}.json"
        if cache_path.exists():
            topology_path = cache_path
            if not input_goal:
                topo_data = _json.loads(topology_path.read_text())
                input_goal = topo_data.get("objective")

    if not topology_path or not topology_path.exists():
        console.print(f"[bold red]Error:[/bold red] Could not find graph for '{id_or_sid}'.")
        sys.exit(1)

    if not input_goal:
        console.print("[bold red]Error:[/bold red] Could not determine goal. Use --goal to provide one.")
        sys.exit(1)

    console.print(
        Panel(f"[bold]Rerunning Goal:[/bold] {input_goal}\n[dim]Using graph: {id_or_sid}[/dim]", style="bold cyan")
    )

    _ensure_logging()
    configure_dspy(settings)
    from arachne.ports import RichTerminalOutput

    arachne = Arachne(settings=settings, interactive=interactive, output=RichTerminalOutput())

    try:
        topology = GraphTopology.model_validate(_json.loads(topology_path.read_text()))
        result = arachne(goal=input_goal, topology=topology)
        display_results(result.run_result, topology)
    except Exception as e:
        console.print(f"\n[bold red]Error during rerun:[/bold red] {e}")
        sys.exit(1)


@app.command("cat")
def cat_session(
    session_id: str = typer.Argument("last", help="Session ID to view output for. Uses most recent if 'last'."),
) -> None:
    """Print the final result nodes of a past session in Markdown."""
    from rich.markdown import Markdown

    from arachne.sessions import default_session_dir

    base = default_session_dir()
    if session_id == "last":
        sessions = sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            console.print("[red]No sessions found.[/red]")
            return
        session_id = sessions[0].name

    session_path = base / session_id
    state_path = session_path / "state.json"
    graph_path = session_path / "graph.json"

    if not state_path.exists():
        console.print(f"[bold red]Error:[/bold red] No results found for session '{session_id}'.")
        return

    try:
        state = _json.loads(state_path.read_text())
        results = state.get("node_results", [])

        # Identify sink nodes to show final output
        topology = None
        if graph_path.exists():
            topology = GraphTopology.model_validate(_json.loads(graph_path.read_text()))

        sink_ids = set(topology.sink_nodes) if topology else set()

        # If we have results, show the ones that are sink nodes OR just the latest if no graph
        found_any = False
        for res in results:
            nid = res.get("node_id")
            if not sink_ids or nid in sink_ids:
                output = res.get("output", {})
                # Display all values in output dict
                for key, val in output.items():
                    console.print(Panel(Markdown(str(val)), title=f"[bold]{nid} ({key})[/bold]", border_style="cyan"))
                    found_any = True

        if not found_any:
            console.print("[yellow]No final outputs found in this session.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error loading results:[/bold red] {e}")


@app.command("config")
def config_cmd(
    action: str = typer.Argument("list", help="Action: 'list' or 'set'"),
    key: str | None = typer.Argument(None),
    value: str | None = typer.Argument(None),
) -> None:
    """Manage calculation settings and .env variables."""
    settings = Settings.from_yaml()

    if action == "list":
        table = Table(title="[bold]Arachne Configuration[/bold]")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        # Filter out complex objects or secrets if needed, but for now just show all
        for k, v in settings.model_dump().items():
            val = ("***" if v else "[red]unset[/red]") if k == "llm_api_key" else str(v)
            table.add_row(k, val)
        console.print(table)

    elif action == "set":
        if not key or not value:
            console.print("[red]Usage: arachne config set <KEY> <VALUE>[/red]")
            return

        # Update .env file
        env_path = Path.cwd() / ".env"
        if not env_path.exists():
            env_path = Path(__file__).parent.parent.parent.parent / ".env"

        lines = []
        found = False
        if env_path.exists():
            lines = env_path.read_text().splitlines()

        new_line = f"{key.upper()}={value}"
        new_lines = []
        for line in lines:
            if line.startswith(f"{key.upper()}="):
                new_lines.append(new_line)
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(new_line)

        env_path.write_text("\n".join(new_lines) + "\n")
        console.print(f"[green]Updated {key.upper()} in {env_path}[/green]")
    else:
        console.print(f"[red]Unknown action '{action}'. Use 'list' or 'set'.[/red]")


@app.command("compile-weaver")
def compile_weaver(
    teacher_model: str | None = typer.Option(None, "--teacher", "-t", help="Teacher model for bootstrapping"),
    max_demos: int = typer.Option(4, "--max-demos", "-n", help="Max bootstrapped demonstrations"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="Output directory for compiled predictors"),
) -> None:
    """Compile all GraphWeaver sub-predictors with BootstrapFewShot.

    Compiles three sub-predictors (weave, selector, clarifier) using
    BootstrapFewShot optimization. The compiled demos are saved to disk
    via DSPy's native save() and auto-loaded at runtime.

    Example:
        uv run arachne compile-weaver --teacher openrouter/qwen/qwen3.6-plus:free
    """
    from arachne.optimizers.weaver_compiler import (
        CLARIFIER_COMPILED,
        SELECTOR_COMPILED,
        WEAVE_COMPILED,
    )
    from arachne.optimizers.weaver_compiler import (
        compile_weaver as do_compile,
    )

    _ensure_logging()
    settings = Settings.from_yaml()

    console.print("[bold cyan]Compiling GraphWeaver sub-predictors with BootstrapFewShot...[/bold cyan]")
    console.print("[dim]  • weave (topology generation)[/dim]")
    console.print("[dim]  • selector (category selection)[/dim]")
    console.print("[dim]  • clarifier (goal completeness)[/dim]")

    result_dir = do_compile(
        settings=settings,
        teacher_model=teacher_model,
        max_demos=max_demos,
        output_dir=output_dir,
    )
    console.print(f"\n[green]✓[/green] All compiled predictors saved to [bold]{result_dir}/[/bold]")
    console.print(f"  [green]✓[/green] {WEAVE_COMPILED} (topology generation)")
    console.print(f"  [green]✓[/green] {SELECTOR_COMPILED} (category selection)")
    console.print(f"  [green]✓[/green] {CLARIFIER_COMPILED} (goal completeness)")
    console.print("[dim]All demos will be auto-loaded at runtime (no config needed).[/dim]")


@app.command()
def info() -> None:
    """Show Arachne configuration and active LLM."""
    settings = Settings.from_yaml()
    api_key_set = bool(settings.llm_api_key.get_secret_value())
    console.print(
        Panel(
            f"[bold]Backend:[/bold]  {settings.llm_backend}\n"
            f"[bold]Model:[/bold]   {settings.llm_model}\n"
            f"[bold]Max Retries:[/bold] 3\n"
            f"[bold]Cost Limit:[/bold]  ${settings.cost.default_max_usd}",
            title="[bold]Arachne Configuration[/bold]",
            border_style="green",
        )
    )
    console.print(f"[bold]API Key:[/bold] {'[green]set[/green]' if api_key_set else '[yellow]not set[/yellow]'}")


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context, list_tools: bool = typer.Option(False, "--list-tools", help="List all available tools.")
) -> None:
    """Arachne -- Runtime harness for production AI agents."""
    _ensure_logging()
    show_banner()
    if list_tools:
        names = get_tool_names()
        table = Table(title="[bold]Available Tools[/bold]", box=None)
        table.add_column("Tool Name", style="cyan")
        table.add_column("Type", style="green")
        for name in names:
            table.add_row(name, "Built-in" if is_tool_builtin(name) else "Custom")
        console.print(table)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def main() -> None:
    app()
