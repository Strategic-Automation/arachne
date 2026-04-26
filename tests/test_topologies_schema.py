"""Tests for topology schema."""

import pytest

from arachne.topologies.schema import (
    EdgeDef,
    FailureReport,
    GraphTopology,
    NodeDef,
    NodeResult,
    NodeRole,
    ResultStatus,
    RunResult,
)


class TestNodeDef:
    def test_defaults(self):
        n = NodeDef(id="s", role=NodeRole.PREDICT, name="S", description="s", output="o")
        assert n.id == "s" and n.max_tokens is None


class TestEdgeDef:
    def test_init(self):
        e = EdgeDef(source="a", target="b")
        assert e.source == "a" and e.label == ""


class TestGraphTopology:
    def test_root_nodes(self):
        t = GraphTopology(
            name="t",
            objective="t",
            nodes=[
                NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o_a"),
                NodeDef(id="b", role=NodeRole.REACT, name="B", description="d", output="o_b"),
                NodeDef(id="c", role=NodeRole.PREDICT, name="C", description="d", output="o_c", inputs=["o_a", "o_b"]),
            ],
            edges=[EdgeDef(source="a", target="c"), EdgeDef(source="b", target="c")],
        )
        assert set(t.root_nodes) == {"a", "b"}

    def test_upstream(self):
        t = GraphTopology(
            name="t",
            objective="t",
            nodes=[
                NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o_a"),
                NodeDef(id="b", role=NodeRole.PREDICT, name="B", description="d", output="o_b", inputs=["o_a"]),
            ],
            edges=[EdgeDef(source="a", target="b")],
        )
        assert t.upstream("b") == ["a"]

    def test_waves_linear(self):
        t = GraphTopology(
            name="t",
            objective="t",
            nodes=[
                NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o_a"),
                NodeDef(id="b", role=NodeRole.PREDICT, name="B", description="d", output="o_b", inputs=["o_a"]),
                NodeDef(id="c", role=NodeRole.PREDICT, name="C", description="d", output="o_c", inputs=["o_b"]),
            ],
            edges=[EdgeDef(source="a", target="b"), EdgeDef(source="b", target="c")],
        )
        assert t.topological_waves() == [["a"], ["b"], ["c"]]

    def test_waves_parallel(self):
        t = GraphTopology(
            name="t",
            objective="t",
            nodes=[
                NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o_a"),
                NodeDef(id="b", role=NodeRole.REACT, name="B", description="d", output="o_b"),
                NodeDef(id="c", role=NodeRole.PREDICT, name="C", description="d", output="o_c", inputs=["o_a", "o_b"]),
            ],
            edges=[EdgeDef(source="a", target="c"), EdgeDef(source="b", target="c")],
        )
        waves = t.topological_waves()
        assert set(waves[0]) == {"a", "b"}
        assert waves[1] == ["c"]

    def test_cycle_raises(self):
        with pytest.raises(ValueError, match=r"Cycle|cycle|root"):
            GraphTopology(
                name="t",
                objective="t",
                nodes=[
                    NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o_a", inputs=["o_b"]),
                    NodeDef(id="b", role=NodeRole.REACT, name="B", description="d", output="o_b", inputs=["o_a"]),
                ],
                edges=[EdgeDef(source="a", target="b"), EdgeDef(source="b", target="a")],
            )


class TestNodeResult:
    def test_defaults(self):
        r = NodeResult(node_id="n")
        assert r.status == ResultStatus.COMPLETED and r.output == {}


class TestRunResult:
    def test_success(self):
        assert RunResult(graph_name="g", goal="x", node_results=[NodeResult(node_id="a")]).is_success

    def test_failure(self):
        rr = RunResult(
            graph_name="g",
            goal="x",
            node_results=[
                NodeResult(node_id="a"),
                NodeResult(node_id="b", status=ResultStatus.FAILED, error="e"),
            ],
        )
        assert not rr.is_success and len(rr.failed_nodes) == 1


class TestFailureReport:
    def test_defaults(self):
        fr = FailureReport(goal="g", attempt=1)
        assert fr.failed_nodes == []
