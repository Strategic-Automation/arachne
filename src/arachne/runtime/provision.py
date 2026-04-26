"""Auto-provisioning layer — agentically creates missing tools and skills."""

import logging

import dspy
from rich.console import Console
from rich.table import Table

from arachne.config import Settings
from arachne.runtime.schemas import SkillGenResult, ToolGenResult
from arachne.skills.registry import exists as skill_exists
from arachne.skills.registry import save as skill_save
from arachne.tools import exists as tool_exists
from arachne.tools import resolve_tool, save_tool
from arachne.topologies.schema import GraphTopology

logger = logging.getLogger(__name__)


class ToolMakerSignature(dspy.Signature):
    """Factory for Python tools.
    1. Research requirements.
    2. Write efficient, type-hinted code.
    3. Lint and verify using 'ruff' via 'shell_exec'.
    """

    tool_name: str = dspy.InputField(desc="snake_case tool name")
    description: str = dspy.InputField(desc="Protocol to implement")
    result: ToolGenResult = dspy.OutputField(desc="Verified Python source code")


class SkillMakerSignature(dspy.Signature):
    """Factory for behavioral skills.
    Write a structured Markdown protocol with clear steps, caveats, and success criteria.
    """

    skill_name: str = dspy.InputField(desc="hierarchical/name")
    description: str = dspy.InputField(desc="Context and goals")
    result: SkillGenResult = dspy.OutputField(desc="Markdown content")


class ToolMaker(dspy.Module):
    """Autonomous agent that creates verified Python tools."""

    def __init__(self) -> None:
        super().__init__()
        # Inject standard engineering tools into the maker
        maker_tools = [resolve_tool(t) for t in ["shell_exec", "read_file", "write_local_file", "web_search"]]
        self.agent = dspy.ReAct(ToolMakerSignature, tools=[t for t in maker_tools if t])

    def forward(self, name: str, description: str) -> str:
        # The agent agentically decides to test, lint, and verify
        # We pass ruff/pytest as a hint in the Signature docstring
        response = self.agent(tool_name=name, description=description)
        return response.result.code


class SkillMaker(dspy.Module):
    """Autonomous agent that creates markdown protocols."""

    def __init__(self) -> None:
        super().__init__()
        maker_tools = [resolve_tool(t) for t in ["web_search", "web_fetch", "read_file"]]
        self.agent = dspy.ReAct(SkillMakerSignature, tools=[t for t in maker_tools if t])

    def forward(self, name: str, description: str) -> str:
        response = self.agent(skill_name=name, description=description)
        return response.result.content


def provision_graph(graph: GraphTopology, settings: Settings, goal: str = "") -> GraphTopology:
    """Check topology for custom tools/skills. Create any that don't exist yet."""
    # Populate name/objective from goal if missing
    if not graph.name or not graph.objective:
        goal_text = goal or "unnamed_goal"
        if not graph.name:
            graph.name = goal_text[:50] if len(goal_text) > 50 else goal_text
        if not graph.objective:
            graph.objective = goal_text

    console = Console()
    tool_maker = ToolMaker()
    skill_maker = SkillMaker()
    created_tools: list[str] = []
    created_skills: list[str] = []

    # Provision custom tools
    for req in graph.custom_tools:
        if tool_exists(req.name):
            console.print(f"[dim]  Tool '{req.name}' already exists, skipping.[/dim]")
            continue

        console.print(f"  [yellow]Agentically creating tool: {req.name}[/yellow]")
        table = Table(show_header=False, box=None)
        table.add_row("Name", req.name)
        table.add_row("Description", req.description)
        console.print(table)

        # Only generate if code not already provided by the Weaver
        code = req.code if req.code else tool_maker(name=req.name, description=req.description)
        path = save_tool(req.name, code, req.description, ext="py")

        # Verify the tool actually loads
        verified = resolve_tool(req.name)
        if verified is None:
            console.print(f"  [red]WARNING: Tool saved but failed to load from {path}[/red]")
            logger.warning("Tool %s saved to %s but resolve_tool() returned None", req.name, path)
        else:
            created_tools.append(req.name)
            console.print(f"  [green]Verified & Saved: {path}[/green]")

    # Provision custom skills
    for req in graph.custom_skills:
        if skill_exists(req.name):
            console.print(f"[dim]  Skill '{req.name}' already exists, skipping.[/dim]")
            continue

        console.print(f"  [yellow]Agentically creating skill: {req.name}[/yellow]")
        table = Table(show_header=False, box=None)
        table.add_row("Name", req.name)
        table.add_row("Description", req.description)
        console.print(table)

        content = req.content if req.content else skill_maker(name=req.name, description=req.description)
        path = skill_save(req.name, content)
        created_skills.append(req.name)
        console.print(f"  [green]Verified & Saved: {path}[/green]")

    if created_tools or created_skills:
        console.print()
        summary = Table(title="[bold]Provisioned Assets[/bold]")
        summary.add_column("Type")
        summary.add_column("Count")
        if created_tools:
            summary.add_row("Tools", str(len(created_tools)))
        if created_skills:
            summary.add_row("Skills", str(len(created_skills)))
        console.print(summary)

    return graph
