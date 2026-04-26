"""Tests for ExecutionManager and related execution components."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import dspy
import pytest

from arachne.execution.manager import ExecutionManager, _run_async_safe
from arachne.runtime.auto_healer import AutoHealer
from arachne.runtime.evaluator import TriangulatedEvaluator
from arachne.runtime.schemas import HealAttempt
from arachne.topologies.node_executor import NodeExecutor
from arachne.topologies.schema import (
    EdgeDef,
    FailureReport,
    GoalDefinition,
    GraphTopology,
    NodeDef,
    NodeResult,
    NodeRole,
    Question,
    QuestionType,
    ResultStatus,
    RunResult,
)
from arachne.topologies.wave_executor import WaveExecutor
from arachne.topologies.weaver import GraphWeaver

# ── Helper factories ──────────────────────────────────────────────────


def _make_node(node_id, role=NodeRole.PREDICT, inputs=None, output=None, name=None):
    """Create a minimal NodeDef for testing."""
    return NodeDef(
        id=node_id,
        name=name or node_id.capitalize(),
        role=role,
        inputs=inputs or [],
        output=output or f"{node_id}_output",
    )


def _make_linear_topology(node_ids=None) -> GraphTopology:
    """Create a linear DAG: n0 -> n1 -> n2 -> ... (root is REACT)."""
    ids = node_ids or ["A", "B", "C"]
    nodes = []
    edges = []
    for i, nid in enumerate(ids):
        inputs = [ids[i - 1] + "_output"] if i > 0 else []
        role = NodeRole.REACT if i == 0 else NodeRole.PREDICT
        nodes.append(_make_node(nid, role=role, inputs=inputs))
        if i > 0:
            edges.append(EdgeDef(source=ids[i - 1], target=nid))
    return GraphTopology(name="Linear Test", objective="test", nodes=nodes, edges=edges)


def _make_diamond_topology() -> GraphTopology:
    """Create a diamond DAG: A -> B, A -> C, B -> D, C -> D."""
    nodes = [
        _make_node("A", NodeRole.REACT, inputs=[], output="a_out"),
        _make_node("B", NodeRole.PREDICT, inputs=["a_out"], output="b_out"),
        _make_node("C", NodeRole.PREDICT, inputs=["a_out"], output="c_out"),
        _make_node("D", NodeRole.CHAIN_OF_THOUGHT, inputs=["b_out", "c_out"], output="d_out"),
    ]
    edges = [
        EdgeDef(source="A", target="B"),
        EdgeDef(source="A", target="C"),
        EdgeDef(source="B", target="D"),
        EdgeDef(source="C", target="D"),
    ]
    return GraphTopology(name="Diamond Test", objective="test", nodes=nodes, edges=edges)


def _make_run_result(graph_name="test", goal="test goal", node_ids=None, statuses=None):
    """Create a RunResult with specified node statuses."""
    ids = node_ids or ["A", "B", "C"]
    stats = statuses or [ResultStatus.COMPLETED] * len(ids)
    return RunResult(
        graph_name=graph_name,
        goal=goal,
        node_results=[
            NodeResult(
                node_id=nid,
                status=st,
                output={f"{nid}_output": f"output from {nid}"},
            )
            for nid, st in zip(ids, stats, strict=False)
        ],
    )


def _make_evaluator_pred(confidence=0.95, diagnosis="", eval_source="semantic_evaluator"):
    """Create a mock evaluator Prediction."""
    report = FailureReport(
        goal="test goal",
        attempt=1,
        confidence_score=confidence,
        diagnosis=diagnosis,
        evaluation_source=eval_source,
    )
    return dspy.Prediction(report=report)


# ── 1. ExecutionManager.__init__ ──────────────────────────────────────


class TestExecutionManagerInit:
    """Tests for ExecutionManager constructor."""

    def test_default_config(self, settings):
        """Init with only required arguments uses sensible defaults."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)

        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        assert mgr.settings is settings
        assert mgr.weaver is weaver
        assert mgr.evaluator is evaluator
        assert mgr.max_retries == 3
        assert mgr.confidence_threshold == 0.8
        assert mgr.goal_definition is None
        assert mgr.on_topology_update is None
        assert mgr.modifications == ""
        assert mgr.interactive is False
        assert isinstance(mgr.auto_healer, AutoHealer)
        assert mgr._history == []

    def test_custom_config(self, settings):
        """Init with all optional arguments stores them correctly."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        goal_def = GoalDefinition(objective="test", success_criteria=["pass"])
        on_update = MagicMock()
        ask_fn = MagicMock(return_value="yes")

        mgr = ExecutionManager(
            settings=settings,
            weaver=weaver,
            evaluator=evaluator,
            goal_definition=goal_def,
            max_retries=5,
            confidence_threshold=0.9,
            on_topology_update=on_update,
            ask_user_fn=ask_fn,
            modifications="skip step 2",
            interactive=True,
        )

        assert mgr.max_retries == 5
        assert mgr.confidence_threshold == 0.9
        assert mgr.goal_definition is goal_def
        assert mgr.on_topology_update is on_update
        assert mgr.ask_user_fn is ask_fn
        assert mgr.modifications == "skip step 2"
        assert mgr.interactive is True

    def test_ask_user_fn_defaults_to_internal(self, settings):
        """ask_user_fn defaults to _default_ask_user when not provided."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)

        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        assert mgr.ask_user_fn == mgr._default_ask_user


