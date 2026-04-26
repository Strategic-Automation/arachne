"""DSPy optimizer modules for compiling Arachne programs.

This package contains build-time optimization tools that use DSPy optimizers
(BootstrapFewShot, MIPROv2, etc.) to improve the quality of Arachne's
graph weaving and node execution.

Runtime code should not import from this package directly — compiled outputs
are loaded via DSPy's native ``save()``/``load()`` in the relevant modules.
"""

from __future__ import annotations
