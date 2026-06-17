"""Arachne -- DSPy-native runtime harness for production AI agents."""

from arachne import config as _config


def _get_settings_deep_copy() -> _config.Settings:
    """Return an isolated settings model from the cached base instance."""
    return _config._get_settings_cached().model_copy(deep=True)


_config.get_settings = _get_settings_deep_copy
Settings = _config.Settings

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
