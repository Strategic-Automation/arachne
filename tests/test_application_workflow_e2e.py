"""Application workflow tests for session resume and HITL output propagation."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import dspy

from arachne.config import SessionSettings, Settings, SkillSettings
from arachne.core import Arachne
from arachne.execution.manager import ExecutionManager
from arachne.sessions.manager import Session
from arachne.topologies.node_executor import NodeExecutor
from arachne.topologies.schema import EdgeDef, GraphTopology, NodeDef, NodeRole, Question, ResultStatus, RunResult


def _isolated_settings(settings: Settings, tmp_path: Path) -> Settings:
    settings.session = SessionSettings(directory=tmp_path / "sessions")
    settings.skill = SkillSettings(directory=tmp_path / "skills")
    return settings


def _approval_topology() -> GraphTopology:
    return GraphTopology(
        name="approval_workflow",
        objective="Create a draft and ask for approval",
        nodes=[
            NodeDef(
                id="draft",
                role=NodeRole.REACT,
                name="Draft",
                description="Collect or create the draft content.",
                output="draft",
            ),
            NodeDef(
                id="approve",
                role=NodeRole.HUMAN_IN_LOOP,
                name="Approve",
                description="Approve the draft.",
                inputs=["draft"],
                output="approved_report",
                question=Question(query="Review this draft:\n{upstream_output}\n\nApprove?"),
            ),
        ],
        edges=[EdgeDef(source="draft", target="approve")],
    )


def _save_session(
    settings: Settings,
    session_id: str,
    goal: str,
    topology: GraphTopology,
    outputs: dict[str, dict[str, str]],
    state: dict[str, Any] | None = None,
) -> Session:
    session = Session(session_id, settings.session.directory)
    session.save_inputs({"goal": goal})
    session.save_graph(topology.model_dump(mode="json"))
    for node_id, output in outputs.items():
        session.save_node_output(node_id, output)
    if state is not None:
        session.save_state(state)
    return session


def _successful_state(goal: str, topology: GraphTopology, outputs: dict[str, dict[str, str]]) -> dict[str, Any]:
    run_result = RunResult(
        graph_name=topology.name,
        goal=goal,
        node_results=[
            {
                "node_id": node_id,
                "status": ResultStatus.COMPLETED,
                "output": output,
            }
            for node_id, output in outputs.items()
        ],
        success=True,
    )
    return run_result.model_dump(mode="json")


def _run_workflow(
    settings: Settings,
    topology: GraphTopology,
    goal: str,
    responses: dict[str, str],
) -> tuple[dspy.Prediction, list[str], list[str], Session]:
    asked_nodes: list[str] = []
    executed_nodes: list[str] = []

    def ask_user(_manager: ExecutionManager, node_def: NodeDef, _inputs: dict[str, Any]) -> str:
        asked_nodes.append(node_def.id)
        if node_def.id not in responses:
            raise AssertionError(f"Unexpected prompt for node '{node_def.id}'")
        return responses[node_def.id]

    async def execute_node(node_executor: NodeExecutor, **_kwargs: Any) -> dspy.Prediction:
        executed_nodes.append(node_executor.node.id)
        if node_executor.node.id != "draft":
            raise AssertionError(f"Unexpected node execution for '{node_executor.node.id}'")
        if "draft" not in responses:
            raise AssertionError("Draft node should have been resumed, not executed")
        return dspy.Prediction(draft=responses["draft"])

    arachne = Arachne(settings=settings)
    with (
        patch.object(ExecutionManager, "_default_ask_user", ask_user),
        patch.object(NodeExecutor, "execute", execute_node),
    ):
        result = arachne.forward(goal=goal, topology=topology)

    assert arachne._session is not None
    return result, asked_nodes, executed_nodes, arachne._session


def test_run_starts_new_session_instead_of_reusing_completed_outputs(settings: Settings, tmp_path: Path) -> None:
    settings = _isolated_settings(settings, tmp_path)
    topology = _approval_topology()
    goal = "summarize the static architecture"
    stale_outputs = {
        "draft": {"draft": "stale completed report from a previous run"},
        "approve": {"approved_report": "yes", "draft": "stale completed report from a previous run"},
    }
    completed_session = _save_session(
        settings=settings,
        session_id="run_20000101_000000",
        goal=goal,
        topology=topology,
        outputs=stale_outputs,
        state=_successful_state(goal, topology, stale_outputs),
    )

    result, asked_nodes, executed_nodes, active_session = _run_workflow(
        settings=settings,
        topology=topology,
        goal=goal,
        responses={
            "draft": "fresh report generated during this end-to-end run",
            "approve": "yes",
        },
    )

    assert active_session.id != completed_session.id
    assert executed_nodes == ["draft"]
    assert asked_nodes == ["approve"]
    outputs = {node.node_id: node.output for node in result.run_result.node_results}
    assert outputs["draft"]["draft"] == "fresh report generated during this end-to-end run"
    assert "stale completed report" not in json.dumps(result.run_result.model_dump(mode="json"))

    completed_inputs = json.loads((completed_session.path / "inputs.json").read_text())
    assert "_auto_resume" not in completed_inputs


def test_run_auto_resumes_partial_session_and_reuses_completed_upstream(settings: Settings, tmp_path: Path) -> None:
    settings = _isolated_settings(settings, tmp_path)
    topology = _approval_topology()
    goal = "summarize the static architecture with existing context"
    partial_session = _save_session(
        settings=settings,
        session_id="run_20000101_000001",
        goal=goal,
        topology=topology,
        outputs={"draft": {"draft": "partial report preserved from interrupted execution"}},
    )

    result, asked_nodes, executed_nodes, active_session = _run_workflow(
        settings=settings,
        topology=topology,
        goal=goal,
        responses={"approve": "yes"},
    )

    assert active_session.id == partial_session.id
    assert executed_nodes == []
    assert asked_nodes == ["approve"]
    outputs = {node.node_id: node.output for node in result.run_result.node_results}
    assert outputs["draft"]["draft"] == "partial report preserved from interrupted execution"
    assert outputs["approve"]["draft"] == "partial report preserved from interrupted execution"

    resumed_inputs = json.loads((partial_session.path / "inputs.json").read_text())
    assert resumed_inputs["_auto_resume"] is True


def test_time_sensitive_goal_does_not_auto_resume_stale_partial_outputs(settings: Settings, tmp_path: Path) -> None:
    settings = _isolated_settings(settings, tmp_path)
    topology = _approval_topology()
    goal = "latest coding subscription value as at today"
    stale_session = _save_session(
        settings=settings,
        session_id="run_20000101_000002",
        goal=goal,
        topology=topology,
        outputs={"draft": {"draft": "stale pricing comparison from a previous execution"}},
    )

    result, asked_nodes, executed_nodes, active_session = _run_workflow(
        settings=settings,
        topology=topology,
        goal=goal,
        responses={
            "draft": "fresh pricing comparison generated for the current request",
            "approve": "yes",
        },
    )

    assert active_session.id != stale_session.id
    assert executed_nodes == ["draft"]
    assert asked_nodes == ["approve"]
    outputs = {node.node_id: node.output for node in result.run_result.node_results}
    assert outputs["draft"]["draft"] == "fresh pricing comparison generated for the current request"
    assert "stale pricing comparison" not in json.dumps(result.run_result.model_dump(mode="json"))
