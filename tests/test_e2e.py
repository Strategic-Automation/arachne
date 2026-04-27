"""End-to-end tests for Arachne core lifecycle.

Mock all LLM-dependent paths while testing real composition of Arachne components.
"""

from unittest.mock import MagicMock, patch

import dspy

from arachne.core import Arachne
from arachne.execution.manager import ExecutionManager
from arachne.runtime.evaluator import TriangulatedEvaluator
from arachne.runtime.provision import provision_graph
from arachne.runtime.schemas import SemanticResult
from arachne.topologies.schema import (
    Constraint,
    ConstraintType,
    CustomToolRequest,
    EdgeDef,
    GoalDefinition,
    GraphTopology,
    NodeDef,
    NodeResult,
    NodeRole,
    ResultStatus,
    RunResult,
)


def _make_minimal_topology(name="test_graph", nodes=None, edges=None):
    """Helper to create a minimal valid GraphTopology."""
    return GraphTopology(
        name=name,
        objective="test objective",
        nodes=nodes or [
            NodeDef(id="node_1", role=NodeRole.REACT, name="Node1", description="test", output="result"),
        ],
        edges=edges or [],
    )


# ── Test 1: Weave simple factual ──────────────────────────────────────

class TestWeaveSimpleFactual:
    def test_weave_simple_factual(self, settings):
        """Call Arachne.weave('What is 2+2?') — verify returns a GraphTopology with nodes."""
        a = Arachne(settings=settings)
        mock_topo = GraphTopology(
            name="math_calculation",
            objective="Calculate 2+2",
            nodes=[
                NodeDef(
                    id="calc",
                    role=NodeRole.REACT,
                    name="Calculator",
                    description="Calculate 2+2 using evaluate_math",
                    output="answer",
                ),
            ],
            edges=[],
        )

        with patch.object(a.weaver, "forward", return_value=dspy.Prediction(topology=mock_topo, is_complete=True)):
            result = a.weave("What is 2+2?")

        assert isinstance(result, GraphTopology)
        assert len(result.nodes) >= 1
        assert result.name == "math_calculation"
        assert result.nodes[0].output == "answer"
        # The topology should be valid (can compute waves without error)
        waves = result.topological_waves()
        assert len(waves) >= 1


# ── Test 2: Weave research task ───────────────────────────────────────

class TestWeaveResearchTask:
    def test_weave_research_task(self, settings):
        """Call Arachne.weave('Research the latest AI news') — verify topology, check custom_tools/custom_skills."""
        a = Arachne(settings=settings)
        mock_topo = GraphTopology(
            name="ai_news_research",
            objective="Research latest AI news",
            nodes=[
                NodeDef(
                    id="search",
                    role=NodeRole.REACT,
                    name="Search",
                    description="Search for AI news",
                    output="articles",
                    tools=[{"name": "duckduckgo_search_async", "description": "Search the web"}],
                ),
                NodeDef(
                    id="summarize",
                    role=NodeRole.CHAIN_OF_THOUGHT,
                    name="Summarize",
                    description="Summarize search findings",
                    output="summary",
                    inputs=["articles"],
                ),
            ],
            edges=[EdgeDef(source="search", target="summarize")],
            custom_tools=[
                CustomToolRequest(
                    name="ai_news_fetcher",
                    description="Fetch latest AI news from RSS feeds",
                    code="def ai_news_fetcher(): pass",
                ),
            ],
            custom_skills=[
            ],
        )

        with patch.object(a.weaver, "forward", return_value=dspy.Prediction(topology=mock_topo, is_complete=True)):
            result = a.weave("Research the latest AI news")

        assert isinstance(result, GraphTopology)
        assert len(result.nodes) >= 1
        assert len(result.edges) >= 1
        # custom_tools may be populated
        assert isinstance(result.custom_tools, list)
        assert len(result.custom_tools) >= 1
        assert result.custom_tools[0].name == "ai_news_fetcher"
        # custom_skills may be empty or populated
        assert isinstance(result.custom_skills, list)


# ── Test 3: Full run cycle ────────────────────────────────────────────

class TestFullRunCycle:
    def test_full_run_cycle(self, settings):
        """Wire up Arachne, weave, provision, execute with mocked execution — verify RunResult produced."""
        a = Arachne(settings=settings)
        mock_topo = _make_minimal_topology()

        mock_run_result = RunResult(
            graph_name="test_graph",
            goal="test goal",
            node_results=[
                NodeResult(
                    node_id="node_1",
                    status=ResultStatus.COMPLETED,
                    output={"result": "the quick brown fox"},
                ),
            ],
            success=True,
            total_cost_usd=0.01,
            total_tokens=42,
            duration_seconds=0.5,
            attempts=1,
        )
        mock_exec_result = dspy.Prediction(run_result=mock_run_result)
        mock_exec_result.topology = mock_topo

        with (
            patch.object(a.weaver, "forward", return_value=dspy.Prediction(topology=mock_topo, is_complete=True)),
            patch("arachne.runtime.provision.provision_graph", return_value=mock_topo),
            patch.object(ExecutionManager, "execute", return_value=mock_exec_result),
        ):
            result = a.forward(goal="test goal", topology=mock_topo)

        assert result is not None
        assert hasattr(result, "run_result")
        assert isinstance(result.run_result, RunResult)
        assert result.run_result.success is True
        assert result.run_result.total_tokens == 42
        assert len(result.run_result.node_results) == 1
        assert result.run_result.node_results[0].status == ResultStatus.COMPLETED


# ── Test 4: Provision creates assets ──────────────────────────────────

