"""Arachne -- DSPy-native runtime harness for production AI agents."""

from arachne import config as _config


def _get_settings_deep_copy() -> _config.Settings:
    """Return an isolated settings model from the cached base instance."""
    return _config._get_settings_cached().model_copy(deep=True)


_config.get_settings = _get_settings_deep_copy
Settings = _config.Settings

from arachne.core import Arachne  # noqa: E402
from arachne.runtime.evaluator import FailureEvaluator  # noqa: E402
from arachne.topologies.schema import (  # noqa: E402
    EdgeDef,
    FailureReport,
    GraphTopology,
    NodeDef,
    NodeResult,
    RunResult,
)
from arachne.topologies.weaver import GraphWeaver  # noqa: E402

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
