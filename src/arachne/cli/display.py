"""Arachne CLI Display -- formatting and pretty-printing logic."""
# ruff: noqa: RUF001, W291

import os
import re

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from arachne.topologies.schema import GraphTopology, RunResult

console = Console()


def show_banner() -> None:
    """Display the Arachne ASCII banner with Rich styling."""
    banner_text = r"""
 █████  ██████   █████   ██████ ██   ██ ███    ██ ███████ 
██   ██ ██   ██ ██   ██ ██      ██   ██ ████   ██ ██      
███████ ██████  ███████ ██      ███████ ██ ██  ██ █████ 
██   ██ ██   ██ ██   ██ ██      ██   ██ ██  ██ ██ ██    
██   ██ ██   ██ ██   ██  ██████ ██   ██ ██   ████ ███████ 
"""
    console.print(f"[cyan]{banner_text}[/cyan]")
    console.print("[dim]  Runtime harness for production AI agents[/dim]\n")


def display_topology(topology: GraphTopology, *, title: str = "[bold]Agent Graph[/bold]") -> None:
    """Pretty-print the agent graph using Rich trees and tables."""
    console.print()

    # Graph overview table
    info = Table(show_header=False, box=None)
    info.add_row("[bold]Graph[/bold]", topology.name)
    info.add_row("[bold]Objective[/bold]", topology.objective)
    info.add_row("[bold]Nodes[/bold]", str(len(topology.nodes)))
    info.add_row("[bold]Edges[/bold]", str(len(topology.edges)))
    console.print(Panel(info, title=title, border_style="cyan"))

    # Topology tree
    tree = Tree(f"[bold]{topology.name}[/bold] ({topology.objective})")
    node_map = {n.id: n for n in topology.nodes}
    roots = set(topology.root_nodes)
    added = set()

    def add_node(node_id, parent_tree):
        if node_id in added:
            return
        added.add(node_id)
        node = node_map[node_id]
        branch = parent_tree.add(f"[bold]{node.id}[/bold]  ({node.role.value})")
        branch.add(Markdown(node.description))
        if node.skills:
            branch.add(f"[bold cyan]skills: {', '.join(node.skills)}[/bold cyan]")
        if node.inputs:
            branch.add(f"[dim]inputs: {', '.join(node.inputs)}[/dim]")
        branch.add(f"[dim]output: {node.output}[/dim]")

        for child_node in topology.nodes:
            if child_node.id in added:
                continue
            if any(child_node.id == e.target for e in topology.edges if e.source == node_id):
                add_node(child_node.id, branch)

    for root_id in sorted(roots):
        add_node(root_id, tree)

    console.print(tree)
    console.print()


def display_results(run_result: RunResult, topology: GraphTopology | None = None) -> None:
    """Show execution results and triangulated evaluation verdict."""
    display_execution_table(run_result)
    display_outputs(run_result, topology)


def display_execution_table(run_result: RunResult) -> None:
    """Show just the execution summary table and verdict."""
    console.print()

    # Build evaluation verdict line
    status_icon = "[green]✓[/green]" if run_result.success else "[red]✗[/red]"
    eval_lines = []

    # Always show Rule check (Level 0)
    if run_result.evaluation_source == "rule_constraint":
        eval_lines.append("[red]Fail[/red]")
    else:
        eval_lines.append("[green]Rules ✓[/green]")

    # Show semantic evaluation if present (Level 1)
    if run_result.confidence_score < 1.0:
        score_color = (
            "green" if run_result.confidence_score >= 0.8 else "yellow" if run_result.confidence_score >= 0.6 else "red"
        )
        eval_lines.append(f"[{score_color}]Semantic: {run_result.confidence_score:.2f}[/{score_color}]")

    # Show human escalation flag if triggered (Level 2)
    if hasattr(run_result, "requires_human") and run_result.requires_human:  # type: ignore[attr-defined]
        eval_lines.append("[bold yellow]→ HITL Escalation[/bold yellow]")

    verdict = " | ".join(eval_lines)
    header = (
        f"{status_icon}  "
        f"{run_result.attempts} attempt(s)  |  "
        f"{run_result.duration_seconds:.1f}s  |  "
        f"${run_result.total_cost_usd:.4f}"
    )
    if verdict:
        header = f"{header}  |  Eval: {verdict}"

    console.print(
        Panel(header, title="[bold]Execution Result[/bold]", border_style="green" if run_result.success else "red")
    )

    table = Table(show_header=True)
    table.add_column("Node")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Cost")
    table.add_column("Error")
    for nr in run_result.node_results:
        from arachne.topologies.schema import ResultStatus

        color = (
            "green" if nr.status == ResultStatus.COMPLETED else "red" if nr.status == ResultStatus.FAILED else "yellow"
        )
        table.add_row(
            nr.node_id,
            f"[{color}]{nr.status.value}[/{color}]",
            f"{nr.duration_seconds:.2f}s",
            f"${nr.cost_usd:.4f}" if nr.cost_usd > 0 else "--",
            f"[red]{nr.error}[/red]" if nr.error else "--",
        )
    console.print(table)


