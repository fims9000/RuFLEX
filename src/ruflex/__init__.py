"""RuFLEX canonical package boundary.

The Studio path deliberately imports only this small Pydantic-domain surface.
Historical toolbox and deep-fuzzy exports remain lazily reachable for legacy
scripts, but never load merely because a Studio API module is imported.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .domain import Project, ProjectManifest, ProjectSummary

__all__ = ["Project", "ProjectManifest", "ProjectSummary"]


_LEGACY_MODULES = (
    "ruflex.toolbox",
    "ruflex.core.enums",
    "ruflex.core.membership",
    "ruflex.core.rules",
    "ruflex.core.variables",
    "ruflex.data.datasets",
    "ruflex.models.specs",
    "ruflex.training.config",
    "ruflex.explain.explainer",
    "ruflex.explain.payloads",
    "ruflex.experiments",
    "ruflex.visualization.plots",
    "ruflex.sdk.services",
)


def __getattr__(name: str) -> Any:
    """Resolve a legacy public symbol only when a legacy caller asks for it."""

    for module_name in _LEGACY_MODULES:
        module = import_module(module_name)
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value
    raise AttributeError(f"module 'ruflex' has no attribute {name!r}")
