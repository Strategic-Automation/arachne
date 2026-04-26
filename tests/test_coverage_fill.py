"""Tests for evaluator, provision, and sessions modules.

Coverage fill for:
- src/arachne/runtime/evaluator.py (TriangulatedEvaluator)
- src/arachne/runtime/provision.py (provision_graph, ToolMaker)
- src/arachne/sessions/manager.py (Session)
"""

import json
import shutil
from unittest.mock import MagicMock, patch

import dspy

from arachne.runtime.evaluator import SemanticEvalSignature, TriangulatedEvaluator
from arachne.runtime.provision import ToolMaker, provision_graph
from arachne.runtime.schemas import SemanticResult, ToolGenResult
from arachne.sessions.manager import Session
from arachne.topologies.schema import (
    CustomToolRequest,
    GoalDefinition,
    GraphTopology,
    NodeDef,
    NodeResult,
    NodeRole,
    ResultStatus,
    RunResult,
)

# ── EVALUATOR Tests ──────────────────────────────────────────────────


class TestTriangulatedEvaluator:
    def test_init_defaults(self):
        """Verify default threshold and that semantic_eval is a dspy.Predict."""
        evaluator = TriangulatedEvaluator()
        assert evaluator.confidence_threshold == 0.8
        assert isinstance(evaluator.semantic_eval, dspy.Predict)
        assert evaluator.semantic_eval.signature == SemanticEvalSignature

    def test_evaluate_success(self):
        """All nodes completed with high semantic confidence."""
        evaluator = TriangulatedEvaluator()
        run_result = RunResult(
            graph_name="test_graph",
            goal="test goal",
            node_results=[
                NodeResult(
                    node_id="a",
                    status=ResultStatus.COMPLETED,
                    output={"result": "meaningful output data here"},
                ),
            ],
        )
        mock_result = SemanticResult(score=0.95, issues=[], improvements=[])
        evaluator.semantic_eval = MagicMock(return_value=dspy.Prediction(evaluation=mock_result))

        prediction = evaluator(goal="test goal", run_result=run_result)
        report = prediction.report

        assert report.confidence_score == 0.95
        assert report.evaluation_source == "semantic_evaluator"
        assert report.requires_human is False

    def test_evaluate_rules_fail(self):
        """Failed nodes trigger rule_constraint failure with zero confidence."""
        evaluator = TriangulatedEvaluator()
        run_result = RunResult(
            graph_name="test_graph",
            goal="test goal",
            node_results=[
                NodeResult(node_id="bad_node", status=ResultStatus.FAILED, error="Boom", output={}),
            ],
        )

        prediction = evaluator(goal="test goal", run_result=run_result)
        report = prediction.report

        assert report.evaluation_source == "rule_constraint"
        assert report.confidence_score == 0.0
        assert "bad_node" in report.failed_nodes

    def test_evaluate_semantic(self):
        """Semantic check returns low score with issues and improvements."""
        evaluator = TriangulatedEvaluator()
        run_result = RunResult(
            graph_name="test_graph",
            goal="test goal",
            node_results=[
                NodeResult(
                    node_id="a",
                    status=ResultStatus.COMPLETED,
                    output={"result": "some output"},
                ),
            ],
        )
        mock_result = SemanticResult(
            score=0.3, issues=["Bad output format"], improvements=["Re-weave with better prompt"]
        )
        evaluator.semantic_eval = MagicMock(return_value=dspy.Prediction(evaluation=mock_result))

        prediction = evaluator(goal="test goal", run_result=run_result)
        report = prediction.report

        assert report.evaluation_source == "semantic_evaluator"
        assert report.confidence_score == 0.3
        assert report.requires_human is True
        assert "Bad output format" in report.diagnosis

    def test_build_from_goal(self):
        """Evaluator uses goal_definition success_criteria in semantic eval."""
        evaluator = TriangulatedEvaluator()
        goal_def = GoalDefinition(
            objective="build a web scraper",
            success_criteria=["output must be valid Python code", "must handle HTTP errors"],
        )
        run_result = RunResult(
            graph_name="test_graph",
            goal="build a web scraper",
            node_results=[
                NodeResult(
                    node_id="a",
                    status=ResultStatus.COMPLETED,
                    output={"code": "import requests\nrequests.get('http://example.com')"},
                ),
            ],
        )
        mock_result = SemanticResult(score=0.88, issues=[], improvements=[])
        evaluator.semantic_eval = MagicMock(return_value=dspy.Prediction(evaluation=mock_result))

        prediction = evaluator(goal="build a web scraper", run_result=run_result, goal_definition=goal_def)
        report = prediction.report

        assert report.confidence_score == 0.88
        assert report.evaluation_source == "semantic_evaluator"

    def test_hitl_threshold(self):
        """Score below confidence_threshold triggers requires_human flag."""
        evaluator = TriangulatedEvaluator(confidence_threshold=0.9)
        run_result = RunResult(
            graph_name="test_graph",
            goal="test goal",
            node_results=[
                NodeResult(
                    node_id="a", status=ResultStatus.COMPLETED, output={"result": "meaningful output data here"}
                ),
            ],
        )
        # Score 0.7 is below the 0.9 threshold
        mock_result = SemanticResult(score=0.7, issues=["mediocre quality"], improvements=["try again"])
        evaluator.semantic_eval = MagicMock(return_value=dspy.Prediction(evaluation=mock_result))

        prediction = evaluator(goal="test goal", run_result=run_result)
        report = prediction.report

        assert report.requires_human is True
        assert report.confidence_score == 0.7
        assert report.evaluation_source == "semantic_evaluator"


# ── PROVISION Tests ──────────────────────────────────────────────────


