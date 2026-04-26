"""Arachne -- Top-level dspy.Module composing Weaver + Runner + Evaluator."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import dspy

from arachne.config import Settings, configure_dspy
from arachne.execution.manager import ExecutionManager
from arachne.ports import HeadlessOutput, OutputPort, RichTerminalOutput
from arachne.runtime.evaluator import TriangulatedEvaluator
from arachne.runtime.provision import provision_graph
from arachne.sessions.manager import Session, find_latest_session_by_goal
from arachne.skills import registry as skills
from arachne.tools import initialize as tools_init
from arachne.topologies.schema import GoalDefinition, GraphTopology, NodeResult
from arachne.topologies.weaver import GraphWeaver
from arachne.utils import goal_hash

logger = logging.getLogger(__name__)


class Arachne(dspy.Module):
    """Top-level dspy.Module: Weaver -> Provision -> Runner -> TriangulatedEvaluator."""

    def __init__(
        self,
        settings: Settings | None = None,
        goal_definition: GoalDefinition | None = None,
        max_retries: int = 3,
        interactive: bool = False,
        cache_dir: str | None = None,
        confidence_threshold: float = 0.8,
        output: OutputPort | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings or Settings.from_yaml()
        self.goal_definition = goal_definition
        self.max_retries = max_retries
        self.interactive = interactive
        self.confidence_threshold = confidence_threshold
        self._cache_dir = Path(cache_dir) if cache_dir else (self.settings.session.directory.parent / "topology-cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # OutputPort: decouples core from terminal I/O
        self._output: OutputPort = output or (RichTerminalOutput() if interactive else HeadlessOutput())

        # Initialize tools and skills registries
        tools_init(self.settings.session.directory.parent / "tools")
        pkg_internal_skills = Path(__file__).parent / "skills"
        skill_dirs = [
            pkg_internal_skills / "default",
            pkg_internal_skills / "custom",
            self.settings.skill.directory / "default",
            self.settings.skill.directory / "custom",
        ]
        skills.initialize(skill_dirs)

        # Ensure environment and LLM are provisioned
        self.settings.ensure_ready()

        # Centralized DSPy configuration (called exactly once per process)
        configure_dspy(self.settings)

        # Now create DSPy modules (will be traced)
        self.weaver = GraphWeaver(settings=self.settings)
        self.evaluator = TriangulatedEvaluator(confidence_threshold=confidence_threshold)
        self._history: list[dict] = []
        self._session: Session | None = None

    def weave(
        self,
        goal: str,
        modifications: str = "",
        failure_context: str | None = None,
        goal_definition: GoalDefinition | None = None,
    ) -> GraphTopology:
        gd = goal_definition or self.goal_definition

        # Check if this goal was previously woven and cached
        cached = self._load_cached_topology(goal)
        if cached and not modifications and not failure_context and not gd:
            if self._session:
                self._session.save_graph(cached.model_dump(mode="json"))
            return cached

        pred = self.weaver(
            goal=goal,
            goal_definition=gd,
            failure_context=failure_context,
            modifications=modifications,
            check_intake=self.interactive and not failure_context,
        )

        if not pred.is_complete and self.interactive:
            self._output.status(f"Goal Analysis: {pred.reasoning}", level="warning")
            self._output.status("Your goal seems underspecified. Could you clarify a few things?")

            new_details = []
            for q in pred.questions:
                ans = self._output.ask_user(
                    node_def=type("Q", (), {"question": {"query": q}})(),
                    inputs={},
                )
                if ans:
                    new_details.append(f"Q: {q}\nA: {ans}")

            if new_details:
                enriched_goal = f"{goal}\n\nAdditional Context:\n" + "\n".join(new_details)
                self._output.status("Goal updated with your context. Weaving...")
                # Re-weave with enriched goal, but disable intake check to avoid loops
                return self.weave(goal=enriched_goal, goal_definition=gd, modifications=modifications)

        topology = pred.topology
        if topology is None:
            # Fallback if weaver failed to produce topology and we didn't handle questions
            raise ValueError(f"Weaver failed to produce a topology. Reason: {pred.reasoning}")

        # Always cache the topology for future use (even without an active session)
        self._save_cached_topology(goal, topology)
        if self._session:
            self._session.save_graph(topology.model_dump(mode="json"))
        return topology

    def load_topology(self, path: str | Path) -> GraphTopology:
        """Load a topology from a JSON file (skip weaving entirely)."""
        data = json.loads(Path(path).read_text())
        topology = GraphTopology.model_validate(data)
        if self._session:
            self._session.save_graph(data)
        return topology

    def forward(
        self,
        goal: str,
        topology: GraphTopology | None = None,
        resume_session_id: str | None = None,
        replay_nodes: list[str] | None = None,
        goal_definition: GoalDefinition | None = None,
        fresh: bool = False,
        **kwargs: Any,
    ) -> dspy.Prediction:
        """Execute a goal, optionally resuming a previous session.

        Args:
            goal: The goal to achieve
            topology: Pre-woven topology (optional)
            resume_session_id: Session ID to resume (loads previous outputs)
            replay_nodes: Node IDs to force-replay even when resuming
            goal_definition: Optional goal definition with objective, success criteria, and constraints
            fresh: If True, bypass automatic resumption and start a new session
        """
        # Session creation and optional resume loading
        session: Session | None = None
        raw_outputs: dict | None = None  # loaded outputs for resume

        if resume_session_id:
            session = Session(resume_session_id, self.settings.session.directory)
            self._session = session
            raw_outputs = session.load_outputs()
            session.save_inputs({"goal": goal, **kwargs, "_resumed": True, "_resume_session": resume_session_id})
        else:
            # Automatic Resume: Check if a session for this goal already exists
            auto_session_id = find_latest_session_by_goal(goal, self.settings.session.directory) if not fresh else None
            if auto_session_id:
                self._output.status(f"↺ Automatically resuming session: {auto_session_id}")
                session = Session(auto_session_id, self.settings.session.directory)
                self._session = session
                raw_outputs = session.load_outputs()
                session.save_inputs({"goal": goal, **kwargs, "_resumed": True, "_auto_resume": True})
            else:
                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                session_id = f"run_{ts}"
                session = Session(session_id, self.settings.session.directory)
                self._session = session
                session.save_inputs({"goal": goal, **kwargs})

        initial_results: dict[str, NodeResult] | None = None  # will be constructed after topology if resuming

        # Resolve effective GoalDefinition (defaults to plain goal as objective)
        effective_gd: GoalDefinition | None = goal_definition or self.goal_definition
        if effective_gd is None:
            effective_gd = GoalDefinition(objective=goal)

        from arachne.runtime.context_store import clear, put
        from arachne.runtime.search_memory import SearchMemoryStore

        clear()
        put("goal", goal)

        # Initialize session-scoped search memory for persistence across healing iterations
        _search_memory = SearchMemoryStore(session.path) if session else None

        # Wire session ID into Langfuse for trace grouping (via env vars for SDK compat)
        # NOTE: This is inherently not concurrency-safe; concurrent sessions will overwrite
        # each other's metadata. A future refactor should use Langfuse's constructor-based API.
        import os

        truncate = goal[:50] + "..." if len(goal) > 50 else goal
        os.environ["LANGFUSE_SESSION_ID"] = self._session.id
        os.environ["LANGFUSE_SESSION_NAME"] = truncate

        # Initialize Langfuse client in this process if not already done
        try:
            from langfuse import get_client

            if self.settings.langfuse.enabled:
                get_client(public_key=self.settings.langfuse.public_key)
        except Exception:
            logger.debug("Langfuse client initialization skipped", exc_info=True)

        # Use provided topology or weave one
        if topology is None:
            topology = self.weave(goal=goal, goal_definition=effective_gd)

        # Provision (create missing skills/tools)
        topology = provision_graph(topology, self.settings, goal)
        if self._session:
            self._session.save_graph(topology.model_dump(mode="json"))

        mods = kwargs.get("modifications", "")
        # Interactive review
        if self.interactive:
            from rich.console import Console

            from arachne.cli.display import review_graph

            console = Console()
            while True:
                feedback = review_graph(topology, console)
                if feedback is None:
                    raise ValueError("Execution cancelled by user")

                # Track latest modifications
                mods = feedback.get("modifications", mods)

                if not feedback.get("re_weave"):
                    break

                with console.status("[bold cyan]Re-weaving agent graph...", spinner="dots"):
                    topology = self.weave(goal=goal, goal_definition=effective_gd, modifications=mods)
                    topology = provision_graph(topology, self.settings, goal)
                    if self._session:
                        self._session.save_graph(topology.model_dump(mode="json"))

        # Build initial_results from resume data if needed
        if raw_outputs:
            initial_results = {}
            for node_id, data in raw_outputs.items():
                if replay_nodes and node_id in replay_nodes:
                    continue
                node_def = topology.nodes_dict.get(node_id)
                if not node_def:
                    continue

                try:
                    # Legacy check: if 'output' is a string in raw data, wrap it before validation
                    if isinstance(data.get("output"), str):
                        data["output"] = {node_def.output: data.get("output")}

                    nr = NodeResult.model_validate(data)
                    initial_results[node_id] = nr
                except Exception:
                    logger.debug("Skipping invalid node result for %s", node_id, exc_info=True)
                    continue

        # Execute the graph
        return self._execute(
            goal,
            topology,
            modifications=mods,
            initial_results=initial_results,
            goal_definition=effective_gd,
            **kwargs,
        )

    def _execute(
        self,
        goal: str,
        topology: GraphTopology,
        modifications: str = "",
        initial_results: dict[str, Any] | None = None,
        goal_definition: GoalDefinition | None = None,
        **kwargs: Any,
    ) -> dspy.Prediction:
        """Execute the graph with self-healing loop and circuit breaker."""
        execution_manager = ExecutionManager(
            settings=self.settings,
            weaver=self.weaver,
            evaluator=self.evaluator,
            goal_definition=goal_definition,
            max_retries=self.max_retries,
            confidence_threshold=self.confidence_threshold,
            on_topology_update=lambda top: self._save_cached_topology(goal, top),
            modifications=modifications,
            interactive=self.interactive,
        )
        return execution_manager.execute(
            goal=goal,
            topology=topology,
            session=self._session,
            initial_results=initial_results,
            **kwargs,
        )

    # ── Topology cache ────────────────────────────────────────────────

    def _load_cached_topology(self, goal: str) -> GraphTopology | None:
        path = self._cache_dir / f"{goal_hash(goal)}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return GraphTopology.model_validate(data)
            except Exception:
                return None
        return None

    def _save_cached_topology(self, goal: str, topology: GraphTopology) -> None:
        path = self._cache_dir / f"{goal_hash(goal)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(topology.model_dump_json(indent=2))
