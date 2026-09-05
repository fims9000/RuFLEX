"""Typed, adapter-driven runtime boundary for RuFLEX.

The runtime is deliberately a computation boundary.  Canonical project objects
and their persistence remain owned by :mod:`ruflex.application`.
"""

from ruflex.runtime.registry import RuntimeRegistry, builtin_runtime_registry

__all__ = ["RuntimeRegistry", "builtin_runtime_registry"]