class TestProvision:
    def test_provision_empty(self, settings):
        """No custom tools or skills: graph is returned unchanged."""
        graph = GraphTopology(
            name="empty_graph",
            objective="nothing to provision",
            nodes=[NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o")],
        )
        result = provision_graph(graph, settings)
        assert result is graph
        assert len(result.custom_tools) == 0
        assert len(result.custom_skills) == 0

    def test_provision_new_tool(self, settings, tmp_path):
        """Tool that doesn't exist gets created and saved."""
        from arachne import tools as tools_mod

        graph = GraphTopology(
            name="new_tool_graph",
            objective="test tool creation",
            nodes=[NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o")],
            custom_tools=[
                CustomToolRequest(
                    name="my_custom_tool",
                    description="A tool that does something useful",
                    code="def my_custom_tool(query: str) -> str:\n    return f'result: {query}'\n",
                )
            ],
        )

        with (
            patch.object(tools_mod, "exists", return_value=False),
            patch.object(tools_mod, "save_tool", return_value=tmp_path / "my_custom_tool.py"),
            patch.object(tools_mod, "resolve_tool", return_value=MagicMock()),
            patch("arachne.runtime.provision.ToolMaker", autospec=True),
            patch("arachne.runtime.provision.SkillMaker", autospec=True),
        ):
            result = provision_graph(graph, settings)
            assert result is graph

    def test_provision_existing_tool(self, settings):
        """Tool that already exists is skipped."""
        from arachne import tools as tools_mod

        graph = GraphTopology(
            name="existing_tool_graph",
            objective="test skip existing",
            nodes=[NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o")],
            custom_tools=[
                CustomToolRequest(
                    name="shell_exec",
                    description="Already exists as built-in",
                    code="",
                )
            ],
        )

        with patch.object(tools_mod, "exists", return_value=True):
            result = provision_graph(graph, settings)
            assert result is graph

    def test_toolmaker_generates_code(self):
        """ToolMaker.forward returns proper Python source code."""
        maker = ToolMaker()
        mock_code = 'def compute_sum(a: int, b: int) -> int:\n    """Return sum of two integers."""\n    return a + b\n'
        mock_result = ToolGenResult(code=mock_code)
        maker.agent = MagicMock(return_value=dspy.Prediction(result=mock_result))

        code = maker(name="compute_sum", description="Add two integers")
        assert code == mock_code
        assert "def compute_sum" in code
        assert "a + b" in code

    def test_save_tool_persists(self, tmp_path):
        """Saved custom tool is resolvable after persist."""
        from arachne.tools import initialize, resolve_tool, save_tool

        initialize(tool_dir=tmp_path)

        tool_name = "persist_test_tool"
        tool_code = f"def {tool_name}(x: int) -> int:\n    return x * 2\n"

        path = save_tool(tool_name, tool_code, "Test tool persistence")
        assert path.exists()
        assert path.suffix == ".py"

        resolved = resolve_tool(tool_name)
        assert resolved is not None
        assert isinstance(resolved, dspy.Tool)


# ── SESSIONS Tests ───────────────────────────────────────────────────


class TestSessions:
    def test_session_create(self, tmp_path):
        """Session creates directory and persists graph metadata."""
        session = Session("test_session_create", base_dir=tmp_path)

        assert session.id == "test_session_create"
        assert session.path.exists()
        assert session.path.is_dir()

        topology_dict = {"name": "test_graph", "nodes": [], "objective": "test"}
        session.save_graph(topology_dict)

        graph_path = session.path / "graph.json"
        assert graph_path.exists()

        with open(graph_path) as f:
            data = json.load(f)
        assert data["name"] == "test_graph"
        assert data["objective"] == "test"

    def test_session_list(self, tmp_path):
        """Sessions listed sorted by modification time, most recent first."""
        s1 = Session("run_20240101_000000", base_dir=tmp_path)
        s1.save_graph({"name": "first"})

        s2 = Session("run_20240102_000000", base_dir=tmp_path)
        s2.save_graph({"name": "second"})

        sessions = sorted(
            [d for d in tmp_path.iterdir() if d.is_dir()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        assert len(sessions) == 2
        assert sessions[0].name == "run_20240102_000000"
        assert sessions[1].name == "run_20240101_000000"

    def test_session_save_load_state(self, tmp_path):
        """Round-trip: save state to disk and read it back."""
        session = Session("test_state_roundtrip", base_dir=tmp_path)
        state = {
            "status": "running",
            "progress": 0.5,
            "nodes": {"a": "completed", "b": "pending"},
            "attempt": 2,
        }
        session.save_state(state)

        state_path = session.path / "state.json"
        assert state_path.exists()

        with open(state_path) as f:
            loaded = json.load(f)
        assert loaded == state
        assert loaded["status"] == "running"
        assert loaded["progress"] == 0.5
        assert loaded["nodes"]["a"] == "completed"
        assert loaded["attempt"] == 2

    def test_session_nonexistent(self, tmp_path):
        """Loading from a fresh session with no files returns safe defaults."""
        session = Session("test_nonexistent_files", base_dir=tmp_path)

        result = session.load_inputs()
        assert result is None

        outputs = session.load_outputs()
        assert outputs == {}

    def test_session_delete(self, tmp_path):
        """Removing session directory cleans up all artifacts."""
        session = Session("to_be_deleted", base_dir=tmp_path)
        session.save_graph({"name": "temporary"})
        session.save_state({"status": "done"})
        session.save_inputs({"goal": "test"})

        session_path = session.path
        assert session_path.exists()
        assert (session_path / "graph.json").exists()
        assert (session_path / "state.json").exists()
        assert (session_path / "inputs.json").exists()

        shutil.rmtree(session_path)
        assert not session_path.exists()
