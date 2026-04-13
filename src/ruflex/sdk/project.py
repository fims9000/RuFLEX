from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ruflex.core.enums import MembershipKind, NormalizationMode, TaskType, VariableRole
from ruflex.core.membership import (
    GaussianMembershipSpec,
    GeneralizedBellMembershipSpec,
    TrapezoidalMembershipSpec,
    TriangularMembershipSpec,
)
from ruflex.core.rules import AntecedentSpec, RuleBaseSpec, RuleSpec
from ruflex.core.variables import VariableSpec
from ruflex.data.datasets import DataSplit, DatasetConfig, NormalizationArtifact, TabularDataset
from ruflex.io.project import load_manifest, load_project_bundle, save_manifest, save_project_bundle
from ruflex.models.base import TrainingSummary
from ruflex.models.deep_fuzzy_feature_learning.model import DeepFuzzyFeatureLearningModel
from ruflex.models.flat_nf.model import FlatNeuroFuzzyModel
from ruflex.models.specs import (
    DecisionLayerSpec,
    HierarchicalModelSpec,
    ShallowModelSpec,
    StageSpec,
    TransparentBlockSpec,
    model_spec_from_dict,
)
from ruflex.training.config import FineTuningOptions, ModelTrainingConfig, RefinementOptions, StagewiseOptions