# ── 2. execute() with linear topology (all succeed) ───────────────────


class TestExecuteLinearSuccess:
    """Tests for execute() on a linear 3-node topology, all succeed."""

    def test_linear_all_succeed(self, settings):
        """A -> B -> C, all nodes complete successfully."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        topology = _make_linear_topology(["A", "B", "C"])
        run_result = _make_run_result("Linear", "analyze data", ["A", "B", "C"])
        run_result.success = True
        evaluator.return_value = _make_evaluator_pred(confidence=0.95)

        with patch(
            "arachne.execution.manager._run_async_safe",
            return_value=(run_result, {}),
        ):
            mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)
            result = mgr.execute(goal="analyze data", topology=topology)

        assert result.run_result.success is True
        assert result.run_result.confidence_score == 0.95
        assert result.run_result.attempts == 1
        evaluator.assert_called_once()

    def test_linear_all_succeed_with_goal_definition(self, settings):
        """Execute with a GoalDefinition passes it to evaluator."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        topology = _make_linear_topology(["X", "Y"])
        run_result = _make_run_result("Linear2", "simple task", ["X", "Y"])
        evaluator.return_value = _make_evaluator_pred(confidence=0.85)
        goal_def = GoalDefinition(objective="simple task", success_criteria=["done"])

        with patch(
            "arachne.execution.manager._run_async_safe",
            return_value=(run_result, {}),
        ):
            mgr = ExecutionManager(
                settings=settings,
                weaver=weaver,
                evaluator=evaluator,
                goal_definition=goal_def,
            )
            mgr.execute(goal="simple task", topology=topology)

        call_kwargs = evaluator.call_args.kwargs
        assert call_kwargs["goal_definition"] is goal_def


# ── 3. execute() with diamond topology ────────────────────────────────


