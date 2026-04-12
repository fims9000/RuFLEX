from __future__ import annotations

from ruflex.models.base import RuFLEXModel
from ruflex.models.specs import ShallowModelSpec
from ruflex.models.utils import to_backend_shallow_config


class FlatNeuroFuzzyModel(RuFLEXModel):
    plain_builder_name = "build_shallow_fuzzy_model"
    bootstrap_builder_name = "build_bootstrapped_shallow_model"
    stagewise_builder_name = "build_stagewise_pretrained_shallow_model"
    refined_builder_name = "build_refined_shallow_model"

    def __init__(self, spec: ShallowModelSpec) -> None:
        super().__init__(spec=spec, kind="flat_neuro_fuzzy")

    def _to_backend_config(self, backend):
        return to_backend_shallow_config(backend, self.spec)

