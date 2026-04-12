from __future__ import annotations

from ruflex.models.base import RuFLEXModel
from ruflex.models.specs import HierarchicalModelSpec
from ruflex.models.utils import to_backend_hierarchical_config


class DeepFuzzyFeatureLearningModel(RuFLEXModel):
    plain_builder_name = "build_hierarchical_model"
    bootstrap_builder_name = "build_bootstrapped_hierarchical_model"
    stagewise_builder_name = "build_stagewise_pretrained_hierarchical_model"
    refined_builder_name = "build_refined_hierarchical_model"

    def __init__(self, spec: HierarchicalModelSpec) -> None:
        super().__init__(spec=spec, kind="deep_fuzzy_feature_learning")

    def _to_backend_config(self, backend):
        return to_backend_hierarchical_config(backend, self.spec)