class TestExecuteDiamond:
    """Tests for execute() on a diamond topology."""

    def test_diamond_all_succeed_and_collects_outputs(self, settings):
        """Diamond topology A->B, A->C, B->D, C->D, all succeed."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        topology = _make_diamond_topology()
        run_result = _make_run_result("Diamond", "complex task", ["A", "B", "C", "D"])
        evaluator.return_value = _make_evaluator_pred(confidence=0.92)

        with patch(
            "arachne.execution.manager._run_async_safe",
            return_value=(run_result, {}),
        ):
            mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)
            result = mgr.execute(goal="complex task", topology=topology)

        assert result.run_result.success is True
        # All 4 nodes completed
        node_ids = {nr.node_id for nr in result.run_result.node_results}
        assert node_ids == {"A", "B", "C", "D"}
        for nr in result.run_result.node_results:
            assert nr.status == ResultStatus.COMPLETED

    def test_diamond_outputs_preserved(self, settings):
        """Verify outputs from all diamond nodes are in the result."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        topology = _make_diamond_topology()

        node_results = [
            NodeResult(node_id="A", status=ResultStatus.COMPLETED, output={"a_out": "alpha"}),
            NodeResult(node_id="B", status=ResultStatus.COMPLETED, output={"b_out": "beta"}),
            NodeResult(node_id="C", status=ResultStatus.COMPLETED, output={"c_out": "gamma"}),
            NodeResult(node_id="D", status=ResultStatus.COMPLETED, output={"d_out": "delta"}),
        ]
        run_result = RunResult(
            graph_name="Diamond",
            goal="multi-output",
            node_results=node_results,
        )
        evaluator.return_value = _make_evaluator_pred(confidence=0.90)

        with patch(
            "arachne.execution.manager._run_async_safe",
            return_value=(run_result, {}),
        ):
            mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)
            result = mgr.execute(goal="multi-output", topology=topology)

        outputs = {nr.node_id: nr.output for nr in result.run_result.node_results}
        assert outputs["A"]["a_out"] == "alpha"
        assert outputs["B"]["b_out"] == "beta"
        assert outputs["C"]["c_out"] == "gamma"
        assert outputs["D"]["d_out"] == "delta"


# ── 4. execute() with a node failing ──────────────────────────────────


class TestExecuteNodeFailure:
    """Tests for failure handling in execute()."""

    def test_single_node_failure_triggers_finalize(self, settings):
        """When a node fails, circuit breaker triggers after max retries."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        topology = _make_linear_topology(["A", "B", "C"])
        # B fails, A completed
        run_result = _make_run_result(
            "FailGraph", "failing task", ["A", "B", "C"],
            [ResultStatus.COMPLETED, ResultStatus.FAILED, ResultStatus.SKIPPED],
        )
        run_result.node_results[1].error = "Simulated failure"

        # Mock the auto_healer to return a valid diagnosis without calling real DSPy
        mock_diag = MagicMock()
        mock_diag.requires_human = False
        mock_diag.fix_strategy = "retry"
        mock_diag.fix_description = "Retry node B with higher resources"
        mock_diag.confidence_score = 0.5
        mock_diag.topology_modifications = ""

        with patch(
            "arachne.execution.manager._run_async_safe",
            return_value=(run_result, {}),
        ):
            mgr = ExecutionManager(
                settings=settings,
                weaver=weaver,
                evaluator=evaluator,
                max_retries=0,   # zero retries => circuit breaker triggers
            )
            mgr.auto_healer = MagicMock(return_value=mock_diag)
            result = mgr.execute(goal="failing task", topology=topology)

        # Circuit breaker triggers because max_retries=0 means first failure trips it
        assert result.run_result.success is False
        assert result.run_result.attempts > 0

    def test_failure_with_retry_strategy(self, settings):
        """First-time failure with no prior retries gets 'retry' strategy."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        topology = _make_linear_topology(["A", "B", "C"])
        run_result_first = _make_run_result(
            "RetryGraph", "retry task", ["A", "B", "C"],
            [ResultStatus.COMPLETED, ResultStatus.FAILED, ResultStatus.SKIPPED],
        )
        run_result_first.node_results[1].error = "Timeout error"

        run_result_second = _make_run_result("RetryGraph", "retry task", ["A", "B", "C"])
        evaluator.return_value = _make_evaluator_pred(confidence=0.95)

        side_effects = [run_result_first, run_result_second]

        with patch(
            "arachne.execution.manager._run_async_safe",
            side_effect=[(r, {}) for r in side_effects],
        ):
            mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator, max_retries=1)
            result = mgr.execute(goal="retry task", topology=topology)

        # After retry, all nodes should succeed
        assert result.run_result.success is True


