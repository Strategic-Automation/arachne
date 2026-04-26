"""Pydantic models for graph topology, nodes, edges, and goals."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class NodeRole(StrEnum):
    CHAIN_OF_THOUGHT = "chain_of_thought"
    REACT = "react"
    PREDICT = "predict"
    HUMAN_IN_LOOP = "human_in_loop"
    RECURSIVE = "recursive"


class ConstraintType(StrEnum):
    COST = "cost"
    TIME = "time"
    SAFETY = "safety"
    QUALITY = "quality"


class Constraint(BaseModel):
    type: ConstraintType
    value: float | None = Field(None, description="Numeric limit if applicable (e.g. max cost in USD)")
    description: str
    is_hard_boundary: bool = Field(False, description="If true, violation fails the run immediately")


class GoalDefinition(BaseModel):
    objective: str
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)


class QuestionType(StrEnum):
    TEXT = "text"
    SELECT = "select"
    CONFIRM = "confirm"


class Question(BaseModel):
    query: str = Field(..., description="The question to ask the user")
    type: QuestionType = Field(
        default=QuestionType.TEXT,
        description="Type of input: 'text' (default), 'confirm' (bool), or 'select' (multi-choice)",
    )
    default: str = Field(default="", description="Default answer or placeholder")
    choices: list[str] = Field(
        default_factory=list,
        description="REQUIRED if type is 'select'. List 2-4 possible answer strings.",
    )


class ToolParameter(BaseModel):
    name: str = Field(..., description="Parameter name")
    type: str = Field(default="str")
    description: str = Field(default="")
    required: bool = Field(default=True)


class ToolDef(BaseModel):
    name: str = Field(
        default="unknown_tool",
        description="Tool name, snake_case. Must match a built-in or a custom tool in 'custom_tools'.",
    )
    description: str = Field(
        default="Tool execution",
        description="Description of how this tool will be used in the node's context.",
    )
    parameters: list[ToolParameter] = Field(default_factory=list)


class CustomToolRequest(BaseModel):
    """A request to create a new custom Python tool.
    Use this if built-in tools (web_search, shell_exec, read_file, etc.) are insufficient to achieve the goal.
    REQUIRED: 'name', 'description', and 'code'.
    'code' must be a complete Python function or class.
    """

    name: str = Field(..., description="Tool name, snake_case")
    description: str = Field(..., description="What this tool does")
    code: str = Field(..., description="Python source code for the tool. Must be self-contained.")


class CustomSkillRequest(BaseModel):
    """A request to create a new custom Markdown skill.
    REQUIRED: 'name', 'description', and 'content'.
    """

    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="When to use this skill")
    content: str = Field(..., description="Markdown content of the skill")


class NodeDef(BaseModel):
    id: str = Field(default="", description="Unique node identifier in snake_case. Must be valid as a dictionary key.")
    role: NodeRole = Field(
        default=NodeRole.REACT,
        description=(
            "Standard module role: 'react' for tool use and file operations (REQUIRED for writing code), "
            "'chain_of_thought' for complex analysis, 'predict' for simple extraction or formatting, "
            "'recursive' for large context exploration (uses DSPy RLM with sandboxed REPL), "
            "'human_in_loop' for user approval."
        ),
    )
    name: str = Field(default="", description="Short human-readable name for the node.")
    description: str = Field(
        default="Execute the assigned node task.",
        description="Detailed natural language instruction for the node. Describe 'what' to do, not 'how' to output it.",
    )
    inputs: list[str] = Field(
        default_factory=list,
        description="List of node IDs whose output fields are needed as inputs. Nodes are executed in topological order.",
    )
    output: str = Field(
        default="",
        description="Name of the output field produced. Should be specific (e.g., 'python_code', 'summary_report').",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of nodes that MUST finish before this node starts, even if their outputs are not directly consumed.",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Token limit for output. High for research/coding (1000+), low for flags (10-50).",
    )
    tools: list[ToolDef] = Field(
        default_factory=list,
        description="List of tools available to this node. Only valid if role is 'react'.",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Full hierarchical paths to behavioral skills (e.g., 'software-development/test-driven-development').",
    )
    mcp_servers: list[str] = Field(
        default_factory=list,
        description="Names of MCP servers to connect to for additional tools.",
    )
    timeout: int | None = Field(
        default=None,
        description="Execution timeout in seconds.",
    )
    question: Question | None = Field(
        default=None,
        description="Mandatory if role is 'human_in_loop'. Ask the user for approval or choice. Use {upstream_output} for context.",
    )

    @model_validator(mode="after")
    def _normalize_fields(self) -> "NodeDef":
        # Convert string tools to ToolDef
        normalized_tools: list[ToolDef] = []
        for t in self.tools:
            if isinstance(t, str):
                normalized_tools.append(ToolDef(name=t, description=f"Tool {t}"))
            else:
                normalized_tools.append(t)
        self.tools = normalized_tools

        # Fill in missing fields from available data
        if not self.id:
            self.id = self.name.lower().replace(" ", "_") if self.name else "node"
        if not self.name:
            self.name = self.id or "unnamed_node"
        if not self.description:
            self.description = f"Node {self.name} for {self.role.value}"
        if not self.output:
            self.output = f"{self.id}_output"

        return self


class EdgeDef(BaseModel):
    source: str = Field(..., description="ID of the upstream node.")
    target: str = Field(..., description="ID of the downstream node.")
    label: str = Field(default="", description="Optional edge label for visualization.")


class GraphTopology(BaseModel):
    name: str = Field(default="unnamed_graph", description="Descriptive name of the graph.")
    objective: str = Field(
        default="execute the requested goal",
        description="The high-level objective this graph accomplishes.",
    )
    nodes: list[NodeDef] = Field(
        default_factory=list,
        description="Complete list of execution nodes. Root nodes (no inputs) MUST be 'react' role.",
    )
    edges: list[EdgeDef] = Field(
        default_factory=list, description="Edges defining the execution flow. Must form a Directed Acyclic Graph (DAG)."
    )
    runtime_inputs: list[str] = Field(default_factory=list, description="Variable names required as initial state.")
    custom_tools: list[CustomToolRequest] = Field(
        default_factory=list, description="Definitions for new Python tools required if built-ins are insufficient."
    )
    custom_skills: list[CustomSkillRequest] = Field(
        default_factory=list,
        description="Definitions for new Markdown behavioral skills required if built-ins are insufficient.",
    )

    @property
    def root_nodes(self) -> list[str]:
        targets = {e.target for e in self.edges}
        return [n.id for n in self.nodes if n.id not in targets]

    @property
    def sink_nodes(self) -> list[str]:
        sources = {e.source for e in self.edges}
        return [n.id for n in self.nodes if n.id not in sources]

    @property
    def nodes_dict(self) -> dict[str, "NodeDef"]:
        return {n.id: n for n in self.nodes}

    def upstream(self, node_id: str) -> list[str]:
        return [e.source for e in self.edges if e.target == node_id]

    @model_validator(mode="after")
    def _validate_not_empty(self) -> "GraphTopology":
        if not self.nodes:
            raise ValueError("Topology must contain at least one node.")
        return self

    @model_validator(mode="after")
    def _validate_io_alignment(self) -> "GraphTopology":
        """Validate all input field names are produced by upstream nodes."""
        if not self.nodes:
            return self

        output_to_node = {n.output: n.id for n in self.nodes if n.output}

        for node in self.nodes:
            for inp in node.inputs:
                if inp not in output_to_node and inp != "goal":
                    raise ValueError(
                        f"Node '{node.id}' requires input '{inp}', but no upstream node produces it. "
                        f"Available outputs: {list(output_to_node.keys())}"
                    )
        return self

    @model_validator(mode="after")
    def _validate_no_cycles(self) -> "GraphTopology":
        """Validate the graph is a DAG at parse time so the manager can re-weave on failure."""
        if not self.nodes:
            return self

        id_set = {n.id for n in self.nodes}
        for edge in self.edges:
            if edge.source not in id_set:
                raise ValueError(
                    f"Edge references non-existent source node '{edge.source}'. Available nodes: {sorted(id_set)}"
                )
            if edge.target not in id_set:
                raise ValueError(
                    f"Edge references non-existent target node '{edge.target}'. Available nodes: {sorted(id_set)}"
                )

        if self.edges:
            roots = self.root_nodes
            if not roots:
                raise ValueError("Topology has no root nodes (graph has cycles or is empty).")

            nodes_dict = {n.id: n for n in self.nodes}
            for root_id in roots:
                root_node = nodes_dict.get(root_id)
                if root_node and root_node.role not in (NodeRole.REACT, NodeRole.RECURSIVE):
                    raise ValueError(
                        f"Root node '{root_id}' must have role='react' or 'recursive', but got '{root_node.role.value}'. "
                        "Graph entry points require tool-using (react/recursive) capability."
                    )

        visited = {nid for wave in self.topological_waves() for nid in wave}
        if visited != id_set:
            cycled = id_set - visited
            raise ValueError(
                f"Topology contains a cycle involving nodes: {cycled}. "
                "Arachne only supports DAGs. Model iterative workflows as a "
                "linear chain (e.g. analyze → fix → validate) without back-edges."
            )
        return self

    def topological_waves(self) -> list[list[str]]:
        """Split the graph into independent execution waves using Kahn's algorithm."""
        id_set = {n.id for n in self.nodes}
        in_degree = {n.id: 0 for n in self.nodes}
        adj = {n.id: [] for n in self.nodes}
        for edge in self.edges:
            if edge.source in id_set and edge.target in id_set:
                in_degree[edge.target] += 1
                adj[edge.source].append(edge.target)
        waves: list[list[str]] = []
        queue = sorted([nid for nid, d in in_degree.items() if d == 0])
        visited: set[str] = set()
        while queue:
            waves.append(list(queue))
            next_queue: list[str] = []
            for nid in queue:
                visited.add(nid)
                for neighbor in adj.get(nid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = sorted(next_queue)
        return waves


class ResultStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"


class NodeResult(BaseModel):
    node_id: str
    status: ResultStatus = ResultStatus.COMPLETED
    output: dict = Field(default_factory=dict)
    error: str | None = None
    cost_usd: float = 0.0
    tokens_used: int = 0
    duration_seconds: float = 0.0


class RunResult(BaseModel):
    graph_name: str
    goal: str
    node_results: list[NodeResult] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    attempts: int = 1
    success: bool = True

    # Phase 2: Evaluation data
    evaluation_source: str = Field(
        default="none",
        description="Source of failure: 'rule_constraint', 'semantic_evaluator', or 'human_escalation'",
    )
    confidence_score: float = Field(
        default=1.0,
        description="Semantic confidence score (0.0-1.0)",
    )
    requires_human: bool = Field(
        default=False,
        description="Whether this result requires human escalation (HITL Level 2)",
    )

    @property
    def failed_nodes(self) -> list[NodeResult]:
        return [r for r in self.node_results if r.status != ResultStatus.COMPLETED]

    @property
    def is_success(self) -> bool:
        return all(r.status == ResultStatus.COMPLETED for r in self.node_results)


class FailureReport(BaseModel):
    goal: str
    attempt: int
    failed_nodes: list[str] = Field(default_factory=list)
    error_details: dict[str, str] = Field(default_factory=dict)
    partial_results: dict[str, dict] = Field(default_factory=dict)
    diagnosis: str = ""
    topology_fix: str = ""
    confidence_score: float = Field(1.0, description="Evaluation confidence 0.0-1.0")
    evaluation_source: str = Field("none", description="rule_constraint, semantic_evaluator, human")
    requires_human: bool = Field(False)
    evaluation_details: dict[str, object] = Field(
        default_factory=dict, description="Structured feedback: reasoning, issues, improvements"
    )
