from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ruflex.data.datasets import DataSplit
from ruflex.explain.payloads import (
    BlockDashboardPayload,
    DecisionConceptContributionPayload,
    ExplainabilityReportPayload,
    HiddenConceptPayload,
    RuleActivationPayload,
    RuleContributionPayload,
    RuleRecordPayload,
    SampleDashboardPayload,
    TermMembershipPayload,
    VariableFuzzificationPayload,
)
from ruflex.models.utils import import_ruanfis_backend
from ruflex.models.utils import (
    bootstrap_initialize_model_from_samples,
    build_backend_model_from_spec,
    spec_has_manual_rule_bases,
)
from ruflex.training.config import ModelTrainingConfig


@dataclass(frozen=True)
class EpochSummary:
    epoch: int
    train_loss: float
    train_metrics: dict[str, float]
    validation_loss: float | None = None
    validation_metrics: dict[str, float] | None = None


@dataclass(frozen=True)
class RefinementCycleSummary:
    cycle_index: int
    source: str
    monitor_name: str
    monitor_value: float
    train_loss: float
    train_metrics: dict[str, float]
    validation_loss: float | None = None
    validation_metrics: dict[str, float] | None = None


@dataclass(frozen=True)
class TrainingSummary:
    source: str
    epochs_ran: int
    best_epoch: int
    monitor_name: str
    best_monitor_value: float
    train_loss: float
    train_metrics: dict[str, float]
    validation_loss: float | None
    validation_metrics: dict[str, float] | None
    history: tuple[EpochSummary, ...]
    refinement_cycles: tuple[RefinementCycleSummary, ...] = ()

    @classmethod
    def from_backend_training_result(cls, result: Any, source: str) -> "TrainingSummary":
        history = tuple(
            EpochSummary(
                epoch=record.epoch,
                train_loss=record.train_loss,
                train_metrics=dict(record.train_metrics),
                validation_loss=record.validation_loss,
                validation_metrics=(
                    None if record.validation_metrics is None else dict(record.validation_metrics)
                ),
            )
            for record in result.history
        )
        return cls(
            source=source,
            epochs_ran=result.epochs_ran,
            best_epoch=result.best_epoch,
            monitor_name=result.monitor_name,
            best_monitor_value=result.best_monitor_value,
            train_loss=result.train_loss,
            train_metrics=dict(result.train_metrics),
            validation_loss=result.validation_loss,
            validation_metrics=None if result.validation_metrics is None else dict(result.validation_metrics),
            history=history,
            refinement_cycles=(),
        )

    @classmethod
    def from_backend_refinement_result(cls, result: Any) -> "TrainingSummary":
        base = cls.from_backend_training_result(result.training_result, source="refinement_loop")
        cycles = tuple(
            RefinementCycleSummary(
                cycle_index=record.cycle_index,
                source=record.source,
                monitor_name=record.monitor_name,
                monitor_value=record.monitor_value,
                train_loss=record.train_loss,
                train_metrics=dict(record.train_metrics),
                validation_loss=record.validation_loss,
                validation_metrics=(
                    None if record.validation_metrics is None else dict(record.validation_metrics)
                ),
            )
            for record in result.cycle_records
        )
        return cls(
            source=base.source,
            epochs_ran=base.epochs_ran,
            best_epoch=base.best_epoch,
            monitor_name=base.monitor_name,
            best_monitor_value=base.best_monitor_value,
            train_loss=base.train_loss,
            train_metrics=base.train_metrics,
            validation_loss=base.validation_loss,
            validation_metrics=base.validation_metrics,
            history=base.history,
            refinement_cycles=cycles,
        )

    def with_epoch_zero(
        self,
        *,
        train_loss: float,
        train_metrics: dict[str, float],
        validation_loss: float | None,
        validation_metrics: dict[str, float] | None,
    ) -> "TrainingSummary":
        epoch_zero = EpochSummary(
            epoch=0,
            train_loss=float(train_loss),
            train_metrics=dict(train_metrics),
            validation_loss=None if validation_loss is None else float(validation_loss),
            validation_metrics=None if validation_metrics is None else dict(validation_metrics),
        )
        return TrainingSummary(
            source=self.source,
            epochs_ran=self.epochs_ran,
            best_epoch=self.best_epoch,
            monitor_name=self.monitor_name,
            best_monitor_value=self.best_monitor_value,
            train_loss=self.train_loss,
            train_metrics=dict(self.train_metrics),
            validation_loss=self.validation_loss,
            validation_metrics=None if self.validation_metrics is None else dict(self.validation_metrics),
            history=(epoch_zero, *self.history),
            refinement_cycles=self.refinement_cycles,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "epochs_ran": self.epochs_ran,
            "best_epoch": self.best_epoch,
            "monitor_name": self.monitor_name,
            "best_monitor_value": self.best_monitor_value,
            "train_loss": self.train_loss,
            "train_metrics": dict(self.train_metrics),
            "validation_loss": self.validation_loss,
            "validation_metrics": None if self.validation_metrics is None else dict(self.validation_metrics),
            "history": [
                {
                    "epoch": entry.epoch,
                    "train_loss": entry.train_loss,
                    "train_metrics": dict(entry.train_metrics),
                    "validation_loss": entry.validation_loss,
                    "validation_metrics": None if entry.validation_metrics is None else dict(entry.validation_metrics),
                }
                for entry in self.history
            ],
            "refinement_cycles": [
                {
                    "cycle_index": cycle.cycle_index,
                    "source": cycle.source,
                    "monitor_name": cycle.monitor_name,
                    "monitor_value": cycle.monitor_value,
                    "train_loss": cycle.train_loss,
                    "train_metrics": dict(cycle.train_metrics),
                    "validation_loss": cycle.validation_loss,
                    "validation_metrics": None if cycle.validation_metrics is None else dict(cycle.validation_metrics),
                }
                for cycle in self.refinement_cycles
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TrainingSummary":
        history = tuple(
            EpochSummary(
                epoch=item["epoch"],
                train_loss=item["train_loss"],
                train_metrics=dict(item["train_metrics"]),
                validation_loss=item.get("validation_loss"),
                validation_metrics=(
                    None if item.get("validation_metrics") is None else dict(item["validation_metrics"])
                ),
            )
            for item in payload.get("history", ())
        )
        refinement_cycles = tuple(
            RefinementCycleSummary(
                cycle_index=item["cycle_index"],
                source=item["source"],
                monitor_name=item["monitor_name"],
                monitor_value=item["monitor_value"],
                train_loss=item["train_loss"],
                train_metrics=dict(item["train_metrics"]),
                validation_loss=item.get("validation_loss"),
                validation_metrics=(
                    None if item.get("validation_metrics") is None else dict(item["validation_metrics"])
                ),
            )
            for item in payload.get("refinement_cycles", ())
        )
        return cls(
            source=payload["source"],
            epochs_ran=payload["epochs_ran"],
            best_epoch=payload["best_epoch"],
            monitor_name=payload["monitor_name"],
            best_monitor_value=payload["best_monitor_value"],
            train_loss=payload["train_loss"],
            train_metrics=dict(payload["train_metrics"]),
            validation_loss=payload.get("validation_loss"),
            validation_metrics=(
                None if payload.get("validation_metrics") is None else dict(payload["validation_metrics"])
            ),
            history=history,
            refinement_cycles=refinement_cycles,
        )


class RuFLEXModel(ABC):
    plain_builder_name: str
    bootstrap_builder_name: str
    stagewise_builder_name: str
    refined_builder_name: str

    def __init__(self, spec: Any, kind: str) -> None:
        self.spec = spec
        self.kind = kind
        self.backend_model = None
        self.training_summary: TrainingSummary | None = None

    @abstractmethod
    def _to_backend_config(self, backend: Any):
        raise NotImplementedError

    def fit(self, split: DataSplit, training_config: ModelTrainingConfig) -> TrainingSummary:
        backend = import_ruanfis_backend()
        train_inputs = torch.as_tensor(split.train_features, dtype=torch.float32)
        train_targets = torch.as_tensor(split.train_targets, dtype=torch.float32)
        validation_inputs = None
        validation_targets = None
        if split.validation_features.shape[0] > 0:
            validation_inputs = torch.as_tensor(split.validation_features, dtype=torch.float32)
            validation_targets = torch.as_tensor(split.validation_targets, dtype=torch.float32)

        if spec_has_manual_rule_bases(self.spec):
            if training_config.refinement.cycles > 1:
                raise ValueError(
                    "Manual rule bases are not yet compatible with refinement cycles > 1 in the current RuFLEX layer."
                )

            model = build_backend_model_from_spec(backend, self.spec, sample_inputs=train_inputs)
            if training_config.use_bootstrap_initialization or training_config.use_stagewise_pretraining:
                bootstrap_initialize_model_from_samples(
                    backend,
                    model,
                    sample_inputs=train_inputs,
                    sample_targets=train_targets,
                    bootstrap_config=training_config.bootstrap.to_backend(backend, training_config.task_type),
                )

            trainer = backend.FuzzyTrainer(
                model,
                training_config.fine_tuning.to_backend(backend, training_config.task_type),
            )
            epoch_zero_train = trainer.evaluate(train_inputs, train_targets)
            epoch_zero_validation = (
                trainer.evaluate(validation_inputs, validation_targets)
                if validation_inputs is not None and validation_targets is not None
                else None
            )
            training_result = trainer.fit(
                train_inputs,
                train_targets,
                validation_inputs=validation_inputs,
                validation_targets=validation_targets,
            )
            self.backend_model = model
            source = (
                "manual_rule_base_initialization_plus_finetuning"
                if training_config.use_bootstrap_initialization or training_config.use_stagewise_pretraining
                else "manual_rule_base_finetuning"
            )
            self.training_summary = TrainingSummary.from_backend_training_result(training_result, source=source).with_epoch_zero(
                train_loss=epoch_zero_train.loss,
                train_metrics=epoch_zero_train.metrics,
                validation_loss=None if epoch_zero_validation is None else epoch_zero_validation.loss,
                validation_metrics=None if epoch_zero_validation is None else epoch_zero_validation.metrics,
            )
            return self.training_summary

        backend_config = self._to_backend_config(backend)

        if training_config.refinement.cycles > 1:
            refinement_result = getattr(backend, self.refined_builder_name)(
                backend_config,
                train_inputs=train_inputs,
                train_targets=train_targets,
                validation_inputs=validation_inputs,
                validation_targets=validation_targets,
                bootstrap_config=training_config.bootstrap.to_backend(backend, training_config.task_type),
                pretraining_config=training_config.stagewise.to_backend(backend, training_config.task_type),
                training_config=training_config.fine_tuning.to_backend(backend, training_config.task_type),
                refinement_cycles=training_config.refinement.cycles,
                refinement_loop_config=training_config.refinement.to_backend_loop(backend),
            )
            self.backend_model = refinement_result.model
            self.training_summary = TrainingSummary.from_backend_refinement_result(refinement_result)
            return self.training_summary

        if training_config.use_stagewise_pretraining:
            model = getattr(backend, self.stagewise_builder_name)(
                backend_config,
                sample_inputs=train_inputs,
                sample_targets=train_targets,
                bootstrap_config=training_config.bootstrap.to_backend(backend, training_config.task_type),
                pretraining_config=training_config.stagewise.to_backend(backend, training_config.task_type),
            )
            source = "stagewise_pretraining_plus_finetuning"
        elif training_config.use_bootstrap_initialization:
            model = getattr(backend, self.bootstrap_builder_name)(
                backend_config,
                sample_inputs=train_inputs,
                sample_targets=train_targets,
                bootstrap_config=training_config.bootstrap.to_backend(backend, training_config.task_type),
            )
            source = "bootstrap_plus_finetuning"
        else:
            model = getattr(backend, self.plain_builder_name)(backend_config, sample_inputs=train_inputs)
            source = "plain_build_plus_finetuning"

        trainer = backend.FuzzyTrainer(model, training_config.fine_tuning.to_backend(backend, training_config.task_type))
        epoch_zero_train = trainer.evaluate(train_inputs, train_targets)
        epoch_zero_validation = (
            trainer.evaluate(validation_inputs, validation_targets)
            if validation_inputs is not None and validation_targets is not None
            else None
        )
        training_result = trainer.fit(
            train_inputs,
            train_targets,
            validation_inputs=validation_inputs,
            validation_targets=validation_targets,
        )
        self.backend_model = model
        self.training_summary = TrainingSummary.from_backend_training_result(training_result, source=source).with_epoch_zero(
            train_loss=epoch_zero_train.loss,
            train_metrics=epoch_zero_train.metrics,
            validation_loss=None if epoch_zero_validation is None else epoch_zero_validation.loss,
            validation_metrics=None if epoch_zero_validation is None else epoch_zero_validation.metrics,
        )
        return self.training_summary

    def predict(self, features: np.ndarray) -> np.ndarray:
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        inputs = torch.as_tensor(self._as_feature_matrix(features), dtype=torch.float32)
        self.backend_model.eval()
        with torch.no_grad():
            predictions = self.backend_model(inputs)
        return predictions.detach().cpu().numpy()

    def explain(self, features: np.ndarray, top_k_rules: int = 2):
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        backend = import_ruanfis_backend()
        inputs = torch.as_tensor(self._as_feature_matrix(features), dtype=torch.float32)
        return backend.explain_samples(self.backend_model, inputs, top_k_rules=top_k_rules)

    def format_explanations(self, features: np.ndarray, top_k_rules: int = 2) -> str:
        backend = import_ruanfis_backend()
        return backend.format_sample_explanations(self.explain(features, top_k_rules=top_k_rules))

    def save_bundle(self, path: str | Path, metadata: dict[str, Any] | None = None) -> None:
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        backend = import_ruanfis_backend()
        backend.save_model_bundle(self.backend_model, path, metadata=metadata)

    def load_bundle(self, path: str | Path) -> None:
        backend = import_ruanfis_backend()
        bundle = backend.load_model_bundle(path)
        self.backend_model = bundle.model

    def trace(self, features: np.ndarray, top_k_rules: int | None = None):
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        inputs = torch.as_tensor(self._as_feature_matrix(features), dtype=torch.float32)
        return self.backend_model.forward_with_trace(inputs, top_k_rules=top_k_rules)

    def export_model_report(self, decimals: int = 3) -> str:
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        backend = import_ruanfis_backend()
        return backend.export_model_report(self.backend_model, decimals=decimals)

    def export_rule_records(self, decimals: int = 3) -> tuple[RuleRecordPayload, ...]:
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")

        records: list[RuleRecordPayload] = []
        for stage in self.backend_model.stages:
            for connected_block in stage.blocks:
                records.extend(
                    self._collect_rule_records(
                        layer=connected_block.block,
                        layer_kind="hidden",
                        stage_name=stage.name,
                        block_name=connected_block.block.name,
                        decimals=decimals,
                    )
                )
        records.extend(
            self._collect_rule_records(
                layer=self.backend_model.decision_layer,
                layer_kind="decision",
                stage_name=None,
                block_name=self.backend_model.decision_layer.name,
                decimals=decimals,
            )
        )
        return tuple(records)

    def explainability_report(self, decimals: int = 3) -> ExplainabilityReportPayload:
        return ExplainabilityReportPayload(
            model_kind=self.kind,
            model_report=self.export_model_report(decimals=decimals),
            rules=self.export_rule_records(decimals=decimals),
        )

    def concept_flow(self, features: np.ndarray, top_k_rules: int = 2):
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        backend = import_ruanfis_backend()
        inputs = torch.as_tensor(self._as_feature_matrix(features), dtype=torch.float32)
        return backend.analyze_concept_flow(self.backend_model, inputs, top_k_rules=top_k_rules)

    def format_concept_flow(self, features: np.ndarray, top_k_rules: int = 2, decimals: int = 4) -> str:
        backend = import_ruanfis_backend()
        return backend.format_concept_flows(self.concept_flow(features, top_k_rules=top_k_rules), decimals=decimals)

    def path_concept_flow(self, features: np.ndarray, top_k_rules: int = 2):
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        backend = import_ruanfis_backend()
        inputs = torch.as_tensor(self._as_feature_matrix(features), dtype=torch.float32)
        return backend.analyze_path_concept_flow(self.backend_model, inputs, top_k_rules=top_k_rules)

    def format_path_concept_flow(self, features: np.ndarray, top_k_rules: int = 2, decimals: int = 4) -> str:
        backend = import_ruanfis_backend()
        return backend.format_path_concept_flows(
            self.path_concept_flow(features, top_k_rules=top_k_rules),
            decimals=decimals,
        )

    def rule_chain_flow(self, features: np.ndarray, top_k_rules: int = 2):
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")
        backend = import_ruanfis_backend()
        inputs = torch.as_tensor(self._as_feature_matrix(features), dtype=torch.float32)
        return backend.analyze_rule_chain_flow(self.backend_model, inputs, top_k_rules=top_k_rules)

    def format_rule_chain_flow(self, features: np.ndarray, top_k_rules: int = 2, decimals: int = 4) -> str:
        backend = import_ruanfis_backend()
        return backend.format_rule_chain_flows(
            self.rule_chain_flow(features, top_k_rules=top_k_rules),
            decimals=decimals,
        )

    def explain_dashboard(
        self,
        features: np.ndarray,
        top_k_rules: int = 2,
        raw_inputs: list[dict[str, float]] | tuple[dict[str, float], ...] | None = None,
    ) -> tuple[SampleDashboardPayload, ...]:
        if self.backend_model is None:
            raise RuntimeError("The model has not been fitted yet.")

        backend = import_ruanfis_backend()
        inputs = torch.as_tensor(self._as_feature_matrix(features), dtype=torch.float32)
        predictions, trace = self.backend_model.forward_with_trace(inputs, top_k_rules=top_k_rules)
        concept_flows = backend.analyze_concept_flow(self.backend_model, inputs, top_k_rules=top_k_rules)

        sample_payloads: list[SampleDashboardPayload] = []
        for sample_index in range(inputs.size(0)):
            hidden_blocks: list[BlockDashboardPayload] = []
            for stage, stage_trace in zip(self.backend_model.stages, trace.stage_traces, strict=True):
                for connected_block, block_trace in zip(stage.blocks, stage_trace.block_traces, strict=True):
                    hidden_blocks.append(
                        self._build_block_dashboard(
                            layer=connected_block.block,
                            stage_name=stage.name,
                            layer_kind="hidden",
                            block_trace=block_trace,
                            sample_index=sample_index,
                            top_k_rules=top_k_rules,
                        )
                    )

            decision_block = self._build_block_dashboard(
                layer=self.backend_model.decision_layer,
                stage_name=None,
                layer_kind="decision",
                block_trace=trace.decision_trace,
                sample_index=sample_index,
                top_k_rules=top_k_rules,
            )

            concept_flow = concept_flows[sample_index]
            hidden_concepts = tuple(
                HiddenConceptPayload(
                    stage_name=item.stage_name,
                    block_name=item.block_name,
                    concept_name=item.concept_name,
                    value=item.value,
                    top_rule_contributions=tuple(
                        RuleContributionPayload(
                            rule_name=rule.rule_name,
                            rule_text=rule.rule_text,
                            normalized_weight=rule.normalized_weight,
                            contribution=(float(rule.contribution),),
                        )
                        for rule in item.top_rule_contributions
                    ),
                )
                for item in concept_flow.hidden_concepts
            )
            decision_concepts = tuple(
                DecisionConceptContributionPayload(
                    concept_name=item.concept_name,
                    source_stage_name=item.source_stage_name,
                    source_block_name=item.source_block_name,
                    concept_value=item.concept_value,
                    contribution=tuple(float(value) for value in item.contribution),
                )
                for item in concept_flow.decision_concept_contributions
            )
            top_decision_rules = tuple(
                RuleContributionPayload(
                    rule_name=rule.rule_name,
                    rule_text=rule.rule_text,
                    normalized_weight=rule.normalized_weight,
                    contribution=tuple(float(value) for value in rule.contribution),
                )
                for rule in concept_flow.top_decision_rules
            )

            sample_payloads.append(
                SampleDashboardPayload(
                    sample_index=sample_index,
                    raw_inputs=None if raw_inputs is None else dict(raw_inputs[sample_index]),
                    normalized_inputs=tuple(float(value) for value in inputs[sample_index].tolist()),
                    prediction=tuple(float(value) for value in predictions[sample_index].tolist()),
                    hidden_blocks=tuple(hidden_blocks),
                    decision_block=decision_block,
                    hidden_concepts=hidden_concepts,
                    decision_concept_contributions=decision_concepts,
                    bias_contribution=tuple(float(value) for value in concept_flow.bias_contribution),
                    top_decision_rules=top_decision_rules,
                )
            )
        return tuple(sample_payloads)

    def _build_block_dashboard(
        self,
        *,
        layer: Any,
        stage_name: str | None,
        layer_kind: str,
        block_trace: Any,
        sample_index: int,
        top_k_rules: int,
    ) -> BlockDashboardPayload:
        weights = block_trace.normalized_rule_weights[sample_index]
        raw_weights = block_trace.raw_rule_weights[sample_index]
        top_rule_count = min(top_k_rules, weights.numel())
        top_values, top_indices = weights.topk(k=top_rule_count)

        variable_fuzzification = tuple(
            VariableFuzzificationPayload(
                variable_name=variable_trace.variable_name,
                input_value=float(block_trace.inputs[sample_index, variable_index].item()),
                memberships=tuple(
                    TermMembershipPayload(
                        term_name=term_name,
                        membership=float(variable_trace.memberships[sample_index, term_index].item()),
                    )
                    for term_index, term_name in enumerate(variable_trace.term_names)
                ),
            )
            for variable_index, variable_trace in enumerate(block_trace.variable_traces)
        )

        top_rules = tuple(
            RuleActivationPayload(
                rule_name=block_trace.rule_names[rule_index],
                rule_text=layer.describe_rule(rule_index),
                normalized_weight=float(top_value),
                raw_weight=float(raw_weights[rule_index].item()),
                outputs=tuple(float(value) for value in block_trace.rule_outputs[sample_index, rule_index].tolist()),
            )
            for top_value, rule_index in zip(top_values.tolist(), top_indices.tolist(), strict=True)
        )

        return BlockDashboardPayload(
            stage_name=stage_name,
            block_name=block_trace.block_name,
            layer_kind=layer_kind,
            input_values=tuple(float(value) for value in block_trace.inputs[sample_index].tolist()),
            output_names=tuple(block_trace.output_names),
            output_values=tuple(float(value) for value in block_trace.outputs[sample_index].tolist()),
            variable_fuzzification=variable_fuzzification,
            top_rules=top_rules,
        )

    def _collect_rule_records(
        self,
        *,
        layer: Any,
        layer_kind: str,
        stage_name: str | None,
        block_name: str,
        decimals: int,
    ) -> list[RuleRecordPayload]:
        rules: list[RuleRecordPayload] = []
        gate_probabilities = layer.rule_probabilities.detach().cpu().tolist()

        for rule_index, rule_name in enumerate(layer.rule_base.names):
            antecedent = layer.describe_rule(rule_index)
            consequent = self._describe_consequent(layer, rule_index=rule_index, decimals=decimals)
            rules.append(
                RuleRecordPayload(
                    layer_kind=layer_kind,
                    stage_name=stage_name,
                    block_name=block_name,
                    rule_index=rule_index,
                    rule_name=rule_name,
                    antecedent=antecedent,
                    consequent=consequent,
                    gate_probability=float(gate_probabilities[rule_index]),
                )
            )
        return rules

    def _describe_consequent(self, layer: Any, rule_index: int, decimals: int) -> str:
        if hasattr(layer, "consequents"):
            values = layer.consequents[rule_index].detach().cpu().tolist()
            return ", ".join(
                f"{name}={value:.{decimals}f}"
                for name, value in zip(layer.output_names, values, strict=True)
            )

        if hasattr(layer, "rule_weights") and hasattr(layer, "rule_bias"):
            expressions = []
            variable_names = [variable.name for variable in layer.variables]
            for output_index, output_name in enumerate(layer.output_names):
                bias = float(layer.rule_bias[rule_index, output_index].detach().cpu().item())
                coefficients = layer.rule_weights[rule_index, :, output_index].detach().cpu().tolist()
                terms = [f"{bias:.{decimals}f}"]
                for coefficient, variable_name in zip(coefficients, variable_names, strict=True):
                    sign = "+" if coefficient >= 0.0 else "-"
                    terms.append(f" {sign} {abs(coefficient):.{decimals}f}*{variable_name}")
                expressions.append(f"{output_name} = {''.join(terms)}")
            return "; ".join(expressions)

        return ""

    def _as_feature_matrix(self, features: np.ndarray) -> np.ndarray:
        array = np.asarray(features, dtype=float)
        if array.ndim == 1:
            return array.reshape(1, -1)
        return array