# ── 5-7. NodeExecutor._build_module() by module type ──────────────────


class TestNodeExecutorBuildModule:
    """Tests for NodeExecutor._build_module() covering Predict, ChainOfThought, ReAct."""

    @pytest.fixture
    def exec_factory(self, settings):
        """Return a factory for NodeExecutor given a node."""
        def _make(node):
            return NodeExecutor(node=node, settings=settings)
        return _make

    def test_build_module_predict_role(self, exec_factory):
        """NodeRole.PREDICT produces dspy.Predict module."""
        node = _make_node("p1", NodeRole.PREDICT, inputs=["in1"], output="out1")
        executor = exec_factory(node)
        module = executor._build_module()
        assert isinstance(module, dspy.Predict)
        assert module is not None

    def test_build_module_chain_of_thought_role(self, exec_factory):
        """NodeRole.CHAIN_OF_THOUGHT produces dspy.Predict module."""
        node = _make_node("cot1", NodeRole.CHAIN_OF_THOUGHT, inputs=["in1"], output="out1")
        executor = exec_factory(node)
        module = executor._build_module()
        assert isinstance(module, dspy.Predict)

    def test_build_module_react_role(self, exec_factory):
        """NodeRole.REACT produces dspy.ReAct module (with tools)."""
        node = _make_node("r1", NodeRole.REACT, inputs=["in1"], output="out1")
        executor = exec_factory(node)
        # We need to mock tools for ReAct
        with patch.object(executor, "_tools", []):
            module = executor._build_module()
        assert isinstance(module, dspy.ReAct)

    def test_build_module_hitl_role_returns_none(self, exec_factory):
        """NodeRole.HUMAN_IN_LOOP returns None (pure approval gate)."""
        node = _make_node("h1", NodeRole.HUMAN_IN_LOOP, inputs=["in1"], output="approval")
        executor = exec_factory(node)
        module = executor._build_module()
        assert module is None

    def test_root_predict_node_promoted_to_react(self, exec_factory):
        """Root node with Predict role gets promoted to ReAct."""
        node = _make_node("root_pred", NodeRole.PREDICT, inputs=[], output="out1")
        executor = exec_factory(node)
        with patch.object(executor, "_tools", []):
            module = executor._build_module()
        assert isinstance(module, dspy.ReAct)

    def test_root_chain_of_thought_promoted_to_react(self, exec_factory):
        """Root node with ChainOfThought role gets promoted to ReAct."""
        node = _make_node("root_cot", NodeRole.CHAIN_OF_THOUGHT, inputs=[], output="out1")
        executor = exec_factory(node)
        with patch.object(executor, "_tools", []):
            module = executor._build_module()
        assert isinstance(module, dspy.ReAct)


# ── 8. _handle_hitl() ─────────────────────────────────────────────────


