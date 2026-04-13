from __future__ import annotations

from typing import Sequence

import torch
from torch import Tensor, nn

from .blocks import SugenoDecisionLayer
from .stages import FuzzyStage
from .traces import ModelTrace


class DeepFuzzyFeatureModel(nn.Module):
    def __init__(
        self,
        stages: Sequence[FuzzyStage],
        decision_layer: SugenoDecisionLayer,
        input_dim: int | None = None,
        decision_input_mode: str = "final_only",
    ) -> None:
        super().__init__()
        self.stages = nn.ModuleList(stages)
        self.decision_layer = decision_layer
        self.input_dim = input_dim
        if decision_input_mode not in {"final_only", "all_stages", "raw_and_final", "raw_and_all_stages"}:
            raise ValueError(
                f"Unsupported decision_input_mode={decision_input_mode!r}. "
                "Expected 'final_only', 'all_stages', 'raw_and_final', or 'raw_and_all_stages'."
            )
        self.decision_input_mode = decision_input_mode
        if self.input_dim is not None:
            current_dim = self.input_dim
            stage_output_dims = []
            for stage in self.stages:
                stage.validate_input_dim(current_dim)
                current_dim = stage.output_dim
                stage_output_dims.append(current_dim)
            expected_decision_dim = self._expected_decision_dim(stage_output_dims, current_dim)
            if expected_decision_dim != self.decision_layer.input_dim:
                raise ValueError(
                    f"The configured decision input produces {expected_decision_dim} features, but the decision layer expects "
                    f"{self.decision_layer.input_dim}."
                )
        elif self.stages:
            stage_output_dims = [stage.output_dim for stage in self.stages]
            feature_dim = stage_output_dims[-1]
            expected_decision_dim = self._expected_decision_dim(stage_output_dims, feature_dim)
            if expected_decision_dim != self.decision_layer.input_dim:
                raise ValueError(
                    f"The configured decision input produces {expected_decision_dim} features, but the decision layer expects "
                    f"{self.decision_layer.input_dim}."
                )

    def _expected_decision_dim(self, stage_output_dims: Sequence[int], fallback_input_dim: int) -> int:
        if not stage_output_dims:
            return fallback_input_dim
        if self.decision_input_mode == "final_only":
            return stage_output_dims[-1]
        if self.decision_input_mode == "all_stages":
            return sum(stage_output_dims)
        if self.input_dim is None:
            raise ValueError("input_dim must be known when using raw feature decision input modes.")
        if self.decision_input_mode == "raw_and_final":
            return self.input_dim + stage_output_dims[-1]
        return self.input_dim + sum(stage_output_dims)

    def _compose_decision_inputs(self, raw_inputs: Tensor, stage_outputs: Sequence[Tensor]) -> Tensor:
        if not stage_outputs:
            return raw_inputs
        if self.decision_input_mode == "final_only":
            return stage_outputs[-1]
        if self.decision_input_mode == "all_stages":
            return torch.cat(tuple(stage_outputs), dim=1)
        if self.decision_input_mode == "raw_and_final":
            return torch.cat((raw_inputs, stage_outputs[-1]), dim=1)
        return torch.cat((raw_inputs, *tuple(stage_outputs)), dim=1)

    def forward_features(self, inputs: Tensor, top_k_rules: int | None = None) -> Tensor:
        features = inputs
        for stage in self.stages:
            features = stage(features, top_k_rules=top_k_rules)
        return features

    def forward(self, inputs: Tensor, top_k_rules: int | None = None) -> Tensor:
        features = inputs
        stage_outputs = []
        for stage in self.stages:
            features = stage(features, top_k_rules=top_k_rules)
            stage_outputs.append(features)
        decision_inputs = self._compose_decision_inputs(inputs, stage_outputs)
        return self.decision_layer(decision_inputs, top_k_rules=top_k_rules)

    def forward_with_trace(
        self,
        inputs: Tensor,
        top_k_rules: int | None = None,
    ) -> tuple[Tensor, ModelTrace]:
        features = inputs
        stage_traces = []
        stage_outputs = []
        for stage in self.stages:
            features, stage_trace = stage.forward_with_trace(features, top_k_rules=top_k_rules)
            stage_traces.append(stage_trace)
            stage_outputs.append(features)
        decision_inputs = self._compose_decision_inputs(inputs, stage_outputs)
        outputs, decision_trace = self.decision_layer.forward_with_trace(decision_inputs, top_k_rules=top_k_rules)
        trace = ModelTrace(stage_traces=tuple(stage_traces), decision_trace=decision_trace)
        return outputs, trace

    def explain(self, inputs: Tensor, top_k_rules: int | None = None) -> ModelTrace:
        _, trace = self.forward_with_trace(inputs, top_k_rules=top_k_rules)
        return trace
