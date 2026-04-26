"""Comprehensive tests for WaveExecutor -- wave-based parallel execution.

Covers: __init__, execute_waves (linear, diamond, failure, HITL),
_execute_wave parallel execution, _get_node_inputs, CancelledError,
empty topology edge case, _skip_downstream, _store_result.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from arachne.config import Settings
from arachne.topologies.schema import (
    EdgeDef,
    GraphTopology,
    NodeDef,
    NodeResult,
    NodeRole,
    ResultStatus,
    RunResult,
)
from arachne.topologies.wave_executor import WaveExecutor

# ── Helpers ──────────────────────────────────────────────────────────


def _mock_node_exec(node_id: str, output_field: str, return_value: dict | None = None):
    """Create a mock node executor that returns a dict result."""
    exec_mock = AsyncMock()
    node_def = _node_def(node_id, output_field=output_field)
    exec_mock.node = node_def
    exec_mock.module = None
    if return_value is None:
        return_value = {output_field: f"{node_id}_output"}
    exec_mock.execute = AsyncMock(return_value=return_value)
    return exec_mock


def _node_def(
    node_id: str,
    role: NodeRole = NodeRole.REACT,
    inputs: list[str] | None = None,
    output_field: str = "",
    depends_on: list[str] | None = None,
    question=None,
) -> NodeDef:
    return NodeDef(
        id=node_id,
        role=role,
        name=node_id.title(),
        description=f"Node {node_id}",
        inputs=inputs or [],
        output=output_field or f"{node_id}_output",
        depends_on=depends_on or [],
        question=question,
    )


def _linear_topology() -> tuple[GraphTopology, dict]:
    """A -> B -> C linear pipeline."""
    nodes = [
        _node_def("a", output_field="a_out"),
        _node_def("b", NodeRole.PREDICT, inputs=["a_out"], output_field="b_out"),
        _node_def("c", NodeRole.PREDICT, inputs=["b_out"], output_field="c_out"),
    ]
    edges = [
        EdgeDef(source="a", target="b", label="a_out"),
        EdgeDef(source="b", target="c", label="b_out"),
    ]
    topo = GraphTopology(name="linear", objective="test linear", nodes=nodes, edges=edges)
    executors = {n.id: _mock_node_exec(n.id, n.output) for n in nodes}
    return topo, executors


def _diamond_topology() -> tuple[GraphTopology, dict]:
    """A -> [B, C] -> D diamond."""
    nodes = [
        _node_def("a", output_field="a_out"),
        _node_def("b", NodeRole.PREDICT, inputs=["a_out"], output_field="b_out"),
        _node_def("c", NodeRole.PREDICT, inputs=["a_out"], output_field="c_out"),
        _node_def("d", NodeRole.PREDICT, inputs=["b_out", "c_out"], output_field="d_out"),
    ]
    edges = [
        EdgeDef(source="a", target="b", label="a_out"),
        EdgeDef(source="a", target="c", label="a_out"),
        EdgeDef(source="b", target="d", label="b_out"),
        EdgeDef(source="c", target="d", label="c_out"),
    ]
    topo = GraphTopology(name="diamond", objective="test diamond", nodes=nodes, edges=edges)
    executors = {n.id: _mock_node_exec(n.id, n.output) for n in nodes}
    return topo, executors


# ── Test: WaveExecutor.__init__ ──────────────────────────────────────


class TestWaveExecutorInit:
    def test_basic_init(self):
        topo, executors = _linear_topology()
        settings = Settings()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=settings)
        assert ex.topology is topo
        assert ex.node_executors is executors
        assert ex.settings is settings
        assert ex.session is None
        assert ex._results == {}
        assert ex._executed_this_run == set()

    def test_init_with_session(self):
        topo, executors = _linear_topology()
        session = MagicMock()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings(), session=session)
        assert ex.session is session

    def test_init_with_initial_results(self):
        topo, executors = _linear_topology()
        initial = {
            "a": NodeResult(node_id="a", status=ResultStatus.COMPLETED, output={"a_out": "done"}),
        }
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings(), initial_results=initial)
        assert "a" in ex._results
        assert ex._results["a"].status == ResultStatus.COMPLETED


# ── Test: execute_waves linear (A -> B -> C) ─────────────────────────


class TestExecuteWavesLinear:
    @pytest.mark.asyncio
    async def test_linear_all_nodes_execute(self):
        topo, executors = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        run_result, node_results = await ex.execute_waves({"goal": "test linear goal"})

        assert isinstance(run_result, RunResult)
        assert run_result.graph_name == "linear"
        assert run_result.goal == "test linear goal"
        assert len(node_results) == 3

        for nid in ("a", "b", "c"):
            assert node_results[nid].status == ResultStatus.COMPLETED
            assert node_results[nid].output != {}

    @pytest.mark.asyncio
    async def test_linear_inputs_propagate(self):
        topo, executors = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        await ex.execute_waves({"goal": "propagate test"})

        # Verify that node b received a_out as input
        call_args = executors["b"].execute.call_args
        assert call_args is not None
        inputs_b = call_args[1] if call_args[1] else call_args.kwargs
        assert "a_out" in inputs_b

    @pytest.mark.asyncio
    async def test_linear_duration_recorded(self):
        topo, executors = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        run_result, _ = await ex.execute_waves({"goal": "test"})

        assert run_result.duration_seconds >= 0
        for nr in run_result.node_results:
            assert nr.duration_seconds >= 0


# ── Test: execute_waves diamond (A -> [B, C] -> D) ──────────────────


class TestExecuteWavesDiamond:
    @pytest.mark.asyncio
    async def test_diamond_all_nodes_execute(self):
        topo, executors = _diamond_topology()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        _, node_results = await ex.execute_waves({"goal": "test diamond"})

        assert len(node_results) == 4
        for nid in ("a", "b", "c", "d"):
            assert node_results[nid].status == ResultStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_diamond_b_and_c_run_in_parallel(self):
        """B and C are in the same wave and should both execute."""
        topo, executors = _diamond_topology()
        waves = topo.topological_waves()
        # Wave 0: [a], Wave 1: [b, c], Wave 2: [d]
        assert waves[1] == ["b", "c"]

        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())
        await ex.execute_waves({"goal": "test"})

        executors["b"].execute.assert_awaited_once()
        executors["c"].execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_diamond_d_receives_both_inputs(self):
        topo, executors = _diamond_topology()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        await ex.execute_waves({"goal": "test"})

        call_kwargs = executors["d"].execute.call_args.kwargs
        assert "b_out" in call_kwargs
        assert "c_out" in call_kwargs


# ── Test: execute_waves with node failures ───────────────────────────


class TestExecuteWavesFailures:
    @pytest.mark.asyncio
    async def test_failure_marks_node_as_failed(self):
        topo, executors = _linear_topology()
        executors["b"].execute = AsyncMock(side_effect=RuntimeError("B blew up"))
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        _, node_results = await ex.execute_waves({"goal": "test failure"})

        assert node_results["a"].status == ResultStatus.COMPLETED
        assert node_results["b"].status == ResultStatus.FAILED
        assert "B blew up" in node_results["b"].error

    @pytest.mark.asyncio
    async def test_failure_skips_downstream(self):
        topo, executors = _linear_topology()
        executors["b"].execute = AsyncMock(side_effect=RuntimeError("B failed"))
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        _, node_results = await ex.execute_waves({"goal": "test skip"})

        assert node_results["c"].status == ResultStatus.SKIPPED
        assert "Upstream node failed" in node_results["c"].error

    @pytest.mark.asyncio
    async def test_diamond_failure_skips_all_downstream(self):
        topo, executors = _diamond_topology()
        executors["b"].execute = AsyncMock(side_effect=RuntimeError("B died"))
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        _, node_results = await ex.execute_waves({"goal": "test diamond fail"})

        assert node_results["a"].status == ResultStatus.COMPLETED
        assert node_results["b"].status == ResultStatus.FAILED
        # C may or may not have executed (same wave as B), but D must be skipped
        assert node_results["d"].status == ResultStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_failure_still_returns_run_result(self):
        topo, executors = _linear_topology()
        executors["a"].execute = AsyncMock(side_effect=RuntimeError("root fail"))
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        run_result, _ = await ex.execute_waves({"goal": "test"})
        assert isinstance(run_result, RunResult)
        assert run_result.duration_seconds >= 0


# ── Test: execute_waves with HITL nodes ──────────────────────────────


class TestExecuteWavesHITL:
    @pytest.mark.asyncio
    async def test_hitl_node_calls_ask_user_fn(self):
        nodes = [
            _node_def("a", output_field="a_out"),
            NodeDef(
                id="approve",
                role=NodeRole.HUMAN_IN_LOOP,
                name="Approve",
                description="Approve output",
                inputs=["a_out"],
                output="approval",
                question={"query": "Do you approve?", "type": "confirm"},
            ),
        ]
        edges = [EdgeDef(source="a", target="approve", label="a_out")]
        topo = GraphTopology(name="hitl_test", objective="test hitl", nodes=nodes, edges=edges)

        executors = {
            "a": _mock_node_exec("a", "a_out"),
        }
        # HITL node executor
        hitl_exec = AsyncMock()
        hitl_exec.node = nodes[1]
        hitl_exec.module = None
        hitl_exec.execute = AsyncMock(return_value={"approval": "yes"})
        executors["approve"] = hitl_exec

        ask_user_fn = MagicMock(return_value="yes")

        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())
        _, node_results = await ex.execute_waves({"goal": "test hitl"}, ask_user_fn=ask_user_fn)

        assert node_results["a"].status == ResultStatus.COMPLETED
        # ask_user_fn should have been called for the HITL node
        ask_user_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_hitl_pre_collected_answer_skips_prompt(self):
        """If answer is pre-collected in knowledge_store, HITL skips the prompt."""
        nodes = [
            NodeDef(
                id="gate",
                role=NodeRole.HUMAN_IN_LOOP,
                name="Gate",
                description="Approval gate",
                inputs=[],
                output="answer",
            ),
        ]
        topo = GraphTopology(name="precollected", objective="test", nodes=nodes, edges=[])

        gate_exec = AsyncMock()
        gate_exec.node = nodes[0]
        gate_exec.module = None
        gate_exec.execute = AsyncMock(return_value={"answer": "pre-answer"})

        ex = WaveExecutor(
            topology=topo,
            node_executors={"gate": gate_exec},
            settings=Settings(),
        )
        # Pass the pre-collected answer in initial inputs
        _, node_results = await ex.execute_waves(
            {"goal": "test", "answer": "pre-answer"},
            ask_user_fn=MagicMock(),
        )
        assert node_results["gate"].status == ResultStatus.COMPLETED


# ── Test: _execute_wave parallel execution ───────────────────────────


class TestExecuteWaveParallel:
    @pytest.mark.asyncio
    async def test_parallel_wave_executes_all_nodes(self):
        topo, executors = _diamond_topology()
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())
        all_results = {"goal": "test"}
        ks = MagicMock()
        lock = asyncio.Lock()

        outcomes = await ex._execute_wave(["b", "c"], all_results, ks, lock, ask_user_fn=None)

        assert len(outcomes) == 2
        assert all(err is None for _, err in outcomes)
        node_ids = {nid for nid, _ in outcomes}
        assert node_ids == {"b", "c"}

    @pytest.mark.asyncio
    async def test_parallel_wave_mixed_success_failure(self):
        topo, executors = _diamond_topology()
        executors["b"].execute = AsyncMock(side_effect=RuntimeError("b broke"))
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())
        all_results = {"goal": "test", "a_out": "data"}
        ks = MagicMock()
        lock = asyncio.Lock()

        outcomes = await ex._execute_wave(["b", "c"], all_results, ks, lock, ask_user_fn=None)

        outcome_map = {nid: err for nid, err in outcomes}
        assert outcome_map["b"] is not None
        assert outcome_map["c"] is None

    @pytest.mark.asyncio
    async def test_already_completed_node_is_skipped(self):
        topo, executors = _diamond_topology()
        initial = {
            "b": NodeResult(node_id="b", status=ResultStatus.COMPLETED, output={"b_out": "old"}),
        }
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings(), initial_results=initial)
        all_results = {"goal": "test", "a_out": "data"}
        ks = MagicMock()
        lock = asyncio.Lock()

        outcomes = await ex._execute_wave(["b"], all_results, ks, lock, ask_user_fn=None)

        # b was already completed and no upstream was re-executed => skip
        assert outcomes[0] == ("b", None)
        executors["b"].execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_completed_node_reruns_if_upstream_changed(self):
        topo, executors = _linear_topology()
        initial = {
            "b": NodeResult(node_id="b", status=ResultStatus.COMPLETED, output={"b_out": "stale"}),
        }
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings(), initial_results=initial)
        # Mark 'a' as having been executed this run
        ex._executed_this_run.add("a")
        all_results = {"goal": "test", "a_out": "fresh_data"}
        ks = MagicMock()
        lock = asyncio.Lock()

        await ex._execute_wave(["b"], all_results, ks, lock, ask_user_fn=None)

        # b should re-execute since upstream 'a' was executed in this run
        executors["b"].execute.assert_awaited_once()


# ── Test: _get_node_inputs ───────────────────────────────────────────


class TestGetNodeInputs:
    def test_resolves_inputs_from_upstream(self):
        topo, _ = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())

        all_results = {"goal": "g", "a_out": "alpha_output"}
        inputs = ex._get_node_inputs("b", all_results)
        assert inputs["a_out"] == "alpha_output"
        assert inputs["goal"] == "g"

    def test_missing_input_is_empty_string(self):
        topo, _ = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())

        all_results = {"goal": "g"}
        inputs = ex._get_node_inputs("b", all_results)
        assert inputs["a_out"] == ""

    def test_goal_always_injected(self):
        topo, _ = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())

        inputs = ex._get_node_inputs("a", {"goal": "my goal"})
        assert inputs["goal"] == "my goal"

    def test_no_inputs_root_node(self):
        topo, _ = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())

        inputs = ex._get_node_inputs("a", {"goal": "g"})
        assert inputs == {"goal": "g"}


# ── Test: CancelledError handling ────────────────────────────────────


class TestCancelledError:
    @pytest.mark.asyncio
    async def test_cancelled_error_propagates_from_gather(self):
        """CancelledError is a BaseException and not caught by 'except Exception'
        in run_one(). It propagates through asyncio.gather and up to execute_waves."""
        topo, executors = _linear_topology()
        executors["b"].execute = AsyncMock(side_effect=asyncio.CancelledError())
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        # CancelledError should propagate out (it's a BaseException, not Exception)
        with pytest.raises(asyncio.CancelledError):
            await ex.execute_waves({"goal": "test cancel"})

        # Node 'a' should have completed before 'b' was cancelled
        assert ex._results["a"].status == ResultStatus.COMPLETED


# ── Test: Empty topology edge case ───────────────────────────────────


class TestEmptyTopologyEdgeCase:
    @pytest.mark.asyncio
    async def test_single_node_topology(self):
        """Smallest valid topology: one node, no edges."""
        nodes = [_node_def("solo", output_field="result")]
        topo = GraphTopology(name="single", objective="one node", nodes=nodes, edges=[])
        executors = {"solo": _mock_node_exec("solo", "result")}
        ex = WaveExecutor(topology=topo, node_executors=executors, settings=Settings())

        _, node_results = await ex.execute_waves({"goal": "solo test"})

        assert len(node_results) == 1
        assert node_results["solo"].status == ResultStatus.COMPLETED

    def test_zero_node_topology_raises(self):
        """GraphTopology validation rejects empty node list."""
        with pytest.raises(ValueError, match="at least one node"):
            GraphTopology(name="empty", objective="nothing", nodes=[], edges=[])


# ── Test: _skip_downstream ──────────────────────────────────────────


class TestSkipDownstream:
    def test_marks_future_waves_as_skipped(self):
        topo, _ = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())
        waves = topo.topological_waves()

        ex._skip_downstream(waves, failed_wave_idx=0)

        # Everything after wave 0 should be skipped
        assert ex._results["b"].status == ResultStatus.SKIPPED
        assert ex._results["c"].status == ResultStatus.SKIPPED

    def test_skip_saves_session_state(self):
        topo, _ = _linear_topology()
        session = MagicMock()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings(), session=session)
        waves = topo.topological_waves()

        ex._skip_downstream(waves, failed_wave_idx=0)

        session.save_state.assert_called_once()
        state_arg = session.save_state.call_args[0][0]
        assert "node_results" in state_arg

    def test_skip_no_session_no_error(self):
        topo, _ = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())
        waves = topo.topological_waves()
        # Should not raise even with no session
        ex._skip_downstream(waves, failed_wave_idx=0)


# ── Test: _store_result ──────────────────────────────────────────────


class TestStoreResult:
    def test_stores_output_by_field_name(self):
        topo, _ = _linear_topology()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())
        all_results: dict = {"goal": "test"}
        ks = MagicMock()
        node_def = topo.nodes[0]  # node 'a'

        result = {"a_out": "hello world"}
        ex._store_result("a", node_def, result, all_results, ks, ts=0.0)

        assert all_results["a"] == "hello world"
        assert all_results["a_out"] == "hello world"
        assert ex._results["a"].status == ResultStatus.COMPLETED

    def test_store_result_with_session(self):
        topo, _ = _linear_topology()
        session = MagicMock()
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings(), session=session)
        all_results: dict = {"goal": "test"}
        ks = MagicMock()
        node_def = topo.nodes[0]

        ex._store_result("a", node_def, {"a_out": "data"}, all_results, ks, ts=0.0)

        session.save_node_output.assert_called_once()
        session.append_log.assert_called_once()

    def test_hitl_result_preserves_rich_dict(self):
        """For HUMAN_IN_LOOP nodes with multi-field results, keep the full dict."""
        node = NodeDef(
            id="approve",
            role=NodeRole.HUMAN_IN_LOOP,
            name="Approve",
            description="Approve",
            inputs=[],
            output="approval",
        )
        topo = GraphTopology(name="hitl_store", objective="test", nodes=[node], edges=[])
        ex = WaveExecutor(topology=topo, node_executors={}, settings=Settings())
        all_results: dict = {"goal": "test"}
        ks = MagicMock()

        result = {"approval": "yes", "context": "original content"}
        ex._store_result("approve", node, result, all_results, ks, ts=0.0)

        # For HITL with >1 field, store the entire dict
        assert isinstance(all_results["approve"], dict)
        assert isinstance(all_results["approval"], dict)
        assert all_results["approval"]["context"] == "original content"