class TestHandleHitl:
    """Tests for WaveExecutor._handle_human_input (human-in-the-loop)."""

    @pytest.mark.asyncio
    async def test_hitl_with_ask_user_fn(self, settings):
        """When ask_user_fn is provided, it is called with node_def and inputs."""
        # Build a 2-node topology: root REACT node -> approval HITL node
        root = NodeDef(
            id="generate",
            name="Generate",
            role=NodeRole.REACT,
            inputs=[],
            output="a_out",
        )
        approval = NodeDef(
            id="approval_gate",
            name="Approval",
            role=NodeRole.HUMAN_IN_LOOP,
            inputs=["a_out"],
            output="approval",
            question=Question(
                query="Approve result from {upstream_output}?",
                type=QuestionType.SELECT,
                choices=["yes", "no"],
            ),
        )
        topology = GraphTopology(
            name="HITL Test",
            objective="test",
            nodes=[root, approval],
            edges=[EdgeDef(source="generate", target="approval_gate")],
        )
        all_results = {"a_out": "some data", "goal": "test"}
        executor = WaveExecutor(
            topology=topology,
            node_executors={"generate": AsyncMock(), "approval_gate": AsyncMock()},
            settings=settings,
        )
        ask_fn = Mock(return_value="yes")
        knowledge_store = MagicMock()
        console_lock = MagicMock()

        result = await executor._handle_human_input(
            node_exec=executor.node_executors["approval_gate"],
            node_def=approval,
            inputs={"a_out": "some data", "goal": "test"},
            knowledge_store=knowledge_store,
            console_lock=console_lock,
            ask_user_fn=ask_fn,
            all_results=all_results,
        )

        assert "approval" in result
        assert result["approval"] == "yes"
        assert "a_out" in result  # upstream output preserved
        ask_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_hitl_pre_collected_answer(self, settings):
        """HITL with pre-collected answer skips user prompt."""
        node = NodeDef(
            id="pre_approved",
            name="PreApproved",
            role=NodeRole.HUMAN_IN_LOOP,
            inputs=[],
            output="answer",
            question=Question(query="Confirm?"),
        )
        topology = GraphTopology(
            name="PreCollected",
            objective="test",
            nodes=[node],
            edges=[],
        )
        executor = WaveExecutor(
            topology=topology,
            node_executors={"pre_approved": MagicMock()},
            settings=settings,
        )
        knowledge_store = MagicMock()
        knowledge_store.get.return_value = "pre-approved answer"
        console_lock = MagicMock()

        mock_exec = MagicMock()
        mock_exec.module = None  # Pure gate

        result = await executor._handle_human_input(
            node_exec=mock_exec,
            node_def=node,
            inputs={"goal": "test"},
            knowledge_store=knowledge_store,
            console_lock=console_lock,
            ask_user_fn=AsyncMock(),
            all_results={"answer": "pre-approved answer"},
        )

        assert result["answer"] == "pre-approved answer"


# ── 9. _collect_outputs() from successful nodes ───────────────────────


class TestCollectOutputs:
    """Tests for output collection from successful nodes."""

    def test_collect_completed_node_outputs(self):
        """Outputs from completed nodes can be extracted from RunResult."""
        node_results = [
            NodeResult(node_id="A", status=ResultStatus.COMPLETED, output={"a_out": "alpha"}),
            NodeResult(node_id="B", status=ResultStatus.FAILED, output={}, error="fail"),
            NodeResult(node_id="C", status=ResultStatus.COMPLETED, output={"c_out": "gamma"}),
        ]
        run_result = RunResult(
            graph_name="Partial",
            goal="test",
            node_results=node_results,
        )

        # Extract outputs from successful nodes (like _handle_low_quality does)
        completed = {
            nr.node_id: nr
            for nr in run_result.node_results
            if nr.status == ResultStatus.COMPLETED
        }

        assert len(completed) == 2
        assert "A" in completed
        assert "C" in completed
        assert "B" not in completed
        assert completed["A"].output["a_out"] == "alpha"
        assert completed["C"].output["c_out"] == "gamma"

    def test_collect_outputs_all_failed(self):
        """When all nodes fail, completed dict is empty."""
        node_results = [
            NodeResult(node_id="A", status=ResultStatus.FAILED, output={}, error="error"),
            NodeResult(node_id="B", status=ResultStatus.FAILED, output={}, error="error"),
        ]
        run_result = RunResult(
            graph_name="AllFail",
            goal="test",
            node_results=node_results,
        )

        completed = {
            nr.node_id: nr
            for nr in run_result.node_results
            if nr.status == ResultStatus.COMPLETED
        }

        assert len(completed) == 0

    def test_collect_outputs_mixed_with_skipped(self):
        """Skipped nodes are not included in completed outputs."""
        node_results = [
            NodeResult(node_id="A", status=ResultStatus.COMPLETED, output={"a_out": "ok"}),
            NodeResult(node_id="B", status=ResultStatus.SKIPPED, error="upstream fail"),
            NodeResult(node_id="C", status=ResultStatus.FAILED, output={}, error="fail"),
        ]
        run_result = RunResult(
            graph_name="Mixed",
            goal="test",
            node_results=node_results,
        )

        completed = {
            nr.node_id: nr
            for nr in run_result.node_results
            if nr.status == ResultStatus.COMPLETED
        }

        assert len(completed) == 1
        assert "A" in completed
        assert "B" not in completed
        assert "C" not in completed


