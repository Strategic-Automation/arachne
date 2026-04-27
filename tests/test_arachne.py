"""Tests for Arachne -- pure DSPy-native modules."""

import inspect
from unittest.mock import MagicMock, patch

import dspy
import pytest

from arachne.core import Arachne
from arachne.runtime.evaluator import FailureEvaluator
from arachne.topologies.node_executor import NodeExecutor
from arachne.topologies.schema import (
    EdgeDef,
    GraphTopology,
    NodeDef,
    NodeRole,
)
from arachne.topologies.weaver import GraphWeaver


class TestNodeExecutor:
    def test_build_signature(self, settings):
        node = NodeDef(id="x", role=NodeRole.PREDICT, name="X", description="x", inputs=["src"], output="dst")
        mod = NodeExecutor(node, settings)
        sig = mod._build_signature()
        assert "src" in sig.input_fields
        assert "dst" in sig.output_fields

    def test_predict_module(self, settings):
        # Non-root node (has deps) so no ReAct promotion or Refine wrapping
        n = NodeDef(
            id="a",
            role=NodeRole.PREDICT,
            name="A",
            description="a",
            inputs=["goal"],
            output="y",
            depends_on=["upstream"],
        )
        executor = NodeExecutor(n, settings)
        module = executor._build_module()
        assert isinstance(module, dspy.Predict)

    def test_cot_module(self, settings):
        n = NodeDef(
            id="a",
            role=NodeRole.CHAIN_OF_THOUGHT,
            name="A",
            description="a",
            inputs=["goal"],
            output="y",
            depends_on=["upstream"],
        )
        executor = NodeExecutor(n, settings)
        module = executor._build_module()
        assert isinstance(module, dspy.Predict)

    def test_react_module(self, settings):
        n = NodeDef(
            id="a",
            role=NodeRole.REACT,
            name="A",
            description="a",
            inputs=["goal"],
            output="y",
            depends_on=["upstream"],
        )
        executor = NodeExecutor(n, settings)
        module = executor._build_module()
        inner = getattr(module, "module", None) or module
        assert isinstance(inner, dspy.ReAct)


class TestGraphWeaver:
    def test_init(self, settings):
        w = GraphWeaver(settings=settings)
        assert "chain_of_thought" in w._available_roles

    def test_forward(self, settings):
        w = GraphWeaver(settings=settings)
        mock_topo = GraphTopology(
            name="t",
            objective="o",
            nodes=[NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o")],
        )
        mock_clarification = dspy.Prediction(is_complete=True, clarifying_questions=[], reasoning="Complete")
        mock_selection = dspy.Prediction(selected_categories=["general"])

        with (
            patch.object(w.clarifier, "forward", return_value=mock_clarification),
            patch.object(w.selector, "forward", return_value=mock_selection),
            patch.object(w.weave, "forward", return_value=dspy.Prediction(topology=mock_topo, is_complete=True)),
        ):
            assert w(goal="g").topology.name == "t"

    def test_forward_sanitizes_failure_context(self, settings):
        w = GraphWeaver(settings=settings)
        mock_topo = GraphTopology(
            name="t",
            objective="o",
            nodes=[NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o")],
        )
        # Note: failure_context is provided, so clarifier is skipped in forward()
        mock_selection = dspy.Prediction(selected_categories=["general"])

        with (
            patch.object(w.selector, "forward", return_value=mock_selection),
            patch.object(w.weave, "forward", return_value=dspy.Prediction(topology=mock_topo, is_complete=True)),
        ):
            result = w(goal="g", failure_context="  \x00malicious\x00  ")
            assert "\x00" not in result.topology.name

    def test_forward_sanitizes_modifications(self, settings):
        w = GraphWeaver(settings=settings)
        mock_topo = GraphTopology(
            name="t",
            objective="o",
            nodes=[NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o")],
        )
        mock_clarification = dspy.Prediction(is_complete=True, clarifying_questions=[], reasoning="Complete")
        mock_selection = dspy.Prediction(selected_categories=["general"])

        with (
            patch.object(w.clarifier, "forward", return_value=mock_clarification),
            patch.object(w.selector, "forward", return_value=mock_selection),
            patch.object(w.weave, "forward", return_value=dspy.Prediction(topology=mock_topo, is_complete=True)),
        ):
            result = w(goal="g", modifications="a" * 6000)
            assert len(result.topology.name) > 0

    def test_forward_caches_tools(self, settings):
        w = GraphWeaver(settings=settings)
        original_tools = w._available_tools
        assert isinstance(original_tools, list)
        assert len(original_tools) > 0

    def test_fallback_tools_when_list_tools_fails(self, settings):
        with (
            patch("arachne.topologies.weaver.list_tools", side_effect=Exception("disk error")),
            pytest.raises(RuntimeError, match="Tool discovery failed"),
        ):
            GraphWeaver(settings=settings)


class TestArachneCore:
    def test_init(self, settings):
        a = Arachne(settings=settings, max_retries=2)
        assert a.max_retries == 2
        assert a.weaver is not None

    def test_weave(self, settings):
        a = Arachne(settings=settings)
        mock = GraphTopology(
            name="t",
            objective="o",
            nodes=[NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o")],
        )
        with patch.object(a.weaver, "forward", return_value=dspy.Prediction(topology=mock, is_complete=True)):
            assert a.weave(goal="g").name == "t"


class TestFailureEvaluator:
    def test_init(self):
        assert FailureEvaluator() is not None


class TestPydanticOutput:
    def test_pydantic_in_signature(self):
        from pydantic import BaseModel, Field

        class Out(BaseModel):
            r: str = Field(description="result")

        class Sig(dspy.Signature):
            """Test."""

            q: str = dspy.InputField()
            o: Out = dspy.OutputField()

        assert "q" in Sig.input_fields
        assert "o" in Sig.output_fields


class TestAsyncify:
    def test_dspy_asyncify(self):
        fn = dspy.asyncify(MagicMock(spec=dspy.Module))
        assert inspect.iscoroutinefunction(fn)

    def test_dspy_parallel(self):
        assert dspy.Parallel(num_threads=4) is not None


class TestWaves:
    def test_diamond(self):
        t = GraphTopology(
            name="d",
            objective="t",
            nodes=[
                NodeDef(id="a", role=NodeRole.REACT, name="A", description="d", output="o_a"),
                NodeDef(id="b", role=NodeRole.REACT, name="B", description="d", output="o_b"),
                NodeDef(id="m", role=NodeRole.PREDICT, name="M", description="d", output="o_m", inputs=["o_a", "o_b"]),
                NodeDef(id="f", role=NodeRole.PREDICT, name="F", description="d", output="o_f", inputs=["o_m"]),
            ],
            edges=[
                EdgeDef(source="a", target="m"),
                EdgeDef(source="b", target="m"),
                EdgeDef(source="m", target="f"),
            ],
        )
        waves = t.topological_waves()
        assert set(waves[0]) == {"a", "b"}
        assert waves[1] == ["m"]
        assert waves[2] == ["f"]
