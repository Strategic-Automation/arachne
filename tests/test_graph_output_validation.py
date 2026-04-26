"""Tests for woven graph topology output validation.

Validates that graph topologies produce outputs matching expected patterns.
Unit tests — no real LLM calls.
"""
import pytest

from arachne.topologies.schema import (
    EdgeDef,
    GraphTopology,
    NodeDef,
    NodeRole,
)


def _node(nid, role=NodeRole.REACT, inputs=None, output=None):
    """Quick NodeDef factory."""
    return NodeDef(
        id=nid,
        name=nid.upper(),
        role=role,
        description=f"Node {nid}",
        inputs=inputs or [],
        output=output or f"{nid}_out",
    )


def test_diamond_graph_output_propagation():
    """Diamond A->[B,C]->D: verify topological waves are correct."""
    topology = GraphTopology(
        name="Diamond", objective="test",
        nodes=[
            _node("A", NodeRole.REACT, [], "a_out"),
            _node("B", NodeRole.PREDICT, ["a_out"], "b_out"),
            _node("C", NodeRole.PREDICT, ["a_out"], "c_out"),
            _node("D", NodeRole.CHAIN_OF_THOUGHT, ["b_out", "c_out"], "d_out"),
        ],
        edges=[
            EdgeDef(source="A", target="B"),
            EdgeDef(source="A", target="C"),
            EdgeDef(source="B", target="D"),
            EdgeDef(source="C", target="D"),
        ],
    )

    waves = topology.topological_waves()
    assert len(waves) == 3
    assert waves[0] == ["A"]
    assert set(waves[1]) == {"B", "C"}
    assert waves[2] == ["D"]


def test_linear_graph_chain_propagation():
    """Linear A->B->C: verify topological ordering is sequential."""
    topology = GraphTopology(
        name="Linear", objective="test",
        nodes=[
            _node("A", NodeRole.REACT, [], "step_a"),
            _node("B", NodeRole.PREDICT, ["step_a"], "step_b"),
            _node("C", NodeRole.CHAIN_OF_THOUGHT, ["step_b"], "step_c"),
        ],
        edges=[
            EdgeDef(source="A", target="B"),
            EdgeDef(source="B", target="C"),
        ],
    )

    waves = topology.topological_waves()
    assert len(waves) == 3
    assert waves[0] == ["A"]
    assert waves[1] == ["B"]
    assert waves[2] == ["C"]


def test_single_node_graph():
    """Single REACT node graph is valid."""
    topology = GraphTopology(
        name="Solo", objective="test",
        nodes=[_node("only", NodeRole.REACT, [], "answer")],
        edges=[],
    )

    waves = topology.topological_waves()
    assert len(waves) == 1
    assert waves[0] == ["only"]


def test_topological_waves_ordering():
    """5-node graph: independent nodes are in same wave."""
    topology = GraphTopology(
        name="Complex", objective="test",
        nodes=[
            _node("a", NodeRole.REACT, [], "a"),
            _node("b", NodeRole.REACT, [], "b"),
            _node("c", NodeRole.PREDICT, ["a"], "c"),
            _node("d", NodeRole.PREDICT, ["b"], "d"),
            _node("e", NodeRole.CHAIN_OF_THOUGHT, ["c", "d"], "e"),
        ],
        edges=[
            EdgeDef(source="a", target="c"),
            EdgeDef(source="b", target="d"),
            EdgeDef(source="c", target="e"),
            EdgeDef(source="d", target="e"),
        ],
    )

    waves = topology.topological_waves()
    assert len(waves) == 3
    assert set(waves[0]) == {"a", "b"}
    assert set(waves[1]) == {"c", "d"}
    assert waves[2] == ["e"]


def test_graph_cycle_detection():
    """Topology with a cycle raises ValueError."""
    with pytest.raises(ValueError, match="cycle"):
        GraphTopology(
            name="Cyclic", objective="test",
            nodes=[
                _node("A", NodeRole.REACT, ["c_out"], "a_out"),
                _node("B", NodeRole.PREDICT, ["a_out"], "b_out"),
                _node("C", NodeRole.PREDICT, ["b_out"], "c_out"),
            ],
            edges=[
                EdgeDef(source="A", target="B"),
                EdgeDef(source="B", target="C"),
                EdgeDef(source="C", target="A"),
            ],
        )


def test_graph_root_node_must_be_react():
    """Root nodes with incoming edges from nowhere must have react or recursive role."""
    with pytest.raises(ValueError, match="Root node"):
        GraphTopology(
            name="BadRoot", objective="test",
            nodes=[
                NodeDef(
                    id="A", name="A", role=NodeRole.PREDICT,
                    description="Bad root", inputs=[], output="out",
                ),
                NodeDef(
                    id="B", name="B", role=NodeRole.PREDICT,
                    description="Child", inputs=["out"], output="b_out",
                ),
            ],
            edges=[EdgeDef(source="A", target="B")],  # edges trigger root validation
        )


def test_nodes_dict_access():
    """GraphTopology.nodes_dict provides id-to-node lookup."""
    topology = GraphTopology(
        name="Lookup", objective="test",
        nodes=[
            _node("input", NodeRole.REACT, [], "raw"),
            _node("process", NodeRole.PREDICT, ["raw"], "result"),
        ],
        edges=[EdgeDef(source="input", target="process")],
    )

    nd = topology.nodes_dict
    assert "input" in nd
    assert "process" in nd
    assert nd["input"].role == NodeRole.REACT
    assert nd["process"].role == NodeRole.PREDICT