# ── 10. check_circuit_breaker logic ───────────────────────────────────


class TestCircuitBreaker:
    """Tests for _check_circuit_breaker logic."""

    def test_no_history_does_not_trip(self, settings):
        """Empty attempt history does not trip circuit breaker."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        failed = [NodeResult(node_id="X", status=ResultStatus.FAILED, error="err")]
        result = mgr._check_circuit_breaker(failed, [], max_node_retries=3, session=None)

        assert result is False

    def test_below_threshold_does_not_trip(self, settings):
        """Node retried less than max does not trip circuit breaker."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        history = [HealAttempt(attempt=1, strategy="retry", fix_description="retry", failed_nodes=["X"])]
        failed = [NodeResult(node_id="X", status=ResultStatus.FAILED, error="err")]
        result = mgr._check_circuit_breaker(failed, history, max_node_retries=3, session=None)

        assert result is False

    def test_hitting_threshold_trips_circuit_breaker(self, settings):
        """Node retried exactly max times trips circuit breaker."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        history = [
            HealAttempt(attempt=1, strategy="retry", fix_description="retry", failed_nodes=["X"]),
            HealAttempt(attempt=2, strategy="retry", fix_description="retry", failed_nodes=["X"]),
            HealAttempt(attempt=3, strategy="retry", fix_description="retry", failed_nodes=["X"]),
        ]
        failed = [NodeResult(node_id="X", status=ResultStatus.FAILED, error="err")]
        result = mgr._check_circuit_breaker(failed, history, max_node_retries=3, session=None)

        assert result is True

    def test_multiple_nodes_counted_separately(self, settings):
        """Each node ID is counted independently."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        history = [
            HealAttempt(attempt=1, strategy="retry", fix_description="retry", failed_nodes=["X"]),
            HealAttempt(attempt=2, strategy="retry", fix_description="retry", failed_nodes=["X"]),
        ]
        # Node X has 2 retries, Node Y has 0 — Y is the one that failed now
        failed = [NodeResult(node_id="Y", status=ResultStatus.FAILED, error="err_new")]
        result = mgr._check_circuit_breaker(failed, history, max_node_retries=3, session=None)

        assert result is False

    def test_with_session_logs_to_session(self, settings):
        """Circuit breaker trip logs to session when available."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        mock_session = MagicMock()
        history = [
            HealAttempt(attempt=1, strategy="retry", fix_description="retry", failed_nodes=["Z"]),
            HealAttempt(attempt=2, strategy="retry", fix_description="retry", failed_nodes=["Z"]),
            HealAttempt(attempt=3, strategy="retry", fix_description="retry", failed_nodes=["Z"]),
        ]
        failed = [NodeResult(node_id="Z", status=ResultStatus.FAILED, error="err")]

        result = mgr._check_circuit_breaker(failed, history, max_node_retries=3, session=mock_session)

        assert result is True
        mock_session.append_log.assert_called()


# ── 11. execute() with empty topology ─────────────────────────────────


class TestExecuteEmptyTopology:
    """Tests for edge case: empty topology."""

    def test_execute_empty_topology_raises(self, settings):
        """An empty topology should raise an error at validation time."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)

        ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        with pytest.raises(ValueError, match="at least one node"):
            GraphTopology(name="Empty", objective="test", nodes=[], edges=[])

    def test_execute_valid_topology_without_edges(self, settings):
        """A single-node topology with no edges executes successfully."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        evaluator.return_value = _make_evaluator_pred(confidence=0.90)

        manager = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        node = _make_node("only", NodeRole.REACT, inputs=[], output="result")
        topology = GraphTopology(name="Single", objective="test", nodes=[node], edges=[])

        run_result = _make_run_result("Single", "solo task", ["only"])
        with patch(
            "arachne.execution.manager._run_async_safe",
            return_value=(run_result, {}),
        ):
            result = manager.execute(goal="solo task", topology=topology)

        assert result.run_result.success is True
        assert len(result.run_result.node_results) == 1


# ── Additional unit tests ─────────────────────────────────────────────


class TestRunAsyncSafe:
    """Tests for the _run_async_safe helper."""

    def test_returns_coroutine_result(self):
        """_run_async_safe should run a coroutine and return its result."""
        async def sample():
            return ("ok", {"x": 1})

        a, b = _run_async_safe(sample())
        assert a == "ok"
        assert b == {"x": 1}


class TestExecutionManagerFinalize:
    """Tests for _finalize_result."""

    def test_finalize_sets_success_and_attempts(self, settings):
        """_finalize_result should set success flag and attempts on the result."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        run_result = _make_run_result("Test", "goal", ["A"])
        result = dspy.Prediction(run_result=run_result)
        result.topology = MagicMock()

        final = mgr._finalize_result(result, session=None, attempts=5, success=False)

        assert final.run_result.success is False
        assert final.run_result.attempts == 5

    def test_finalize_with_session_saves_state(self, settings):
        """_finalize_result saves state when session is provided."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        run_result = _make_run_result("Test", "goal", ["A"])
        result = dspy.Prediction(run_result=run_result)
        result.topology = MagicMock()
        session = MagicMock()

        final = mgr._finalize_result(result, session=session, attempts=3, success=True)

        session.save_state.assert_called_once()
        assert final.run_result.success is True
        assert final.run_result.attempts == 3


class TestLogStatus:
    """Tests for _log_status."""

    def test_log_info(self, settings):
        """_log_status logs info-level messages."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        mgr._log_status("test message", "info")

    def test_log_with_session(self, settings):
        """_log_status appends to session log when available."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)
        session = MagicMock()

        mgr._log_status("session message", "warning", session)

        session.append_log.assert_called_once_with("_manager", "session message")


class TestDiagnoseFailure:
    """Tests for _diagnose_failure."""

    def test_diagnose_calls_auto_healer(self, settings):
        """_diagnose_failure invokes the auto_healer with failure context."""
        weaver = MagicMock(spec=GraphWeaver)
        evaluator = MagicMock(spec=TriangulatedEvaluator)
        mgr = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

        # Create a proper AutoHealer mock
        mock_healer = MagicMock()
        diagnosis = dspy.Prediction(
            fix_strategy="re-weave",
            fix_description="Redesign graph",
            requires_human=False,
            confidence_score=0.7,
        )
        mock_healer.return_value = diagnosis
        mgr.auto_healer = mock_healer

        topology = _make_linear_topology(["A", "B"])
        run_result = _make_run_result("Diag", "diag goal", ["A", "B"],
                                       [ResultStatus.COMPLETED, ResultStatus.FAILED])
        run_result.node_results[1].error = "KeyError: missing input"

        failed = [nr for nr in run_result.node_results if nr.status.value not in
                   (ResultStatus.COMPLETED, ResultStatus.SKIPPED)]

        result = mgr._diagnose_failure("diag goal", topology, dspy.Prediction(run_result=run_result),
                                       failed, [])

        assert result.fix_strategy == "re-weave"
        assert result.fix_description == "Redesign graph"
        mock_healer.assert_called_once()
