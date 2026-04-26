from unittest.mock import MagicMock, patch

import dspy

from arachne.execution.manager import ExecutionManager
from arachne.runtime.evaluator import TriangulatedEvaluator
from arachne.topologies.schema import (
    EdgeDef,
    GraphTopology,
    NodeDef,
    NodeResult,
    NodeRole,
    Question,
    QuestionType,
    ResultStatus,
    RunResult,
)


def test_rejection_reason(settings):
    # Setup dummy LM for DSPy
    dspy.configure(lm=dspy.LM("openai/gpt-4o-mini", api_key="sk-dummy"))

    # 1. Setup topology with HITL node and a REACT root
    nodes = [
        NodeDef(id="init", role=NodeRole.REACT, name="Init", description="Init", output="meta"),
        NodeDef(
            id="approve",
            role=NodeRole.HUMAN_IN_LOOP,
            name="Approval Gate",
            description="Verify output",
            output="approved",
            inputs=["meta"],
            question=Question(query="Accept?", type=QuestionType.CONFIRM),
        ),
    ]
    edges = [EdgeDef(source="init", target="approve")]
    topo = GraphTopology(name="test", objective="Verify result", nodes=nodes, edges=edges)

    # 2. Mock ExecutionManager's _default_ask_user or use a mock fn
    from arachne.topologies.weaver import GraphWeaver

    weaver = GraphWeaver(settings=settings)
    evaluator = TriangulatedEvaluator()
    manager = ExecutionManager(settings=settings, weaver=weaver, evaluator=evaluator)

    with patch("questionary.confirm") as mock_conf:
        mock_ask = MagicMock()
        mock_ask.ask.return_value = "no: Too academic"
        mock_conf.return_value = mock_ask

        result = manager._default_ask_user(nodes[1], {})
        assert result == "no: Too academic"

    # 3. Verify Evaluator flags the rejection
    run_res = RunResult(
        graph_name="test",
        goal="Explain QC",
        node_results=[
            NodeResult(node_id="approve", status=ResultStatus.COMPLETED, output={"approved": "no: Too academic"})
        ],
    )

    evaluator = TriangulatedEvaluator()
    eval_pred = evaluator(goal="Explain QC", run_result=run_res, topology=topo)
    report = eval_pred.report

    assert report.confidence_score == 0.0
    assert report.evaluation_source == "human_rejection"
    assert "Too academic" in report.diagnosis
    assert "Too academic" in report.evaluation_details["issues"]
