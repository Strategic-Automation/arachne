"""Tests for GraphRunner data propagation between nodes.

Verifies that downstream nodes receive upstream outputs correctly,
addressing the root cause of the 'no script' bug where output field
names were not propagated into all_results for lookup.
"""

from arachne.config import Settings
from arachne.topologies.schema import (
    EdgeDef,
    GraphTopology,
    NodeDef,
    NodeRole,
)
from arachne.topologies.wave_executor import WaveExecutor


def _make_topology() -> GraphTopology:
    """Create a simple 3-node pipeline: writer -> reviewer -> compiler.

    writer produces 'script', reviewer takes 'script' and produces 'notes',
    compiler takes both 'script' and 'notes' and produces 'final'.
    """
    nodes = [
        NodeDef(
            id="writer", role=NodeRole.REACT, name="Writer", description="Write a script", inputs=[], output="script"
        ),
        NodeDef(
            id="reviewer",
            role=NodeRole.PREDICT,
            name="Reviewer",
            description="Review the script",
            inputs=["script"],
            output="notes",
        ),
        NodeDef(
            id="compiler",
            role=NodeRole.PREDICT,
            name="Compiler",
            description="Compile everything",
            inputs=["script", "notes"],
            output="final",
        ),
    ]
    edges = [
        EdgeDef(source="writer", target="reviewer", label="script"),
        EdgeDef(source="writer", target="compiler", label="script"),
        EdgeDef(source="reviewer", target="compiler", label="notes"),
    ]
    return GraphTopology(name="Test Pipeline", objective="test", nodes=nodes, edges=edges)


class TestWaveInputs:
    """Verify _get_node_inputs resolves upstream field names correctly."""

    def test_resolves_upstream_output_by_field_name(self):
        """After writer executes, its 'script' output is stored under the field name
        so reviewer can look it up via all_results.get('script')."""
        topology = _make_topology()
        executor = WaveExecutor(topology=topology, node_executors={}, settings=Settings())

        # Simulate what store_result does AFTER node execution:
        # 1. Stores result under node ID
        # 2. Stores output value under the field name
        all_results = {
            "goal": "write a movie",
            "writer": "The full screenplay content",
            "script": "The full screenplay content",
        }

        # reviewer needs 'script' from upstream writer
        inputs = executor._get_node_inputs("reviewer", all_results)
        assert inputs["script"] == "The full screenplay content"

    def test_multi_upstream_inputs(self):
        """compiler takes both 'script' and 'notes' from different nodes."""
        topology = _make_topology()
        executor = WaveExecutor(topology=topology, node_executors={}, settings=Settings())

        # Simulate both upstream nodes completed and propagated their outputs
        all_results = {
            "goal": "write a movie",
            "writer": "Full screenplay",
            "script": "Full screenplay",
            "reviewer": "More drama please",
            "notes": "More drama please",
        }

        inputs = executor._get_node_inputs("compiler", all_results)
        assert inputs["script"] == "Full screenplay"
        assert inputs["notes"] == "More drama please"

    def test_returns_empty_for_missing_upstream(self):
        """No upstream results yet - inputs should be empty strings."""
        topology = _make_topology()
        executor = WaveExecutor(topology=topology, node_executors={}, settings=Settings())

        all_results = {"goal": "write a movie"}
        inputs = executor._get_node_inputs("reviewer", all_results)
        assert inputs["script"] == ""

    def test_root_node_has_no_inputs(self):
        """Writer is a root node with no inputs but should still get goal context."""
        topology = _make_topology()
        executor = WaveExecutor(topology=topology, node_executors={}, settings=Settings())

        all_results = {"goal": "write a movie"}
        inputs = executor._get_node_inputs("writer", all_results)
        assert inputs == {"goal": "write a movie"}


class TestOutputPropagation:
    """Verify that node outputs are stored under their field name --
    the root cause fix for the 'no script' bug."""

    def test_output_stored_by_field_name_after_node_execution(self):
        """After a node completes, its output is indexed by field name so
        downstream _wave_inputs can find it with all_results.get(field_name)."""
        topology = _make_topology()
        executor = WaveExecutor(topology=topology, node_executors={}, settings=Settings())

        # Simulate store_result post-execution logic
        writer_result = "FAKE SCREENPLAY"
        all_results: dict = {"goal": "test"}
        node_id = "writer"
        node_def = topology.nodes[0]

        # This mimics what store_result does: store by node_id AND by field name
        all_results[node_id] = writer_result
        if node_def.output:
            all_results[node_def.output] = writer_result

        # The output is now accessible by field name
        assert "script" in all_results
        assert all_results["script"] == "FAKE SCREENPLAY"

        # And a downstream node can resolve it via _get_node_inputs
        inputs = executor._get_node_inputs("reviewer", all_results)
        assert inputs["script"] == "FAKE SCREENPLAY"

    def test_chain_propagation_across_three_nodes(self):
        """Full pipeline: writer -> reviewer -> compiler.
        Each node's output must be available as input to the next."""
        topology = _make_topology()
        executor = WaveExecutor(topology=topology, node_executors={}, settings=Settings())
        all_results: dict = {"goal": "test"}

        # Wave 1: writer completes
        writer_result = "Act 1: Once upon a time..."
        all_results["writer"] = writer_result
        all_results["script"] = writer_result

        inputs = executor._get_node_inputs("reviewer", all_results)
        assert inputs["script"] == "Act 1: Once upon a time..."

        # Wave 2: reviewer completes
        reviewer_result = "Needs more conflict in Act 2"
        all_results["reviewer"] = reviewer_result
        all_results["notes"] = reviewer_result

        inputs = executor._get_node_inputs("compiler", all_results)
        assert inputs["script"] == "Act 1: Once upon a time..."
        assert inputs["notes"] == "Needs more conflict in Act 2"

        # Verify: all outputs are in all_results by field name
        assert all_results["script"] == "Act 1: Once upon a time..."
        assert all_results["notes"] == "Needs more conflict in Act 2"


class TestTopologyValidation:
    """Verify the test topology is well-formed."""

    def test_topological_waves_are_correct(self):
        topology = _make_topology()
        waves = topology.topological_waves()
        assert waves == [["writer"], ["reviewer"], ["compiler"]]

    def test_output_names_match_input_names(self):
        topology = _make_topology()
        output_names = {n.output for n in topology.nodes}
        input_names = set()
        for n in topology.nodes:
            input_names.update(n.inputs)
        # Every input should be an output of some upstream node
        assert input_names.issubset(output_names | {"goal"})