def display_outputs(run_result: RunResult, topology: GraphTopology | None = None) -> None:
    """Show the actual outputs of the nodes."""
    # Identify which nodes to showcase
    showcase_nodes = []
    if topology:
        leaf_node_ids = {n.id for n in topology.nodes} - {e.source for e in topology.edges}
        showcase_nodes = [nr for nr in run_result.node_results if nr.node_id in leaf_node_ids]
    elif run_result.node_results:
        showcase_nodes = [run_result.node_results[-1]]

    # If the leaf nodes are empty or have very little content, add upstream nodes with substantial content.
    # This handles cases like: generate_code → save_file, where save_file only says "Successfully wrote X"
    # but the actual generated content lives in generate_code's output.
    _showcase_ids = {nr.node_id for nr in showcase_nodes}
    _sink_content_len = sum(len(str(v)) for nr in showcase_nodes for v in nr.output.values()) if showcase_nodes else 0
    _sink_is_minimal = _sink_content_len < 200

    if _sink_is_minimal:
        for nr in reversed(run_result.node_results):
            if nr.node_id not in _showcase_ids and nr.output:
                # If it has more than 200 chars total, it's "substantial"
                total_len = sum(len(str(v)) for v in nr.output.values())
                if total_len > 200:
                    showcase_nodes.insert(0, nr)
                    break

    for nr in showcase_nodes:
        if not nr.output or all(not str(v).strip() for v in nr.output.values()):
            continue

        items = []
        expected_key = next((n.output for n in topology.nodes if n.id == nr.node_id), None) if topology else None
        meta_prefixes = {"trajectory", "rationale", "reasoning", "thought", "observation", "tool_name", "tool_args"}

        for k, v in nr.output.items():
            val_str = str(v).strip()
            if not val_str:
                continue

            k_lower = k.lower()
            if expected_key and k == expected_key:
                items.insert(0, (k, v))
                continue

            is_internal = any(k_lower.startswith(p) for p in meta_prefixes) or bool(re.search(r"_\d+$", k))
            if is_internal:
                continue

            items.append((k, v))

        def _get_renderables_for_value(v_val) -> list:
            _r = []
            if isinstance(v_val, str):
                v_stripped = v_val.strip()
                is_file = False
                if len(v_stripped) < 255:
                    try:
                        if os.path.isfile(v_stripped):
                            is_file = True
                    except Exception:
                        pass

                if is_file:
                    abs_path = os.path.abspath(v_stripped)
                    _r.append(f"file://{abs_path}")
                    try:
                        with open(v_stripped, encoding="utf-8") as f:
                            content = f.read(32000)
                            is_truncated = len(content) == 32000
                        _r.append(f"\n[bold cyan]📄 Contents of {os.path.basename(v_stripped)}:[/bold cyan]")
                        if v_stripped.endswith(".md"):
                            _r.append(Markdown(content))
                        else:
                            _r.append(content)
                        if is_truncated:
                            _r.append(
                                "\n[bold yellow]⚠ [TRUNCATED] - File content is too large for terminal preview.[/bold yellow]"
                            )
                        _r.append(
                            "[dim]--------------------------------------------------------------------------------[/dim]"
                        )
                    except Exception:
                        pass
                elif "#" in v_val or "-" in v_val or "*" in v_val or "[" in v_val:
                    _r.append(Markdown(v_val))
                else:
                    _r.append(v_val)
            else:
                _r.append(str(v_val))
            return _r

        renderables = []
        for k, v in items:
            renderables.append(f"[bold]{k}:[/bold]")
            renderables.extend(_get_renderables_for_value(v))

        if not renderables:
            for k, v in nr.output.items():
                if str(v).strip():
                    renderables.append(f"[bold]{k}:[/bold]")
                    renderables.extend(_get_renderables_for_value(v))

        console.print()
        console.print(Panel(Group(*renderables), title=f"[bold]Output ({nr.node_id})[/bold]", border_style="magenta"))


def review_graph(topology: GraphTopology, console: Console) -> dict | None:
    """Prompt the user to review the graph before execution."""
    import questionary

    display_topology(topology, title="[bold]Review Proposed Graph[/bold]")

    choice = questionary.select(
        "  Action",
        choices=["Execute as-is", "Edit and re-weave", "Cancel"],
    ).ask()

    if choice == "Cancel":
        return None
    if choice == "Edit and re-weave":
        mods = questionary.text("What changes would you like to make?", default="Make it more efficient").ask()
        return {"re_weave": True, "modifications": mods}
    return {"re_weave": False}
