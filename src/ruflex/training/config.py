from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ruflex.core.enums import TaskType


@dataclass(frozen=True)
class BootstrapOptions:
    hidden_high: float = 0.85
    hidden_low: float = 0.15
    gate_floor: float = 0.25
    gate_ceiling: float = 0.85
    decision_binary_target_clip: float = 0.05

    def to_backend(self, backend: Any, task_type: TaskType):
        return backend.BootstrapConfig(
            hidden_high=self.hidden_high,
            hidden_low=self.hidden_low,
            gate_floor=self.gate_floor,
            gate_ceiling=self.gate_ceiling,
            decision_task_type=task_type.value,
            decision_binary_target_clip=self.decision_binary_target_clip,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hidden_high": self.hidden_high,
            "hidden_low": self.hidden_low,
            "gate_floor": self.gate_floor,
            "gate_ceiling": self.gate_ceiling,
            "decision_binary_target_clip": self.decision_binary_target_clip,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BootstrapOptions":
        return cls(**payload)


@dataclass(frozen=True)
class StagewiseOptions:
    epochs_per_stage: int = 40
    decision_epochs: int = 30
    refinement_rounds: int = 1
    learning_rate: float = 0.02
    batch_size: int | None = 64
    shuffle: bool = True
    rule_sparsity_weight: float = 0.0
    concept_orthogonality_weight: float = 0.0
    concept_binarization_weight: float = 0.0
    membership_order_weight: float = 0.0
    membership_min_gap: float = 0.0
    membership_overlap_weight: float = 0.0
    membership_max_overlap: float = 0.35
    membership_coverage_weight: float = 0.0
    membership_min_coverage: float = 0.6
    classification_target_clip: float = 0.05

    def to_backend(self, backend: Any, task_type: TaskType):
        return backend.StagewisePretrainingConfig(
            task_type=task_type.value,
            epochs_per_stage=self.epochs_per_stage,
            decision_epochs=self.decision_epochs,
            refinement_rounds=self.refinement_rounds,
            learning_rate=self.learning_rate,
            batch_size=self.batch_size,
            shuffle=self.shuffle,
            rule_sparsity_weight=self.rule_sparsity_weight,
            concept_orthogonality_weight=self.concept_orthogonality_weight,
            concept_binarization_weight=self.concept_binarization_weight,
            membership_order_weight=self.membership_order_weight,
            membership_min_gap=self.membership_min_gap,
            membership_overlap_weight=self.membership_overlap_weight,
            membership_max_overlap=self.membership_max_overlap,
            membership_coverage_weight=self.membership_coverage_weight,
            membership_min_coverage=self.membership_min_coverage,
            classification_target_clip=self.classification_target_clip,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StagewiseOptions":
        return cls(**payload)


@dataclass(frozen=True)
class FineTuningOptions:
    max_epochs: int = 120
    learning_rate: float = 1e-3
    batch_size: int | None = 64
    patience: int | None = 20
    min_delta: float = 0.0
    weight_decay: float = 0.0
    gradient_clip_norm: float | None = None
    shuffle: bool = True
    device: str | None = None
    classification_threshold: float = 0.5
    rule_sparsity_weight: float = 0.0
    rule_length_weight: float = 0.0
    concept_orthogonality_weight: float = 0.0
    concept_binarization_weight: float = 0.0
    membership_order_weight: float = 0.0
    membership_min_gap: float = 0.0
    membership_overlap_weight: float = 0.0
    membership_max_overlap: float = 0.35
    membership_coverage_weight: float = 0.0
    membership_min_coverage: float = 0.6
    prune_after_fit: bool = False
    prune_threshold: float = 0.1
    prune_temperature: float = 0.05
    prune_keep_at_least: int = 1

    def to_backend(self, backend: Any, task_type: TaskType):
        return backend.TrainingConfig(
            task_type=task_type.value,
            max_epochs=self.max_epochs,
            learning_rate=self.learning_rate,
            batch_size=self.batch_size,
            patience=self.patience,
            min_delta=self.min_delta,
            weight_decay=self.weight_decay,
            gradient_clip_norm=self.gradient_clip_norm,
            shuffle=self.shuffle,
            device=self.device,
            classification_threshold=self.classification_threshold,
            rule_sparsity_weight=self.rule_sparsity_weight,
            rule_length_weight=self.rule_length_weight,
            concept_orthogonality_weight=self.concept_orthogonality_weight,
            concept_binarization_weight=self.concept_binarization_weight,
            membership_order_weight=self.membership_order_weight,
            membership_min_gap=self.membership_min_gap,
            membership_overlap_weight=self.membership_overlap_weight,
            membership_max_overlap=self.membership_max_overlap,
            membership_coverage_weight=self.membership_coverage_weight,
            membership_min_coverage=self.membership_min_coverage,
            prune_after_fit=self.prune_after_fit,
            prune_threshold=self.prune_threshold,
            prune_temperature=self.prune_temperature,
            prune_keep_at_least=self.prune_keep_at_least,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FineTuningOptions":
        return cls(**payload)


@dataclass(frozen=True)
class RefinementOptions:
    cycles: int = 1
    patience: int | None = None
    min_delta: float = 0.0

    def to_backend_loop(self, backend: Any):
        return backend.RefinementLoopConfig(
            max_cycles=self.cycles,
            patience=self.patience,
            min_delta=self.min_delta,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RefinementOptions":
        return cls(**payload)


@dataclass(frozen=True)
class ModelTrainingConfig:
    task_type: TaskType = TaskType.REGRESSION
    use_bootstrap_initialization: bool = True
    use_stagewise_pretraining: bool = True
    bootstrap: BootstrapOptions = field(default_factory=BootstrapOptions)
    stagewise: StagewiseOptions = field(default_factory=StagewiseOptions)
    fine_tuning: FineTuningOptions = field(default_factory=FineTuningOptions)
    refinement: RefinementOptions = field(default_factory=RefinementOptions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "use_bootstrap_initialization": self.use_bootstrap_initialization,
            "use_stagewise_pretraining": self.use_stagewise_pretraining,
            "bootstrap": self.bootstrap.to_dict(),
            "stagewise": self.stagewise.to_dict(),
            "fine_tuning": self.fine_tuning.to_dict(),
            "refinement": self.refinement.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelTrainingConfig":
        return cls(
            task_type=TaskType(payload.get("task_type", TaskType.REGRESSION.value)),
            use_bootstrap_initialization=bool(payload.get("use_bootstrap_initialization", True)),
            use_stagewise_pretraining=bool(payload.get("use_stagewise_pretraining", True)),
            bootstrap=BootstrapOptions.from_dict(payload.get("bootstrap", {})),
            stagewise=StagewiseOptions.from_dict(payload.get("stagewise", {})),
            fine_tuning=FineTuningOptions.from_dict(payload.get("fine_tuning", {})),
            refinement=RefinementOptions.from_dict(payload.get("refinement", {})),
        )