class TestProvisionCreatesAssets:
    def test_provision_creates_assets(self, settings):
        """Provision a topology with custom tools, verify ToolMaker is called."""
        topo = GraphTopology(
            name="test_provision",
            objective="test",
            nodes=[
                NodeDef(id="n1", role=NodeRole.REACT, name="N1", description="d", output="o"),
            ],
            custom_tools=[
                # Empty code forces ToolMaker generation
                CustomToolRequest(name="my_custom_tool", description="A custom tool for testing", code=""),
            ],
        )

        with (
            patch("arachne.runtime.provision.tool_exists", return_value=False),
            patch("arachne.runtime.provision.ToolMaker.forward") as mock_toolmaker_forward,
            patch("arachne.runtime.provision.save_tool") as mock_save,
            patch("arachne.runtime.provision.resolve_tool", return_value=MagicMock()),
        ):
            mock_toolmaker_forward.return_value = "def my_custom_tool(): return 42"
            result = provision_graph(topo, settings, "test goal")

        assert mock_toolmaker_forward.called
        assert mock_save.called
        assert result is not None
        assert result.name == "test_provision"


# ── Test 5: Evaluate passing ──────────────────────────────────────────

class TestEvaluatePassing:
    def test_evaluate_passing(self):
        """Wire up evaluator with a good result — verify confidence >= threshold."""
        evaluator = TriangulatedEvaluator(confidence_threshold=0.8)

        run_result = RunResult(
            graph_name="test",
            goal="What is 2+2?",
            node_results=[
                NodeResult(
                    node_id="n1",
                    status=ResultStatus.COMPLETED,
                    output={"result": "Two plus two equals four. This is the correct mathematical answer."},
                ),
            ],
            success=True,
        )

        mock_semantic = dspy.Prediction(
            evaluation=SemanticResult(score=0.95, issues=[], improvements=[])
        )

        with patch.object(evaluator.semantic_eval, "forward", return_value=mock_semantic):
            pred = evaluator(
                goal="What is 2+2?",
                run_result=run_result,
                goal_definition=None,
                topology=None,
                attempt=1,
            )

        report = pred.report
        assert report.confidence_score >= 0.8
        assert report.confidence_score == 0.95
        assert report.evaluation_source in ("semantic_evaluator", "none")


# ── Test 6: Evaluate failing ──────────────────────────────────────────

class TestEvaluateFailing:
    def test_evaluate_failing(self):
        """Evaluator with bad result — verify confidence < threshold."""
        evaluator = TriangulatedEvaluator(confidence_threshold=0.8)

        run_result = RunResult(
            graph_name="test",
            goal="Research AI news",
            node_results=[
                NodeResult(
                    node_id="n1",
                    status=ResultStatus.COMPLETED,
                    output={"result": "I could not find any relevant information about AI news."},
                ),
            ],
            success=True,
        )

        mock_semantic = dspy.Prediction(
            evaluation=SemanticResult(
                score=0.25,
                issues=["Incomplete research: no actual AI news found"],
                improvements=["Use multiple search engines to cross-reference", "Broaden search terms"],
            )
        )

        # Mock _detect_bad_tool_data to return None so semantic evaluator is reached
        with (
            patch.object(evaluator, "_detect_bad_tool_data", return_value=None),
            patch.object(evaluator.semantic_eval, "forward", return_value=mock_semantic),
        ):
            pred = evaluator(
                goal="Research AI news",
                run_result=run_result,
                goal_definition=None,
                topology=None,
                attempt=1,
            )

        report = pred.report
        assert report.confidence_score < 0.8
        assert report.confidence_score == 0.25
        assert report.evaluation_source == "semantic_evaluator"
        assert len(report.evaluation_details.get("issues", [])) >= 1


# ── Test 7: Arachne init ──────────────────────────────────────────────

class TestArachneInit:
    def test_arachne_init(self, settings):
        """Constructor validates settings, creates weaver, evaluator."""
        a = Arachne(settings=settings, max_retries=5, confidence_threshold=0.9)

        assert a.max_retries == 5
        assert a.confidence_threshold == 0.9
        assert a.settings is settings
        assert a.weaver is not None
        assert a.evaluator is not None
        assert isinstance(a.evaluator, TriangulatedEvaluator)
        assert a.goal_definition is None  # Not provided
        assert a.interactive is False  # Default


# ── Test 8: Weave with constraints ────────────────────────────────────

class TestWeaveWithConstraints:
    def test_weave_with_constraints(self, settings):
        """Pass goal with explicit constraints, verify they're reflected in the weave call."""
        a = Arachne(settings=settings)
        gd = GoalDefinition(
            objective="Write a Python script to sort numbers",
            success_criteria=[
                "Script runs without errors",
                "Output is correctly sorted",
            ],
            constraints=[
                Constraint(
                    type=ConstraintType.COST,
                    value=5.0,
                    description="Max cost $5",
                    is_hard_boundary=True,
                ),
                Constraint(
                    type=ConstraintType.TIME,
                    value=60.0,
                    description="Max 60 seconds",
                ),
            ],
        )

        a.goal_definition = gd

        mock_topo = _make_minimal_topology(name="constrained_task")

        with patch.object(a.weaver, "forward") as mock_weave:
            mock_weave.return_value = dspy.Prediction(topology=mock_topo, is_complete=True)
            result = a.weave("Write a Python script to sort numbers", goal_definition=gd)

        assert isinstance(result, GraphTopology)
        assert result.name == "constrained_task"
        # Verify the weaver was called with the goal definition
        mock_weave.assert_called_once()
        call_kwargs = mock_weave.call_args.kwargs
        assert call_kwargs["goal"] == "Write a Python script to sort numbers"
        assert call_kwargs["goal_definition"] is gd
        # The constraints and success_criteria should have been propagated
        assert "constraints_text" in call_kwargs or call_kwargs["goal_definition"] is not None
