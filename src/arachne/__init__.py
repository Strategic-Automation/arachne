"""Arachne -- DSPy-native runtime harness for production AI agents."""

from arachne.config import Settings
from arachne.core import Arachne
from arachne.runtime.evaluator import FailureEvaluator
from arachne.topologies.schema import (
    EdgeDef,
    FailureReport,
    GraphTopology,
    NodeDef,
    NodeResult,
    RunResult,
)
from arachne.topologies.weaver import GraphWeaver

__version__ = "0.1.0"
__all__ = [
    "Arachne",
    "EdgeDef",
    "FailureEvaluator",
    "FailureReport",
    "GraphTopology",
    "GraphWeaver",
    "NodeDef",
    "NodeResult",
    "RunResult",
    "Settings",
]