@dataclass
class Project:
    name: str
    task_type: str = TaskType.REGRESSION.value
    description: str | None = None

    def __post_init__(self) -> None:
        self.dataset: TabularDataset | None = None
        self.dataset_config: DatasetConfig | None = None
        self.variables: tuple[VariableSpec, ...] = ()
        self.model_spec: HierarchicalModelSpec | ShallowModelSpec | None = None
        self.model_kind: str | None = None
        self.model = None
        self.training_config: ModelTrainingConfig | None = None
        self.training_summary: TrainingSummary | None = None
        self.preprocessing: NormalizationArtifact | None = None
        self.last_split: DataSplit | None = None
        self.test_metrics: dict[str, float] | None = None
        self.notes: dict[str, Any] = {}

    def from_dataframe(
        self,
        frame: pd.DataFrame,
        *,
        target_column: str,
        feature_columns: tuple[str, ...] | None = None,
        validation_fraction: float = 0.2,
        test_fraction: float = 0.2,
        normalization: NormalizationMode = NormalizationMode.STANDARD,
        fill_missing: str = "median",
        random_state: int = 42,
    ) -> "Project":
        self.dataset = TabularDataset.from_dataframe(frame)
        self.variables = ()
        self.model_spec = None
        self.model_kind = None
        self.dataset_config = DatasetConfig(
            target_column=target_column,
            feature_columns=feature_columns,
            validation_fraction=validation_fraction,
            test_fraction=test_fraction,
            normalization=normalization,
            fill_missing=fill_missing,
            random_state=random_state,
        )
        self._invalidate_runtime_state()
        return self

    def from_csv(self, path: str | Path, **kwargs) -> "Project":
        self.dataset = TabularDataset.from_csv(path)
        self.variables = ()
        self.model_spec = None
        self.model_kind = None
        self.dataset_config = DatasetConfig(
            target_column=kwargs["target_column"],
            feature_columns=kwargs.get("feature_columns"),
            validation_fraction=kwargs.get("validation_fraction", 0.2),
            test_fraction=kwargs.get("test_fraction", 0.2),
            normalization=kwargs.get("normalization", NormalizationMode.STANDARD),
            fill_missing=kwargs.get("fill_missing", "median"),
            random_state=kwargs.get("random_state", 42),
        )
        self._invalidate_runtime_state()
        return self

    def use_dataset(
        self,
        dataset: TabularDataset,
        *,
        target_column: str,
        feature_columns: tuple[str, ...] | None = None,
        validation_fraction: float = 0.2,
        test_fraction: float = 0.2,
        normalization: NormalizationMode = NormalizationMode.STANDARD,
        fill_missing: str = "median",
        random_state: int = 42,
    ) -> "Project":
        self.dataset = dataset
        self.variables = ()
        self.model_spec = None
        self.model_kind = None
        self.dataset_config = DatasetConfig(
            target_column=target_column,
            feature_columns=feature_columns,
            validation_fraction=validation_fraction,
            test_fraction=test_fraction,
            normalization=normalization,
            fill_missing=fill_missing,
            random_state=random_state,
        )
        self._invalidate_runtime_state()
        return self

    def infer_variables(
        self,
        term_count: int = 3,
        membership_kind: str = MembershipKind.GAUSSIAN.value,
        normalization: NormalizationMode | None = None,
    ) -> "Project":
        if self.dataset is None or self.dataset_config is None:
            raise RuntimeError("Load a dataset before inferring variables.")
        if term_count <= 0:
            raise ValueError("term_count must be positive.")

        feature_columns = self.dataset_config.feature_columns or self.dataset.numeric_feature_columns(
            self.dataset_config.target_column
        )
        variables = []
        for column in feature_columns:
            series = self.dataset.frame[column].dropna().astype(float)
            low = float(series.min())
            high = float(series.max())
            membership = self._build_membership(
                kind=MembershipKind(membership_kind),
                low=low,
                high=high,
                term_count=term_count,
            )
            variables.append(
                VariableSpec(
                    name=column,
                    membership=membership,
                    value_range=(low, high),
                    role=VariableRole.INPUT,
                    normalization=normalization or self.dataset_config.normalization,
                )
            )
        self.variables = tuple(variables)
        if self.model_spec is not None:
            updated_spec = self._with_updated_input_variables(self.variables)
            self._validate_all_rule_bases(updated_spec)
            self.model_spec = updated_spec
        self._invalidate_runtime_state()
        return self

    def set_variables(self, variables: tuple[VariableSpec, ...] | list[VariableSpec]) -> "Project":
        if not variables:
            raise ValueError("variables must not be empty.")
        self.variables = tuple(variables)
        if self.model_spec is not None:
            updated_spec = self._with_updated_input_variables(self.variables)
            self._validate_all_rule_bases(updated_spec)
            self.model_spec = updated_spec
        self._invalidate_runtime_state()
        return self

    def get_variable(self, variable_name: str) -> VariableSpec:
        for variable in self.variables:
            if variable.name == variable_name:
                return variable
        raise KeyError(f"Variable {variable_name!r} was not found in the project.")

    def set_variable(self, variable_name: str, variable: VariableSpec) -> "Project":
        if variable.name != variable_name:
            raise ValueError(
                f"Variable payload name {variable.name!r} must match the target variable name {variable_name!r}."
            )
        updated_variables = []
        found = False
        for current in self.variables:
            if current.name == variable_name:
                updated_variables.append(variable)
                found = True
            else:
                updated_variables.append(current)
        if not found:
            raise KeyError(f"Variable {variable_name!r} was not found in the project.")
        self.variables = tuple(updated_variables)
        if self.model_spec is not None:
            updated_spec = self._with_updated_input_variables(self.variables)
            self._validate_all_rule_bases(updated_spec)
            self.model_spec = updated_spec
        self._invalidate_runtime_state()
        return self

    def variable_catalog(self) -> dict[str, Any]:
        return {variable.name: variable.to_dict() for variable in self.variables}

    def set_variable_catalog(
        self,
        catalog: dict[str, Any] | list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> "Project":
        if isinstance(catalog, dict):
            if self.variables:
                names = [variable.name for variable in self.variables]
                missing = [name for name in names if name not in catalog]
                extra = [name for name in catalog if name not in names]
                if missing:
                    raise ValueError(
                        f"Variable catalog is missing configured variables: {missing}."
                    )
                if extra:
                    raise ValueError(f"Variable catalog contains unknown variables: {extra}.")
                ordered_payloads = [catalog[name] for name in names]
            else:
                ordered_payloads = list(catalog.values())
        else:
            ordered_payloads = list(catalog)
        variables = tuple(VariableSpec.from_dict(item) for item in ordered_payloads)
        return self.set_variables(variables)

    def save_variable_catalog_json(self, path: str | Path) -> None:
        save_manifest(self.variable_catalog(), path)

    def load_variable_catalog_json(self, path: str | Path) -> "Project":
        return self.set_variable_catalog(load_manifest(path))

    def model_preset(self) -> dict[str, Any]:
        if self.model_spec is None or self.model_kind is None:
            raise RuntimeError("Configure a model before exporting a model preset.")
        return {
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "feature_names": list(self.feature_names),
            "target_name": self.target_name,
            "variables": [variable.to_dict() for variable in self.variables],
            "model_kind": self.model_kind,
            "model_spec": self.model_spec.to_dict(),
        }

    def apply_model_preset(self, payload: dict[str, Any]) -> "Project":
        variables = tuple(VariableSpec.from_dict(item) for item in payload.get("variables", ()))
        if not variables:
            raise ValueError("Model preset does not contain variables.")
        model_kind = payload.get("model_kind")
        if model_kind not in {"flat_neuro_fuzzy", "deep_fuzzy_feature_learning"}:
            raise ValueError(f"Unsupported model_kind in preset: {model_kind!r}.")
        model_spec_payload = payload.get("model_spec")
        if model_spec_payload is None:
            raise ValueError("Model preset does not contain model_spec.")
        model_spec = model_spec_from_dict(model_spec_payload)
        if model_spec.input_dim != len(variables):
            raise ValueError(
                f"Model preset input_dim={model_spec.input_dim} does not match variable_count={len(variables)}."
            )

        preset_feature_names = tuple(variable.name for variable in variables)
        if self.dataset_config is not None:
            current_feature_names = self.dataset_config.feature_columns
            if current_feature_names is None and self.dataset is not None:
                current_feature_names = self.dataset.numeric_feature_columns(self.dataset_config.target_column)
            if current_feature_names is not None and tuple(current_feature_names) != preset_feature_names:
                raise ValueError(
                    "Model preset feature names do not match the current project dataset features."
                )

        self.task_type = payload.get("task_type", self.task_type)
        self.description = payload.get("description", self.description)
        self.variables = variables
        self.model_kind = model_kind
        self.model_spec = model_spec
        self._validate_all_rule_bases(self.model_spec)
        self._invalidate_runtime_state()
        return self

    def save_model_preset_json(self, path: str | Path) -> None:
        save_manifest(self.model_preset(), path)

    def load_model_preset_json(self, path: str | Path) -> "Project":
        return self.apply_model_preset(load_manifest(path))

    def experiment_history(self) -> tuple[dict[str, Any], ...]:
        history = self.notes.get("experiment_history", ())
        return tuple(dict(item) for item in history)

    def clear_experiment_history(self) -> "Project":
        self.notes["experiment_history"] = []
        return self

    def study_run_history(self) -> tuple[dict[str, Any], ...]:
        history = self.notes.get("study_run_history", ())
        return tuple(dict(item) for item in history)

    def clear_study_run_history(self) -> "Project":
        self.notes["study_run_history"] = []
        return self

    def export_study_run_artifacts(
        self,
        root_dir: str | Path = "experiments",
        *,
        study_run_index: int = -1,
    ) -> dict[str, Any]:
        resolved_index, record = self._resolve_study_run_record(study_run_index)
        export_dir = self._study_artifact_directory(
            root_dir=root_dir,
            timestamp_utc=str(record["timestamp_utc"]),
            pipeline_name=str(record["pipeline_name"]),
        )
        export_dir.mkdir(parents=True, exist_ok=False)

        files: dict[str, str] = {}

        study_run_path = export_dir / "study_run.json"
        save_manifest(record, study_run_path)
        files["study_run"] = str(study_run_path)

        metrics_path = export_dir / "metrics.json"
        save_manifest(
            {
                "training_source": record.get("training_source"),
                "epochs_ran": record.get("epochs_ran"),
                "train_metrics": record.get("train_metrics"),
                "validation_metrics": record.get("validation_metrics"),
                "test_metrics": record.get("test_metrics"),
            },
            metrics_path,
        )
        files["metrics"] = str(metrics_path)

        project_manifest_path = export_dir / "project_manifest.json"
        save_manifest(dict(record.get("project_manifest") or self.to_manifest()), project_manifest_path)
        files["project_manifest"] = str(project_manifest_path)

        project_summary_path = export_dir / "project_summary.json"
        save_manifest(dict(record.get("project_summary") or self.summary()), project_summary_path)
        files["project_summary"] = str(project_summary_path)

        if record.get("dataset_summary") is not None or self.dataset is not None:
            dataset_summary_path = export_dir / "dataset_summary.json"
            save_manifest(dict(record.get("dataset_summary") or self.dataset_summary()), dataset_summary_path)
            files["dataset_summary"] = str(dataset_summary_path)

        if record.get("training_config") is not None or self.training_config is not None:
            training_config_path = export_dir / "training_config.json"
            save_manifest(dict(record.get("training_config") or self.training_config.to_dict()), training_config_path)
            files["training_config"] = str(training_config_path)

        if record.get("model_preset") is not None or (self.model_spec is not None and self.model_kind is not None):
            model_preset_path = export_dir / "model_preset.json"
            save_manifest(dict(record.get("model_preset") or self.model_preset()), model_preset_path)
            files["model_preset"] = str(model_preset_path)

            rule_base_catalog_path = export_dir / "rule_base_catalog.json"
            save_manifest(dict(record.get("rule_base_catalog") or self.rule_base_catalog()), rule_base_catalog_path)
            files["rule_base_catalog"] = str(rule_base_catalog_path)

        if record.get("variable_catalog") is not None or self.variables:
            variable_catalog_path = export_dir / "variable_catalog.json"
            save_manifest(dict(record.get("variable_catalog") or self.variable_catalog()), variable_catalog_path)
            files["variable_catalog"] = str(variable_catalog_path)

        pipeline_name = record.get("pipeline_name")
        if pipeline_name:
            pipeline_path = export_dir / "study_pipeline.json"
            try:
                pipeline_payload = self.study_pipeline(str(pipeline_name))
            except KeyError:
                pipeline_payload = {
                    "name": str(pipeline_name),
                    "label": record.get("pipeline_label"),
                    "workspace_template": record.get("workspace_template"),
                    "training_preset": record.get("training_preset"),
                    "training_preset_override": record.get("training_preset_override"),
                    "article_role": record.get("article_role"),
                    "kind": "ad_hoc_benchmark_variant",
                }
            save_manifest(pipeline_payload, pipeline_path)
            files["study_pipeline"] = str(pipeline_path)

        project_report_path = export_dir / "project_report.txt"
        project_report_path.write_text(
            str(record.get("project_report") or self.project_report()),
            encoding="utf-8",
        )
        files["project_report"] = str(project_report_path)

        model_report = record.get("model_report")
        if model_report is not None:
            model_report_path = export_dir / "model_report.txt"
            model_report_path.write_text(str(model_report), encoding="utf-8")
            files["model_report"] = str(model_report_path)

        if self.model is not None:
            project_bundle_dir = export_dir / "project_bundle"
            save_project_bundle(self, project_bundle_dir, include_dataset=True)
            files["project_bundle"] = str(project_bundle_dir)

        return {
            "study_run_index": resolved_index,
            "pipeline_name": record.get("pipeline_name"),
            "timestamp_utc": record.get("timestamp_utc"),
            "export_dir": str(export_dir),
            "files": files,
        }

    def list_exported_studies(self, root_dir: str | Path = "experiments") -> tuple[dict[str, Any], ...]:
        root = Path(root_dir).expanduser().resolve()
        if not root.exists():
            return ()

        exports = []
        for candidate in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True):
            study_run_path = candidate / "study_run.json"
            if not study_run_path.exists():
                continue
            record = load_manifest(study_run_path)
            project_summary = self._load_optional_artifact_manifest(candidate / "project_summary.json")
            exports.append(
                {
                    "export_dir": str(candidate),
                    "directory_name": candidate.name,
                    "pipeline_name": record.get("pipeline_name"),
                    "pipeline_label": record.get("pipeline_label"),
                    "timestamp_utc": record.get("timestamp_utc"),
                    "workspace_template": record.get("workspace_template"),
                    "training_preset": record.get("training_preset"),
                    "training_source": record.get("training_source"),
                    "epochs_ran": record.get("epochs_ran"),
                    "model_kind": None if project_summary is None else project_summary.get("model_kind"),
                    "project_name": None if project_summary is None else project_summary.get("name"),
                    "feature_count": None if project_summary is None else project_summary.get("feature_count"),
                    "manual_rule_targets": (
                        None if project_summary is None else project_summary.get("manual_rule_targets")
                    ),
                    "train_metrics": record.get("train_metrics"),
                    "validation_metrics": record.get("validation_metrics"),
                    "test_metrics": record.get("test_metrics"),
                    "available_files": tuple(sorted(path.name for path in candidate.iterdir() if path.is_file())),
                }
            )
        return tuple(exports)

    def load_exported_study(self, export_dir: str | Path) -> dict[str, Any]:
        root = Path(export_dir).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Experiment export directory was not found: {root}")
        study_run_path = root / "study_run.json"
        if not study_run_path.exists():
            raise FileNotFoundError(f"Experiment export is missing study_run.json: {root}")

        payload = {
            "export_dir": str(root),
            "available_files": tuple(sorted(path.name for path in root.iterdir() if path.is_file())),
            "available_directories": tuple(sorted(path.name for path in root.iterdir() if path.is_dir())),
            "study_run": load_manifest(study_run_path),
            "metrics": self._load_optional_artifact_manifest(root / "metrics.json"),
            "project_manifest": self._load_optional_artifact_manifest(root / "project_manifest.json"),
            "project_summary": self._load_optional_artifact_manifest(root / "project_summary.json"),
            "dataset_summary": self._load_optional_artifact_manifest(root / "dataset_summary.json"),
            "training_config": self._load_optional_artifact_manifest(root / "training_config.json"),
            "model_preset": self._load_optional_artifact_manifest(root / "model_preset.json"),
            "variable_catalog": self._load_optional_artifact_manifest(root / "variable_catalog.json"),
            "rule_base_catalog": self._load_optional_artifact_manifest(root / "rule_base_catalog.json"),
            "study_pipeline": self._load_optional_artifact_manifest(root / "study_pipeline.json"),
            "project_report": self._load_optional_artifact_text(root / "project_report.txt"),
            "model_report": self._load_optional_artifact_text(root / "model_report.txt"),
        }
        return payload

    def compare_exported_studies(self, root_dir: str | Path = "experiments") -> tuple[dict[str, Any], ...]:
        rows = []
        for item in self.list_exported_studies(root_dir):
            row = {
                "directory_name": item.get("directory_name"),
                "pipeline_name": item.get("pipeline_name"),
                "timestamp_utc": item.get("timestamp_utc"),
                "project_name": item.get("project_name"),
                "model_kind": item.get("model_kind"),
                "feature_count": item.get("feature_count"),
                "manual_rule_targets": item.get("manual_rule_targets"),
                "workspace_template": item.get("workspace_template"),
                "training_preset": item.get("training_preset"),
                "training_source": item.get("training_source"),
                "epochs_ran": item.get("epochs_ran"),
                "export_dir": item.get("export_dir"),
            }
            row.update(self._flatten_metric_block(item.get("train_metrics"), "train"))
            row.update(self._flatten_metric_block(item.get("validation_metrics"), "validation"))
            row.update(self._flatten_metric_block(item.get("test_metrics"), "test"))
            rows.append(row)
        return tuple(rows)

    def rank_exported_studies(
        self,
        root_dir: str | Path = "experiments",
        *,
        metric_name: str,
        higher_is_better: bool | None = None,
        split_priority: tuple[str, ...] = ("test", "validation", "train"),
    ) -> tuple[dict[str, Any], ...]:
        ranked_rows = []
        resolved_goal = self._metric_higher_is_better(metric_name, override=higher_is_better)

        for item in self.list_exported_studies(root_dir):
            split_name, metric_value = self._exported_metric_value(item, metric_name, split_priority)
            row = {
                **item,
                "ranking_metric": metric_name,
                "ranking_split": split_name,
                "ranking_value": metric_value,
                "higher_is_better": resolved_goal,
            }
            ranked_rows.append(row)

        sortable = []
        missing = []
        for row in ranked_rows:
            metric_value = row["ranking_value"]
            if metric_value is None:
                missing.append(row)
                continue
            score = float(metric_value) if resolved_goal else -float(metric_value)
            sortable.append((score, row))

        sortable.sort(key=lambda item: item[0], reverse=True)
        ordered_rows = [row for _, row in sortable] + missing
        for index, row in enumerate(ordered_rows, start=1):
            row["rank"] = index
        return tuple(ordered_rows)

    def best_exported_study(
        self,
        root_dir: str | Path = "experiments",
        *,
        metric_name: str,
        higher_is_better: bool | None = None,
        split_priority: tuple[str, ...] = ("test", "validation", "train"),
    ) -> dict[str, Any]:
        ranked = self.rank_exported_studies(
            root_dir,
            metric_name=metric_name,
            higher_is_better=higher_is_better,
            split_priority=split_priority,
        )
        if not ranked:
            raise RuntimeError("No exported studies were found under the selected experiment root.")
        best = ranked[0]
        if best["ranking_value"] is None:
            raise RuntimeError(
                f"No exported studies contain the metric {metric_name!r} in the requested split priority."
            )
        return dict(best)

    def apply_model_preset_from_exported_study(self, export_dir: str | Path) -> "Project":
        payload = self.load_exported_study(export_dir)
        model_preset = payload.get("model_preset")
        if model_preset is None:
            raise RuntimeError("The exported study does not contain model_preset.json.")
        return self.apply_model_preset(dict(model_preset))

    def list_workspace_templates(self) -> tuple[dict[str, Any], ...]:
        feature_count = self._feature_count_hint()
        compact_block_size = 1 if feature_count <= 1 else min(2, feature_count)
        research_block_size = 1 if feature_count <= 1 else min(3, feature_count)
        flat_baseline_concepts = max(1, min(3, feature_count))
        flat_interpretable_concepts = max(1, min(2, feature_count))
        deep_compact_stages = 1 if feature_count <= 2 else 2
        deep_article_stages = 1 if feature_count <= 3 else 2
        deep_research_stages = 3 if feature_count >= 6 else 2

        templates = (
            {
                "name": "flat_baseline",
                "label": "Flat Baseline",
                "description": "Compact flat neuro-fuzzy baseline for quick benchmarking.",
                "mode": "flat_neuro_fuzzy",
                "term_count": 3,
                "membership_kind": MembershipKind.GAUSSIAN.value,
                "config": {
                    "n_concepts": flat_baseline_concepts,
                    "max_rule_arity": 2,
                    "max_rules": max(4, min(8, feature_count * 2)),
                    "rule_generation_mode": "prototype",
                },
                "recommended_training_preset": "balanced",
            },
            {
                "name": "flat_interpretable",
                "label": "Flat Interpretable",
                "description": "Smaller flat model biased toward compact and readable rule bases.",
                "mode": "flat_neuro_fuzzy",
                "term_count": 3,
                "membership_kind": MembershipKind.GAUSSIAN.value,
                "config": {
                    "n_concepts": flat_interpretable_concepts,
                    "max_rule_arity": 2,
                    "max_rules": 4,
                    "rule_generation_mode": "prototype",
                },
                "recommended_training_preset": "interpretable",
            },
            {
                "name": "deep_compact",
                "label": "Deep Compact",
                "description": "A compact deep fuzzy feature learning stack for small and medium tables.",
                "mode": "deep_fuzzy_feature_learning",
                "term_count": 3,
                "membership_kind": MembershipKind.GAUSSIAN.value,
                "config": {
                    "block_size": compact_block_size,
                    "hidden_stage_count": deep_compact_stages,
                    "concept_width": 2,
                    "max_rule_arity": 2,
                    "max_rules": 4,
                    "rule_generation_mode": "prototype",
                },
                "recommended_training_preset": "balanced",
            },
            {
                "name": "deep_article_demo",
                "label": "Deep Article Demo",
                "description": "Reference deep fuzzy feature learning preset aligned with the article demo flow.",
                "mode": "deep_fuzzy_feature_learning",
                "term_count": 3,
                "membership_kind": MembershipKind.GAUSSIAN.value,
                "config": {
                    "block_size": compact_block_size,
                    "hidden_stage_count": deep_article_stages,
                    "concept_width": 2,
                    "max_rule_arity": 2,
                    "max_rules": 4,
                    "rule_generation_mode": "prototype",
                },
                "recommended_training_preset": "article_demo",
            },
            {
                "name": "deep_research",
                "label": "Deep Research",
                "description": "Broader deep fuzzy stack for exploratory studies with richer hidden concepts.",
                "mode": "deep_fuzzy_feature_learning",
                "term_count": 4,
                "membership_kind": MembershipKind.GENERALIZED_BELL.value,
                "config": {
                    "block_size": research_block_size,
                    "hidden_stage_count": deep_research_stages,
                    "concept_width": 3,
                    "max_rule_arity": 2,
                    "max_rules": 6,
                    "rule_generation_mode": "prototype",
                },
                "recommended_training_preset": "article_demo",
            },
        )
        return tuple(templates)

    def apply_workspace_template(self, template_name: str) -> "Project":
        if self.dataset is None or self.dataset_config is None:
            raise RuntimeError("Attach a dataset before applying a workspace template.")
        template = self._workspace_template_by_name(template_name)
        self.infer_variables(
            term_count=int(template["term_count"]),
            membership_kind=str(template["membership_kind"]),
        )
        self.configure_model(str(template["mode"]), **dict(template["config"]))
        return self

    def list_training_presets(self) -> tuple[dict[str, Any], ...]:
        deep_mode = self.model_kind == "deep_fuzzy_feature_learning"
        return (
            {
                "name": "fast_debug",
                "label": "Fast Debug",
                "description": "Short run for smoke checks and UI debugging.",
                "config": {
                    "use_bootstrap_initialization": True,
                    "use_stagewise_pretraining": False,
                    "fine_tuning": {
                        "max_epochs": 8,
                        "learning_rate": 2e-3,
                        "batch_size": 16,
                        "patience": 4,
                    },
                    "refinement": {"cycles": 1},
                    "stagewise": {"epochs_per_stage": 8, "decision_epochs": 6},
                },
                "recommended_for": ("debug", "smoke"),
            },
            {
                "name": "balanced",
                "label": "Balanced",
                "description": "Default training profile balancing speed and model quality.",
                "config": {
                    "use_bootstrap_initialization": True,
                    "use_stagewise_pretraining": deep_mode,
                    "fine_tuning": {
                        "max_epochs": 40 if deep_mode else 30,
                        "learning_rate": 1e-3,
                        "batch_size": 32,
                        "patience": 10,
                    },
                    "refinement": {"cycles": 1},
                    "stagewise": {"epochs_per_stage": 20, "decision_epochs": 15},
                },
                "recommended_for": ("default",),
            },
            {
                "name": "interpretable",
                "label": "Interpretable",
                "description": "Adds structure-aware regularization to favor compact and readable rules.",
                "config": {
                    "use_bootstrap_initialization": True,
                    "use_stagewise_pretraining": deep_mode,
                    "fine_tuning": {
                        "max_epochs": 48 if deep_mode else 36,
                        "learning_rate": 1e-3,
                        "batch_size": 32,
                        "patience": 12,
                        "rule_sparsity_weight": 1e-3,
                        "rule_length_weight": 1e-3,
                        "concept_orthogonality_weight": 1e-3,
                        "membership_order_weight": 5e-3,
                        "membership_overlap_weight": 1e-3,
                        "membership_coverage_weight": 1e-3,
                    },
                    "refinement": {"cycles": 1},
                    "stagewise": {"epochs_per_stage": 24, "decision_epochs": 18},
                },
                "recommended_for": ("interpretable", "compact"),
            },
            {
                "name": "article_demo",
                "label": "Article Demo",
                "description": "Reference research preset for the article-oriented deep fuzzy demonstration.",
                "config": {
                    "use_bootstrap_initialization": True,
                    "use_stagewise_pretraining": True if deep_mode else False,
                    "fine_tuning": {
                        "max_epochs": 28 if deep_mode else 24,
                        "learning_rate": 1e-3,
                        "batch_size": 32,
                        "patience": 8,
                        "rule_sparsity_weight": 5e-4,
                        "concept_orthogonality_weight": 5e-4,
                    },
                    "refinement": {"cycles": 1},
                    "stagewise": {"epochs_per_stage": 18, "decision_epochs": 14},
                },
                "recommended_for": ("demo", "article"),
            },
        )

    def training_preset(self, preset_name: str) -> ModelTrainingConfig:
        preset = self._training_preset_by_name(preset_name)
        config = preset["config"]
        base = self.default_training_config(
            stagewise=bool(config["use_stagewise_pretraining"]),
            refinement_cycles=int(config["refinement"]["cycles"]),
            max_epochs=int(config["fine_tuning"]["max_epochs"]),
            batch_size=int(config["fine_tuning"]["batch_size"]),
            learning_rate=float(config["fine_tuning"]["learning_rate"]),
        )
        return ModelTrainingConfig(
            task_type=TaskType(self.task_type),
            use_bootstrap_initialization=bool(config["use_bootstrap_initialization"]),
            use_stagewise_pretraining=bool(config["use_stagewise_pretraining"]),
            bootstrap=base.bootstrap,
            stagewise=StagewiseOptions(
                **{
                    **base.stagewise.to_dict(),
                    **dict(config.get("stagewise", {})),
                }
            ),
            fine_tuning=FineTuningOptions(
                **{
                    **base.fine_tuning.to_dict(),
                    **dict(config.get("fine_tuning", {})),
                }
            ),
            refinement=RefinementOptions(
                **{
                    **base.refinement.to_dict(),
                    **dict(config.get("refinement", {})),
                }
            ),
        )

    def list_study_pipelines(self) -> tuple[dict[str, Any], ...]:
        return (
            {
                "name": "quick_smoke",
                "label": "Quick Smoke",
                "description": "Fast end-to-end check using a compact deep model and short training.",
                "workspace_template": "deep_compact",
                "training_preset": "fast_debug",
                "outputs": ("project_report", "model_report"),
            },
            {
                "name": "flat_baseline_benchmark",
                "label": "Flat Baseline Benchmark",
                "description": "Reference flat neuro-fuzzy baseline with balanced training.",
                "workspace_template": "flat_baseline",
                "training_preset": "balanced",
                "outputs": ("project_report", "model_report"),
            },
            {
                "name": "interpretable_flat_study",
                "label": "Interpretable Flat Study",
                "description": "Compact flat model with interpretability-oriented regularization.",
                "workspace_template": "flat_interpretable",
                "training_preset": "interpretable",
                "outputs": ("project_report", "model_report"),
            },
            {
                "name": "deep_article_demo",
                "label": "Deep Article Demo",
                "description": "Article-style deep fuzzy feature learning run with the reference preset.",
                "workspace_template": "deep_article_demo",
                "training_preset": "article_demo",
                "outputs": ("project_report", "model_report"),
            },
            {
                "name": "deep_research_study",
                "label": "Deep Research Study",
                "description": "Richer deep fuzzy run for exploratory studies with broader hidden concepts.",
                "workspace_template": "deep_research",
                "training_preset": "article_demo",
                "outputs": ("project_report", "model_report"),
            },
        )

    def study_pipeline(self, pipeline_name: str) -> dict[str, Any]:
        return dict(self._study_pipeline_by_name(pipeline_name))

    def run_study_pipeline(
        self,
        pipeline_name: str,
        *,
        export_root: str | Path | None = None,
        training_preset_override: str | None = None,
    ) -> dict[str, Any]:
        if self.dataset is None or self.dataset_config is None:
            raise RuntimeError("Attach a dataset before running a study pipeline.")

        pipeline = self._study_pipeline_by_name(pipeline_name)
        self.apply_workspace_template(str(pipeline["workspace_template"]))
        resolved_training_preset = (
            str(training_preset_override)
            if training_preset_override is not None
            else str(pipeline["training_preset"])
        )
        training_config = self.training_preset(resolved_training_preset)
        summary = self.train(training_config=training_config)

        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_name": pipeline["name"],
            "pipeline_label": pipeline["label"],
            "workspace_template": pipeline["workspace_template"],
            "training_preset": resolved_training_preset,
            "training_preset_override": training_preset_override,
            "training_source": summary.source,
            "epochs_ran": int(summary.epochs_ran),
            "train_metrics": dict(summary.train_metrics),
            "validation_metrics": (
                None if summary.validation_metrics is None else dict(summary.validation_metrics)
            ),
            "test_metrics": None if self.test_metrics is None else dict(self.test_metrics),
            "training_config": training_config.to_dict(),
            "project_manifest": self.to_manifest(),
            "project_summary": dict(self.summary()),
            "dataset_summary": self.dataset_summary(),
            "variable_catalog": self.variable_catalog(),
            "rule_base_catalog": self.rule_base_catalog(),
            "model_preset": self.model_preset(),
            "project_report": self.project_report(),
            "model_report": self.model_report(),
        }
        history = list(self.notes.get("study_run_history", ()))
        history.append(record)
        self.notes["study_run_history"] = history
        if export_root is not None:
            record["artifact_export"] = self.export_study_run_artifacts(
                root_dir=export_root,
                study_run_index=len(history) - 1,
            )
            history[-1] = record
            self.notes["study_run_history"] = history
        return record

    def configure_model(self, mode: str, **kwargs) -> "Project":
        if mode == "flat_neuro_fuzzy":
            return self.configure_flat_model(**kwargs)
        if mode == "deep_fuzzy_feature_learning":
            return self.configure_deep_model(**kwargs)
        raise ValueError(
            f"Unsupported mode={mode!r}. Expected 'flat_neuro_fuzzy' or 'deep_fuzzy_feature_learning'."
        )

    def configure_flat_model(
        self,
        *,
        n_concepts: int | None = None,
        max_rule_arity: int = 2,
        max_rules: int = 8,
        rule_generation_mode: str = "prototype",
    ) -> "Project":
        self._require_variables()
        concept_count = n_concepts or max(1, min(4, len(self.variables)))
        concept_names = tuple(f"flat_concept_{index + 1}" for index in range(concept_count))
        feature_rule_arity = min(max_rule_arity, len(self.variables))
        feature_block = TransparentBlockSpec(
            name="flat_feature_block",
            input_indices=tuple(range(len(self.variables))),
            variables=self.variables,
            n_concepts=concept_count,
            concept_names=concept_names,
            max_rule_arity=feature_rule_arity,
            max_rules=max_rules,
            rule_generation_mode=rule_generation_mode,
        )
        decision_variables = tuple(self._make_concept_variable(name) for name in concept_names)
        decision_rule_arity = min(max_rule_arity, len(decision_variables))
        decision_layer = DecisionLayerSpec(
            name="flat_decision",
            variables=decision_variables,
            output_dim=1,
            output_names=("target",),
            max_rule_arity=decision_rule_arity,
            max_rules=max_rules,
            rule_generation_mode=rule_generation_mode,
        )
        self.model_spec = ShallowModelSpec(
            input_dim=len(self.variables),
            feature_block=feature_block,
            decision_layer=decision_layer,
            stage_name="flat_stage",
        )
        self.model_kind = "flat_neuro_fuzzy"
        self._invalidate_runtime_state()
        return self

    def configure_deep_model(
        self,
        *,
        block_size: int = 2,
        hidden_stage_count: int = 2,
        concept_width: int = 2,
        max_rule_arity: int = 2,
        max_rules: int = 4,
        rule_generation_mode: str = "prototype",
    ) -> "Project":
        self._require_variables()
        if block_size <= 0:
            raise ValueError("block_size must be positive.")
        if hidden_stage_count <= 0:
            raise ValueError("hidden_stage_count must be positive.")

        stages = []
        current_variables = list(self.variables)
        for stage_index in range(hidden_stage_count):
            blocks = []
            next_variables = []
            for block_index, start in enumerate(range(0, len(current_variables), block_size), start=1):
                local_variables = tuple(current_variables[start : start + block_size])
                local_rule_arity = min(max_rule_arity, len(local_variables))
                concept_names = tuple(
                    f"stage_{stage_index + 1}_block_{block_index}_concept_{concept_index + 1}"
                    for concept_index in range(max(1, concept_width))
                )
                blocks.append(
                    TransparentBlockSpec(
                        name=f"stage_{stage_index + 1}_block_{block_index}",
                        input_indices=tuple(range(start, start + len(local_variables))),
                        variables=local_variables,
                        n_concepts=len(concept_names),
                        concept_names=concept_names,
                        max_rule_arity=local_rule_arity,
                        max_rules=max_rules,
                        rule_generation_mode=rule_generation_mode,
                    )
                )
                next_variables.extend(self._make_concept_variable(name) for name in concept_names)
            stages.append(StageSpec(name=f"stage_{stage_index + 1}", blocks=tuple(blocks)))
            current_variables = next_variables

        decision_rule_arity = min(max_rule_arity, len(current_variables))
        decision_layer = DecisionLayerSpec(
            name="deep_decision",
            variables=tuple(current_variables),
            output_dim=1,
            output_names=("target",),
            max_rule_arity=decision_rule_arity,
            max_rules=max(max_rules, 4),
            rule_generation_mode=rule_generation_mode,
        )
        self.model_spec = HierarchicalModelSpec(
            input_dim=len(self.variables),
            stages=tuple(stages),
            decision_layer=decision_layer,
        )
        self.model_kind = "deep_fuzzy_feature_learning"
        self._invalidate_runtime_state()
        return self

    def list_rule_targets(self) -> tuple[dict[str, Any], ...]:
        if self.model_spec is None:
            return ()
        targets = []
        if self.model_kind == "flat_neuro_fuzzy":
            targets.append(
                {
                    "layer_kind": "hidden",
                    "stage_name": self.model_spec.stage_name,
                    "block_name": self.model_spec.feature_block.name,
                    "variable_names": tuple(variable.name for variable in self.model_spec.feature_block.variables),
                    "variable_terms": {
                        variable.name: variable.term_names for variable in self.model_spec.feature_block.variables
                    },
                    "output_names": self.model_spec.feature_block.concept_names
                    or tuple(f"concept_{index + 1}" for index in range(self.model_spec.feature_block.n_concepts)),
                    "max_rule_arity": self.model_spec.feature_block.max_rule_arity,
                    "max_rules": self.model_spec.feature_block.max_rules,
                }
            )
        else:
            for stage in self.model_spec.stages:
                for block in stage.blocks:
                    targets.append(
                        {
                            "layer_kind": "hidden",
                            "stage_name": stage.name,
                            "block_name": block.name,
                            "variable_names": tuple(variable.name for variable in block.variables),
                            "variable_terms": {variable.name: variable.term_names for variable in block.variables},
                            "output_names": block.concept_names or tuple(
                                f"concept_{index + 1}" for index in range(block.n_concepts)
                            ),
                            "max_rule_arity": block.max_rule_arity,
                            "max_rules": block.max_rules,
                        }
                    )
        decision = self._decision_layer_spec()
        targets.append(
            {
                "layer_kind": "decision",
                "stage_name": None,
                "block_name": decision.name,
                "variable_names": tuple(variable.name for variable in decision.variables),
                "variable_terms": {variable.name: variable.term_names for variable in decision.variables},
                "output_names": decision.output_names or tuple(f"output_{index + 1}" for index in range(decision.output_dim)),
                "max_rule_arity": decision.max_rule_arity,
                "max_rules": decision.max_rules,
            }
        )
        return tuple(targets)

    def get_block_rule_base(self, block_name: str, stage_name: str | None = None) -> RuleBaseSpec | None:
        if self.model_spec is None:
            raise RuntimeError("Configure a model before accessing block rule bases.")
        if self.model_kind == "flat_neuro_fuzzy":
            if block_name != self.model_spec.feature_block.name:
                raise KeyError(f"Unknown block: {block_name!r}.")
            if stage_name is not None and stage_name != self.model_spec.stage_name:
                raise KeyError(f"Unknown stage: {stage_name!r}.")
            return self.model_spec.feature_block.rule_base

        matches = []
        for stage in self.model_spec.stages:
            if stage_name is not None and stage.name != stage_name:
                continue
            for block in stage.blocks:
                if block.name == block_name:
                    matches.append(block.rule_base)
        if not matches:
            raise KeyError(f"Unknown block: {block_name!r}.")
        if len(matches) > 1 and stage_name is None:
            raise KeyError(f"Block name {block_name!r} is ambiguous. Provide stage_name.")
        return matches[0]

    def set_block_rule_base(
        self,
        block_name: str,
        rule_base: RuleBaseSpec | None,
        *,
        stage_name: str | None = None,
    ) -> "Project":
        if self.model_spec is None:
            raise RuntimeError("Configure a model before setting block rule bases.")
        if self.model_kind == "flat_neuro_fuzzy":
            if block_name != self.model_spec.feature_block.name:
                raise KeyError(f"Unknown block: {block_name!r}.")
            if stage_name is not None and stage_name != self.model_spec.stage_name:
                raise KeyError(f"Unknown stage: {stage_name!r}.")
            candidate_spec = replace(
                self.model_spec,
                feature_block=replace(self.model_spec.feature_block, rule_base=rule_base),
            )
            self._validate_all_rule_bases(candidate_spec)
            self.model_spec = candidate_spec
            self._invalidate_runtime_state()
            return self

        found = False
        new_stages = []
        for stage in self.model_spec.stages:
            new_blocks = []
            for block in stage.blocks:
                if block.name == block_name and (stage_name is None or stage.name == stage_name):
                    new_blocks.append(replace(block, rule_base=rule_base))
                    found = True
                else:
                    new_blocks.append(block)
            new_stages.append(replace(stage, blocks=tuple(new_blocks)))
        if not found:
            raise KeyError(f"Unknown block: {block_name!r}.")
        candidate_spec = replace(self.model_spec, stages=tuple(new_stages))
        self._validate_all_rule_bases(candidate_spec)
        self.model_spec = candidate_spec
        self._invalidate_runtime_state()
        return self

    def get_decision_rule_base(self) -> RuleBaseSpec | None:
        return self._decision_layer_spec().rule_base if self.model_spec is not None else None

    def set_decision_rule_base(self, rule_base: RuleBaseSpec | None) -> "Project":
        if self.model_spec is None:
            raise RuntimeError("Configure a model before setting decision rule bases.")
        candidate_spec = replace(
            self.model_spec,
            decision_layer=replace(self.model_spec.decision_layer, rule_base=rule_base),
        )
        self._validate_all_rule_bases(candidate_spec)
        self.model_spec = candidate_spec
        self._invalidate_runtime_state()
        return self

    def clear_all_rule_bases(self) -> "Project":
        if self.model_spec is None:
            raise RuntimeError("Configure a model before clearing rule bases.")
        if self.model_kind == "flat_neuro_fuzzy":
            self.model_spec = replace(
                self.model_spec,
                feature_block=replace(self.model_spec.feature_block, rule_base=None),
                decision_layer=replace(self.model_spec.decision_layer, rule_base=None),
            )
            self._invalidate_runtime_state()
            return self
        self.model_spec = replace(
            self.model_spec,
            stages=tuple(
                replace(stage, blocks=tuple(replace(block, rule_base=None) for block in stage.blocks))
                for stage in self.model_spec.stages
            ),
            decision_layer=replace(self.model_spec.decision_layer, rule_base=None),
        )
        self._invalidate_runtime_state()
        return self

    def rule_base_catalog(self) -> dict[str, Any]:
        catalog: dict[str, Any] = {}
        for target in self.list_rule_targets():
            key = self._rule_target_key(target["block_name"], target["stage_name"], target["layer_kind"])
            if target["layer_kind"] == "decision":
                rule_base = self.get_decision_rule_base()
            else:
                rule_base = self.get_block_rule_base(target["block_name"], stage_name=target["stage_name"])
            catalog[key] = None if rule_base is None else rule_base.to_dict()
        return catalog

    def set_rule_base_catalog(
        self,
        catalog: dict[str, Any],
        *,
        clear_missing: bool = False,
    ) -> "Project":
        if self.model_spec is None:
            raise RuntimeError("Configure a model before setting a rule-base catalog.")
        targets = {
            self._rule_target_key(target["block_name"], target["stage_name"], target["layer_kind"]): target
            for target in self.list_rule_targets()
        }
        unknown = [key for key in catalog if key not in targets]
        if unknown:
            raise ValueError(f"Rule-base catalog contains unknown targets: {unknown}.")

        if clear_missing:
            self.clear_all_rule_bases()

        for key, payload in catalog.items():
            target = targets[key]
            rule_base = None if payload is None else RuleBaseSpec.from_dict(payload)
            if target["layer_kind"] == "decision":
                self.set_decision_rule_base(rule_base)
            else:
                self.set_block_rule_base(
                    target["block_name"],
                    rule_base,
                    stage_name=target["stage_name"],
                )
        return self

    def save_rule_base_catalog_json(self, path: str | Path) -> None:
        save_manifest(self.rule_base_catalog(), path)

    def load_rule_base_catalog_json(self, path: str | Path, *, clear_missing: bool = False) -> "Project":
        return self.set_rule_base_catalog(load_manifest(path), clear_missing=clear_missing)

    def make_rule_template(
        self,
        *,
        block_name: str,
        stage_name: str | None = None,
        layer_kind: str = "hidden",
    ) -> RuleBaseSpec:
        if layer_kind == "decision":
            decision = self._decision_layer_spec()
            antecedents = tuple(
                AntecedentSpec(variable_name=variable.name, term_name=variable.term_names[0])
                for variable in decision.variables[: min(2, len(decision.variables))]
            )
            consequent = {}
            output_names = decision.output_names or tuple(f"output_{index + 1}" for index in range(decision.output_dim))
            if output_names:
                if len(output_names) == 1:
                    consequent["bias"] = 0.0
                else:
                    consequent[f"bias:{output_names[0]}"] = 0.0
            return RuleBaseSpec(
                rules=(
                    RuleSpec(
                        identifier=f"{decision.name}_rule_1",
                        antecedents=antecedents,
                        weight=0.5,
                        consequent=consequent,
                        layer_name=decision.name,
                    ),
                )
            )

        block_spec = self._find_block_spec(block_name, stage_name=stage_name)
        antecedents = tuple(
            AntecedentSpec(variable_name=variable.name, term_name=variable.term_names[0])
            for variable in block_spec.variables[: min(2, len(block_spec.variables))]
        )
        output_names = block_spec.concept_names or tuple(f"concept_{index + 1}" for index in range(block_spec.n_concepts))
        consequent = {output_names[0]: 0.8} if output_names else {}
        return RuleBaseSpec(
            rules=(
                RuleSpec(
                    identifier=f"{block_spec.name}_rule_1",
                    antecedents=antecedents,
                    weight=0.5,
                    consequent=consequent,
                    layer_name=block_spec.name,
                ),
            )
        )

    def default_training_config(
        self,
        *,
        stagewise: bool | None = None,
        refinement_cycles: int = 1,
        max_epochs: int = 120,
        batch_size: int | None = 64,
        learning_rate: float = 1e-3,
    ) -> ModelTrainingConfig:
        task_type = TaskType(self.task_type)
        use_stagewise = (
            self.model_kind == "deep_fuzzy_feature_learning" if stagewise is None else bool(stagewise)
        )
        return ModelTrainingConfig(
            task_type=task_type,
            use_stagewise_pretraining=use_stagewise,
            fine_tuning=FineTuningOptions(
                max_epochs=max_epochs,
                batch_size=batch_size,
                learning_rate=learning_rate,
            ),
            refinement=RefinementOptions(cycles=refinement_cycles),
        )

    def train(self, training_config: ModelTrainingConfig | None = None) -> TrainingSummary:
        if self.dataset is None or self.dataset_config is None:
            raise RuntimeError("Load a dataset before training.")
        if self.model_spec is None or self.model_kind is None:
            raise RuntimeError("Configure a model before training.")

        effective_training = training_config or ModelTrainingConfig(task_type=TaskType(self.task_type))
        split = self.dataset.split(self.dataset_config)
        model = self._make_model()
        summary = model.fit(split, effective_training)
        self.model = model
        self.training_config = effective_training
        self.training_summary = summary
        self.preprocessing = split.normalization
        self.last_split = split
        self.test_metrics = self._compute_metrics(split.test_targets, model.predict(split.test_features))
        self._append_experiment_record(summary)
        return summary

    def evaluate(self, features: pd.DataFrame | np.ndarray, targets: pd.DataFrame | np.ndarray) -> dict[str, float]:
        predictions = self.predict(features)
        return self._compute_metrics(np.asarray(targets, dtype=float), predictions)

    def predict(self, features: pd.DataFrame | np.ndarray) -> np.ndarray:
        if self.model is None or self.preprocessing is None:
            raise RuntimeError("Train or load a project before prediction.")
        transformed = self._transform_features(features)
        return self.model.predict(transformed)

    def explain(self, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2, as_text: bool = False):
        if self.model is None or self.preprocessing is None:
            raise RuntimeError("Train or load a project before explanation.")
        transformed = self._transform_features(features)
        if as_text:
            return self.model.format_explanations(transformed, top_k_rules=top_k_rules)
        return self.model.explain(transformed, top_k_rules=top_k_rules)

    def dashboard(self, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2):
        if self.model is None or self.preprocessing is None:
            raise RuntimeError("Train or load a project before explanation.")
        transformed = self._transform_features(features)
        return self.model.explain_dashboard(
            transformed,
            top_k_rules=top_k_rules,
            raw_inputs=self._raw_input_rows(features),
        )

    def concept_flow(self, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2, as_text: bool = False):
        if self.model is None or self.preprocessing is None:
            raise RuntimeError("Train or load a project before explanation.")
        transformed = self._transform_features(features)
        if as_text:
            return self.model.format_concept_flow(transformed, top_k_rules=top_k_rules)
        return self.model.concept_flow(transformed, top_k_rules=top_k_rules)

    def path_concept_flow(self, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2, as_text: bool = False):
        if self.model is None or self.preprocessing is None:
            raise RuntimeError("Train or load a project before explanation.")
        transformed = self._transform_features(features)
        if as_text:
            return self.model.format_path_concept_flow(transformed, top_k_rules=top_k_rules)
        return self.model.path_concept_flow(transformed, top_k_rules=top_k_rules)

    def rule_chain_flow(self, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2, as_text: bool = False):
        if self.model is None or self.preprocessing is None:
            raise RuntimeError("Train or load a project before explanation.")
        transformed = self._transform_features(features)
        if as_text:
            return self.model.format_rule_chain_flow(transformed, top_k_rules=top_k_rules)
        return self.model.rule_chain_flow(transformed, top_k_rules=top_k_rules)

    def model_report(self, decimals: int = 3) -> str:
        if self.model is None:
            raise RuntimeError("Train or load a project before exporting a model report.")
        return self.model.export_model_report(decimals=decimals)

    def rule_records(self, decimals: int = 3):
        if self.model is None:
            raise RuntimeError("Train or load a project before exporting rules.")
        return self.model.export_rule_records(decimals=decimals)

    def explainability_report(self, decimals: int = 3):
        if self.model is None:
            raise RuntimeError("Train or load a project before exporting an explainability report.")
        return self.model.explainability_report(decimals=decimals)

    def project_report(self, decimals: int = 3) -> str:
        lines = [
            "PROJECT REPORT",
            f"name: {self.name}",
            f"task_type: {self.task_type}",
            f"model_kind: {self.model_kind}",
        ]
        if self.dataset is not None:
            lines.append(f"dataset_rows: {len(self.dataset.frame)}")
            lines.append(f"dataset_columns: {len(self.dataset.frame.columns)}")
        if self.training_summary is not None:
            lines.append(f"training_source: {self.training_summary.source}")
            lines.append(f"train_metrics: {self.training_summary.train_metrics}")
            if self.training_summary.validation_metrics is not None:
                lines.append(f"validation_metrics: {self.training_summary.validation_metrics}")
        if self.test_metrics is not None:
            lines.append(f"test_metrics: {self.test_metrics}")
        if self.model is not None:
            lines.append("")
            lines.append(self.model_report(decimals=decimals))
        return "\n".join(lines)

    def save(self, path: str | Path, include_dataset: bool = False) -> None:
        save_project_bundle(self, path, include_dataset=include_dataset)

    def save_manifest_json(self, path: str | Path) -> None:
        save_manifest(self.to_manifest(), path)

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        return load_project_bundle(path)

    @classmethod
    def load_manifest_json(cls, path: str | Path, frame: pd.DataFrame | None = None) -> "Project":
        return cls.from_manifest(load_manifest(path), frame=frame)

    @classmethod
    def load_project_from_exported_study(
        cls,
        export_dir: str | Path,
        frame: pd.DataFrame | None = None,
    ) -> "Project":
        root = Path(export_dir).expanduser().resolve()
        bundle_dir = root / "project_bundle"
        if bundle_dir.exists() and frame is None:
            return load_project_bundle(bundle_dir)
        manifest_path = root / "project_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Exported study is missing project_manifest.json: {root}")

        manifest = load_manifest(manifest_path)
        resolved_frame = cls._resolve_exported_study_frame(root, manifest, frame)
        if resolved_frame is not None:
            cls._validate_manifest_frame(manifest, resolved_frame)
        return cls.from_manifest(manifest, frame=resolved_frame)

    @property
    def target_name(self) -> str | None:
        return None if self.dataset_config is None else self.dataset_config.target_column

    @property
    def feature_names(self) -> tuple[str, ...]:
        if self.dataset_config is not None and self.dataset_config.feature_columns is not None:
            return self.dataset_config.feature_columns
        return tuple(variable.name for variable in self.variables)

    def summary(self) -> dict[str, Any]:
        dataset_rows = None if self.dataset is None else int(len(self.dataset.frame))
        dataset_columns = None if self.dataset is None else int(len(self.dataset.frame.columns))
        variable_roles: dict[str, int] = {}
        for variable in self.variables:
            variable_roles[variable.role.value] = variable_roles.get(variable.role.value, 0) + 1
        return {
            "name": self.name,
            "task_type": self.task_type,
            "model_kind": self.model_kind,
            "target_name": self.target_name,
            "feature_count": len(self.feature_names),
            "variable_count": len(self.variables),
            "variable_roles": variable_roles,
            "dataset_rows": dataset_rows,
            "dataset_columns": dataset_columns,
            "has_model": self.model is not None,
            "has_training_summary": self.training_summary is not None,
            "experiment_count": len(self.experiment_history()),
            "study_run_count": len(self.study_run_history()),
            "manual_rule_targets": sum(
                1 for value in self.rule_base_catalog().values() if value is not None
            ) if self.model_spec is not None else 0,
            "test_metrics": self.test_metrics,
        }

    def dataset_summary(self) -> dict[str, Any]:
        if self.dataset is None:
            raise RuntimeError("No dataset is attached to the project.")
        frame = self.dataset.frame
        numeric = frame.select_dtypes(include=[np.number])
        missing = {column: int(value) for column, value in frame.isna().sum().to_dict().items()}
        return {
            "rows": int(len(frame)),
            "columns": tuple(frame.columns),
            "numeric_columns": tuple(numeric.columns),
            "missing_values": missing,
            "target_name": self.target_name,
        }

    def to_manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task_type": self.task_type,
            "description": self.description,
            "dataset_config": None if self.dataset_config is None else self.dataset_config.to_dict(),
            "variables": [variable.to_dict() for variable in self.variables],
            "model_kind": self.model_kind,
            "model_spec": None if self.model_spec is None else self.model_spec.to_dict(),
            "training_config": None if self.training_config is None else self.training_config.to_dict(),
            "training_summary": None if self.training_summary is None else self.training_summary.to_dict(),
            "preprocessing": None if self.preprocessing is None else self.preprocessing.to_dict(),
            "test_metrics": self.test_metrics,
            "dataset_source_path": None if self.dataset is None else self.dataset.source_path,
            "notes": dict(self.notes),
        }

    @classmethod
    def from_manifest(cls, payload: dict[str, Any], frame: pd.DataFrame | None = None) -> "Project":
        project = cls(
            name=payload["name"],
            task_type=payload.get("task_type", TaskType.REGRESSION.value),
            description=payload.get("description"),
        )
        dataset_config = payload.get("dataset_config")
        if dataset_config is not None:
            project.dataset_config = DatasetConfig.from_dict(dataset_config)
        if frame is not None:
            project.dataset = TabularDataset.from_dataframe(frame)
        project.variables = tuple(VariableSpec.from_dict(item) for item in payload.get("variables", ()))
        if payload.get("model_spec") is not None:
            project.model_spec = model_spec_from_dict(payload["model_spec"])
        project.model_kind = payload.get("model_kind")
        if payload.get("training_config") is not None:
            project.training_config = ModelTrainingConfig.from_dict(payload["training_config"])
        if payload.get("training_summary") is not None:
            project.training_summary = TrainingSummary.from_dict(payload["training_summary"])
        if payload.get("preprocessing") is not None:
            project.preprocessing = NormalizationArtifact.from_dict(payload["preprocessing"])
        project.test_metrics = payload.get("test_metrics")
        project.notes = dict(payload.get("notes", {}))
        return project

    def _load_model_bundle(self, path: str | Path) -> None:
        self.model = self._make_model()
        self.model.load_bundle(path)

    def _make_model(self):
        if self.model_kind == "flat_neuro_fuzzy":
            return FlatNeuroFuzzyModel(self.model_spec)
        if self.model_kind == "deep_fuzzy_feature_learning":
            return DeepFuzzyFeatureLearningModel(self.model_spec)
        raise ValueError(f"Unsupported model_kind: {self.model_kind!r}.")

    def _require_variables(self) -> None:
        if not self.variables:
            raise RuntimeError("Infer or define variables before configuring the model.")

    def _transform_features(self, features: pd.DataFrame | np.ndarray) -> np.ndarray:
        if self.preprocessing is None:
            raise RuntimeError("No preprocessing artifact is available.")
        if isinstance(features, pd.DataFrame):
            return self.preprocessing.transform_frame(features)
        array = np.asarray(features, dtype=float)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        return self.preprocessing.transform_array(array)

    def _raw_input_rows(self, features: pd.DataFrame | np.ndarray) -> list[dict[str, float]]:
        if isinstance(features, pd.DataFrame):
            return [
                {column: float(row[column]) for column in self.feature_names}
                for _, row in features.loc[:, list(self.feature_names)].iterrows()
            ]
        array = np.asarray(features, dtype=float)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        return [
            {name: float(row[index]) for index, name in enumerate(self.feature_names)}
            for row in array
        ]

    def _compute_metrics(self, targets: np.ndarray, predictions: np.ndarray) -> dict[str, float]:
        targets = np.asarray(targets, dtype=float).reshape(-1)
        predictions = np.asarray(predictions, dtype=float).reshape(-1)
        if TaskType(self.task_type) is TaskType.REGRESSION:
            diff = predictions - targets
            mse = float(np.mean(diff**2))
            mae = float(np.mean(np.abs(diff)))
            rmse = float(np.sqrt(mse))
            denom = float(np.sum((targets - targets.mean()) ** 2))
            r2 = float(1.0 - (np.sum(diff**2) / (denom + 1e-12)))
            return {"mse": mse, "mae": mae, "rmse": rmse, "r2": r2}
        probabilities = 1.0 / (1.0 + np.exp(-predictions))
        predicted_labels = (probabilities >= 0.5).astype(float)
        target_labels = (targets >= 0.5).astype(float)
        accuracy = float(np.mean(predicted_labels == target_labels))
        true_positive = float(np.sum((predicted_labels == 1.0) & (target_labels == 1.0)))
        false_positive = float(np.sum((predicted_labels == 1.0) & (target_labels == 0.0)))
        false_negative = float(np.sum((predicted_labels == 0.0) & (target_labels == 1.0)))
        precision = true_positive / (true_positive + false_positive + 1e-12)
        recall = true_positive / (true_positive + false_negative + 1e-12)
        f1 = 2.0 * precision * recall / (precision + recall + 1e-12)
        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }

    def _build_membership(
        self,
        *,
        kind: MembershipKind,
        low: float,
        high: float,
        term_count: int,
    ):
        if np.isclose(low, high):
            high = low + 1.0
        centers = np.linspace(low, high, term_count)
        term_names = tuple(f"term_{index + 1}" for index in range(term_count))
        span = max(high - low, 1e-6)
        if kind is MembershipKind.GAUSSIAN:
            spread = span / max(term_count - 1, 1)
            return GaussianMembershipSpec(
                centers=tuple(float(value) for value in centers),
                spreads=tuple(float(max(spread, 1e-3)) for _ in range(term_count)),
                term_names=term_names,
            )
        if kind is MembershipKind.GENERALIZED_BELL:
            width = span / max(term_count, 1)
            return GeneralizedBellMembershipSpec(
                centers=tuple(float(value) for value in centers),
                widths=tuple(float(max(width, 1e-3)) for _ in range(term_count)),
                slopes=tuple(2.0 for _ in range(term_count)),
                term_names=term_names,
            )
        if kind is MembershipKind.TRIANGULAR:
            step = span / max(term_count - 1, 1)
            return TriangularMembershipSpec(
                left=tuple(float(value - step) for value in centers),
                center=tuple(float(value) for value in centers),
                right=tuple(float(value + step) for value in centers),
                term_names=term_names,
            )
        step = span / max(term_count - 1, 1)
        return TrapezoidalMembershipSpec(
            left=tuple(float(value - step) for value in centers),
            left_top=tuple(float(value - step / 2.0) for value in centers),
            right_top=tuple(float(value + step / 2.0) for value in centers),
            right=tuple(float(value + step) for value in centers),
            term_names=term_names,
        )

    def _make_concept_variable(self, name: str) -> VariableSpec:
        return VariableSpec(
            name=name,
            membership=GaussianMembershipSpec(
                centers=(0.25, 0.75),
                spreads=(0.20, 0.20),
                term_names=("low", "high"),
            ),
            value_range=(0.0, 1.0),
            role=VariableRole.HIDDEN_CONCEPT,
            normalization=NormalizationMode.NONE,
        )

    def _invalidate_runtime_state(self) -> None:
        self.model = None
        self.training_summary = None
        self.preprocessing = None
        self.last_split = None
        self.test_metrics = None

    def _feature_count_hint(self) -> int:
        if self.variables:
            return len(self.variables)
        if self.dataset_config is not None:
            if self.dataset_config.feature_columns is not None:
                return len(self.dataset_config.feature_columns)
            if self.dataset is not None:
                return len(self.dataset.numeric_feature_columns(self.dataset_config.target_column))
        return 1

    def _workspace_template_by_name(self, template_name: str) -> dict[str, Any]:
        for template in self.list_workspace_templates():
            if template["name"] == template_name:
                return template
        raise KeyError(f"Unknown workspace template: {template_name!r}.")

    def _training_preset_by_name(self, preset_name: str) -> dict[str, Any]:
        for preset in self.list_training_presets():
            if preset["name"] == preset_name:
                return preset
        raise KeyError(f"Unknown training preset: {preset_name!r}.")

    def _study_pipeline_by_name(self, pipeline_name: str) -> dict[str, Any]:
        for pipeline in self.list_study_pipelines():
            if pipeline["name"] == pipeline_name:
                return pipeline
        raise KeyError(f"Unknown study pipeline: {pipeline_name!r}.")

    def _resolve_study_run_record(self, study_run_index: int) -> tuple[int, dict[str, Any]]:
        history = self.study_run_history()
        if not history:
            raise RuntimeError("Run a study pipeline before exporting study-run artifacts.")
        try:
            resolved_index = range(len(history))[study_run_index]
        except IndexError as exc:
            raise IndexError(
                f"study_run_index={study_run_index} is out of range for {len(history)} study runs."
            ) from exc
        return resolved_index, dict(history[resolved_index])

    def _study_artifact_directory(
        self,
        *,
        root_dir: str | Path,
        timestamp_utc: str,
        pipeline_name: str,
    ) -> Path:
        root = Path(root_dir).expanduser().resolve()
        timestamp_token = self._artifact_slug(timestamp_utc.replace(":", "-"))
        pipeline_token = self._artifact_slug(pipeline_name)
        base_dir = root / f"{timestamp_token}_{pipeline_token}"
        if not base_dir.exists():
            return base_dir
        suffix = 2
        while True:
            candidate = root / f"{timestamp_token}_{pipeline_token}_{suffix}"
            if not candidate.exists():
                return candidate
            suffix += 1

    def _artifact_slug(self, value: str) -> str:
        slug = "".join(character if character.isalnum() else "_" for character in value.strip().lower())
        slug = slug.strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "artifact"

    def _load_optional_artifact_manifest(self, path: Path) -> dict[str, Any] | None:
        return load_manifest(path) if path.exists() else None

    def _load_optional_artifact_text(self, path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _flatten_metric_block(self, payload: dict[str, Any] | None, prefix: str) -> dict[str, Any]:
        if payload is None:
            return {}
        return {f"{prefix}_{key}": value for key, value in payload.items()}

    def _exported_metric_value(
        self,
        exported_study: dict[str, Any],
        metric_name: str,
        split_priority: tuple[str, ...],
    ) -> tuple[str | None, float | None]:
        for split_name in split_priority:
            payload = exported_study.get(f"{split_name}_metrics")
            if payload is None:
                continue
            if metric_name in payload and payload[metric_name] is not None:
                return split_name, float(payload[metric_name])
        return None, None

    def _metric_higher_is_better(self, metric_name: str, override: bool | None = None) -> bool:
        if override is not None:
            return bool(override)
        return metric_name.lower() in {"accuracy", "precision", "recall", "f1", "r2"}

    def _append_experiment_record(self, summary: TrainingSummary) -> None:
        history = list(self.notes.get("experiment_history", ()))
        history.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "model_kind": self.model_kind,
                "training_source": summary.source,
                "epochs_ran": int(summary.epochs_ran),
                "best_epoch": int(summary.best_epoch),
                "train_metrics": dict(summary.train_metrics),
                "validation_metrics": (
                    None if summary.validation_metrics is None else dict(summary.validation_metrics)
                ),
                "test_metrics": None if self.test_metrics is None else dict(self.test_metrics),
                "manual_rule_targets": (
                    sum(1 for value in self.rule_base_catalog().values() if value is not None)
                    if self.model_spec is not None
                    else 0
                ),
                "feature_names": list(self.feature_names),
            }
        )
        self.notes["experiment_history"] = history

    @staticmethod
    def _resolve_exported_study_frame(
        root: Path,
        manifest: dict[str, Any],
        frame: pd.DataFrame | None,
    ) -> pd.DataFrame | None:
        if frame is not None:
            return frame

        bundled_candidates = (
            root / "dataset.csv",
            root / "artifacts" / "dataset.csv",
        )
        for candidate in bundled_candidates:
            if candidate.exists():
                return pd.read_csv(candidate)

        source_path = manifest.get("dataset_source_path")
        if source_path:
            source_candidate = Path(source_path)
            if source_candidate.exists() and source_candidate.suffix.lower() == ".csv":
                return pd.read_csv(source_candidate)
        return None

    @staticmethod
    def _validate_manifest_frame(manifest: dict[str, Any], frame: pd.DataFrame) -> None:
        columns = set(str(column) for column in frame.columns)
        dataset_config = manifest.get("dataset_config") or {}
        target_name = dataset_config.get("target_column")
        if target_name is not None and target_name not in columns:
            raise ValueError(
                f"The provided frame does not contain the exported target column {target_name!r}."
            )

        feature_columns = dataset_config.get("feature_columns")
        if feature_columns:
            missing_features = [name for name in feature_columns if name not in columns]
            if missing_features:
                raise ValueError(
                    f"The provided frame is missing exported feature columns: {missing_features}."
                )
            return

        variable_names = [item.get("name") for item in manifest.get("variables", ()) if item.get("name") is not None]
        missing_variables = [name for name in variable_names if name not in columns]
        if missing_variables:
            raise ValueError(
                f"The provided frame is missing exported variables: {missing_variables}."
            )

    def _with_updated_input_variables(
        self,
        variables: tuple[VariableSpec, ...],
    ) -> HierarchicalModelSpec | ShallowModelSpec:
        if self.model_spec is None:
            raise RuntimeError("No model is configured.")
        if len(variables) != self.model_spec.input_dim:
            raise ValueError(
                f"Expected {self.model_spec.input_dim} input variables, received {len(variables)}."
            )

        if self.model_kind == "flat_neuro_fuzzy":
            return replace(
                self.model_spec,
                feature_block=replace(self.model_spec.feature_block, variables=tuple(variables)),
            )

        updated_stages = []
        for stage_index, stage in enumerate(self.model_spec.stages):
            if stage_index > 0:
                updated_stages.append(stage)
                continue
            updated_blocks = []
            for block in stage.blocks:
                local_variables = []
                for input_index in block.input_indices:
                    if input_index >= len(variables):
                        raise ValueError(
                            f"Block {block.name!r} references input index {input_index}, "
                            f"but only {len(variables)} input variables are available."
                        )
                    local_variables.append(variables[input_index])
                updated_blocks.append(replace(block, variables=tuple(local_variables)))
            updated_stages.append(replace(stage, blocks=tuple(updated_blocks)))
        return replace(self.model_spec, stages=tuple(updated_stages))

    def _validate_all_rule_bases(
        self,
        spec: HierarchicalModelSpec | ShallowModelSpec,
    ) -> None:
        if isinstance(spec, ShallowModelSpec):
            self._validate_hidden_rule_base(spec.feature_block.rule_base, spec.feature_block)
        else:
            for stage in spec.stages:
                for block in stage.blocks:
                    self._validate_hidden_rule_base(block.rule_base, block)
        self._validate_decision_rule_base(spec.decision_layer.rule_base, spec.decision_layer)

    def _validate_hidden_rule_base(
        self,
        rule_base: RuleBaseSpec | None,
        block_spec: TransparentBlockSpec,
    ) -> None:
        if rule_base is None:
            return
        active_rules = rule_base.active_rules
        if not active_rules:
            raise ValueError("A manual hidden rule base must contain at least one active rule.")
        if block_spec.max_rules is not None and len(active_rules) > block_spec.max_rules:
            raise ValueError(
                f"Hidden block {block_spec.name!r} allows at most {block_spec.max_rules} active rules."
            )
        variable_lookup = {variable.name: variable for variable in block_spec.variables}
        concept_names = set(
            block_spec.concept_names or tuple(f"concept_{index + 1}" for index in range(block_spec.n_concepts))
        )
        for rule in active_rules:
            self._validate_rule_antecedents(
                rule=rule,
                variable_lookup=variable_lookup,
                max_rule_arity=block_spec.max_rule_arity,
                layer_name=block_spec.name,
            )
            unknown_concepts = [name for name in rule.consequent if name not in concept_names]
            if unknown_concepts:
                raise ValueError(
                    f"Rule {rule.identifier!r} references unknown hidden consequent concepts: {unknown_concepts}."
                )
            for concept_name, value in rule.consequent.items():
                if not np.isfinite(value):
                    raise ValueError(
                        f"Rule {rule.identifier!r} has a non-finite hidden consequent value for {concept_name!r}."
                    )
                if value < 0.0 or value > 1.0:
                    raise ValueError(
                        f"Hidden consequent {concept_name!r} in rule {rule.identifier!r} must stay within [0, 1]."
                    )

    def _validate_decision_rule_base(
        self,
        rule_base: RuleBaseSpec | None,
        decision_spec: DecisionLayerSpec,
    ) -> None:
        if rule_base is None:
            return
        active_rules = rule_base.active_rules
        if not active_rules:
            raise ValueError("A manual decision rule base must contain at least one active rule.")
        if decision_spec.max_rules is not None and len(active_rules) > decision_spec.max_rules:
            raise ValueError(
                f"Decision layer {decision_spec.name!r} allows at most {decision_spec.max_rules} active rules."
            )
        variable_lookup = {variable.name: variable for variable in decision_spec.variables}
        output_names = tuple(
            decision_spec.output_names or tuple(f"output_{index + 1}" for index in range(decision_spec.output_dim))
        )
        output_lookup = set(output_names)
        for rule in active_rules:
            self._validate_rule_antecedents(
                rule=rule,
                variable_lookup=variable_lookup,
                max_rule_arity=decision_spec.max_rule_arity,
                layer_name=decision_spec.name,
            )
            for key, value in rule.consequent.items():
                if not np.isfinite(value):
                    raise ValueError(
                        f"Rule {rule.identifier!r} has a non-finite decision consequent value for {key!r}."
                    )
                if ":" in key:
                    left, right = key.split(":", 1)
                    if left == "bias":
                        if right not in output_lookup:
                            raise ValueError(
                                f"Rule {rule.identifier!r} references unknown decision output {right!r}."
                            )
                    elif left not in variable_lookup or right not in output_lookup:
                        raise ValueError(
                            f"Rule {rule.identifier!r} references unsupported decision consequent key {key!r}."
                        )
                    continue
                if key == "bias":
                    if decision_spec.output_dim != 1:
                        raise ValueError(
                            "Plain 'bias' consequents are only supported for single-output decision layers."
                        )
                    continue
                if key in variable_lookup:
                    if decision_spec.output_dim != 1:
                        raise ValueError(
                            f"Plain variable consequent {key!r} requires a single-output decision layer."
                        )
                    continue
                if key not in output_lookup:
                    raise ValueError(
                        f"Rule {rule.identifier!r} references unsupported decision consequent key {key!r}."
                    )

    def _validate_rule_antecedents(
        self,
        *,
        rule: RuleSpec,
        variable_lookup: dict[str, VariableSpec],
        max_rule_arity: int | None,
        layer_name: str,
    ) -> None:
        if not np.isfinite(rule.weight):
            raise ValueError(f"Rule {rule.identifier!r} has a non-finite weight.")
        if not rule.antecedents:
            raise ValueError(f"Rule {rule.identifier!r} in layer {layer_name!r} has no antecedents.")
        if max_rule_arity is not None and len(rule.antecedents) > max_rule_arity:
            raise ValueError(
                f"Rule {rule.identifier!r} in layer {layer_name!r} exceeds max_rule_arity={max_rule_arity}."
            )
        for antecedent in rule.antecedents:
            variable = variable_lookup.get(antecedent.variable_name)
            if variable is None:
                raise ValueError(
                    f"Rule {rule.identifier!r} references unknown variable {antecedent.variable_name!r} "
                    f"in layer {layer_name!r}."
                )
            if antecedent.term_name not in variable.term_names:
                raise ValueError(
                    f"Rule {rule.identifier!r} references unknown term {antecedent.term_name!r} "
                    f"for variable {variable.name!r}."
                )

    def _decision_layer_spec(self) -> DecisionLayerSpec:
        if self.model_spec is None:
            raise RuntimeError("No model is configured.")
        return self.model_spec.decision_layer

    def _find_block_spec(self, block_name: str, stage_name: str | None = None) -> TransparentBlockSpec:
        if self.model_spec is None:
            raise RuntimeError("No model is configured.")
        if self.model_kind == "flat_neuro_fuzzy":
            if block_name != self.model_spec.feature_block.name:
                raise KeyError(f"Unknown block: {block_name!r}.")
            if stage_name is not None and stage_name != self.model_spec.stage_name:
                raise KeyError(f"Unknown stage: {stage_name!r}.")
            return self.model_spec.feature_block

        matches = []
        for stage in self.model_spec.stages:
            if stage_name is not None and stage.name != stage_name:
                continue
            for block in stage.blocks:
                if block.name == block_name:
                    matches.append(block)
        if not matches:
            raise KeyError(f"Unknown block: {block_name!r}.")
        if len(matches) > 1 and stage_name is None:
            raise KeyError(f"Block name {block_name!r} is ambiguous. Provide stage_name.")
        return matches[0]

    @staticmethod
    def _rule_target_key(block_name: str, stage_name: str | None, layer_kind: str) -> str:
        if layer_kind == "decision":
            return f"decision::{block_name}"
        return f"{stage_name or 'stage'}::{block_name}"
