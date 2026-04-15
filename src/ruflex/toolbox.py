from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ruflex.core.enums import MembershipKind, NormalizationMode, TaskType, VariableRole
from ruflex.core.membership import (
    GaussianMembershipSpec,
    GeneralizedBellMembershipSpec,
    MembershipFunctionSpec,
    TrapezoidalMembershipSpec,
    TriangularMembershipSpec,
)
from ruflex.core.rules import AntecedentSpec, RuleBaseSpec, RuleSpec
from ruflex.core.variables import VariableSpec
from ruflex.data.datasets import TabularDataset
from ruflex.experiments.article_benchmark import (
    ArticleBenchmarkVariant,
    article_benchmark_plan as _article_benchmark_plan,
    list_article_benchmark_runs as _list_article_benchmark_runs,
    load_article_benchmark as _load_article_benchmark,
    prepare_article_materials as _prepare_article_materials,
    run_article_benchmark as _run_article_benchmark,
)
from ruflex.sdk.project import Project
from ruflex.training.config import ModelTrainingConfig
from ruflex.visualization.plots import plot_membership_functions, plot_training_history


@dataclass(frozen=True)
class ToolboxFunctionInfo:
    name: str
    category: str
    signature: str
    description: str


def make_antecedent(variable_name: str, term_name: str) -> AntecedentSpec:
    return AntecedentSpec(variable_name=variable_name, term_name=term_name)


def make_rule(
    identifier: str,
    antecedents: tuple[AntecedentSpec, ...] | list[AntecedentSpec],
    *,
    aggregation: str = "product",
    weight: float = 0.5,
    consequent: dict[str, float] | None = None,
    layer_name: str | None = None,
    active: bool = True,
) -> RuleSpec:
    return RuleSpec(
        identifier=identifier,
        antecedents=tuple(antecedents),
        aggregation=aggregation,
        weight=weight,
        consequent={} if consequent is None else dict(consequent),
        layer_name=layer_name,
        active=active,
    )


def make_rule_base(rules: tuple[RuleSpec, ...] | list[RuleSpec]) -> RuleBaseSpec:
    return RuleBaseSpec(rules=tuple(rules))


def gaussian_mf(
    centers: tuple[float, ...] | list[float],
    spreads: tuple[float, ...] | list[float],
    term_names: tuple[str, ...] | list[str] | None = None,
    min_spread: float = 1e-3,
) -> GaussianMembershipSpec:
    return GaussianMembershipSpec(
        centers=tuple(float(value) for value in centers),
        spreads=tuple(float(value) for value in spreads),
        term_names=None if term_names is None else tuple(term_names),
        min_spread=min_spread,
    )


def gbell_mf(
    centers: tuple[float, ...] | list[float],
    widths: tuple[float, ...] | list[float],
    slopes: tuple[float, ...] | list[float],
    term_names: tuple[str, ...] | list[str] | None = None,
    min_width: float = 1e-3,
    min_slope: float = 1e-2,
) -> GeneralizedBellMembershipSpec:
    return GeneralizedBellMembershipSpec(
        centers=tuple(float(value) for value in centers),
        widths=tuple(float(value) for value in widths),
        slopes=tuple(float(value) for value in slopes),
        term_names=None if term_names is None else tuple(term_names),
        min_width=min_width,
        min_slope=min_slope,
    )


def triangular_mf(
    left: tuple[float, ...] | list[float],
    center: tuple[float, ...] | list[float],
    right: tuple[float, ...] | list[float],
    term_names: tuple[str, ...] | list[str] | None = None,
) -> TriangularMembershipSpec:
    return TriangularMembershipSpec(
        left=tuple(float(value) for value in left),
        center=tuple(float(value) for value in center),
        right=tuple(float(value) for value in right),
        term_names=None if term_names is None else tuple(term_names),
    )


def trapezoidal_mf(
    left: tuple[float, ...] | list[float],
    left_top: tuple[float, ...] | list[float],
    right_top: tuple[float, ...] | list[float],
    right: tuple[float, ...] | list[float],
    term_names: tuple[str, ...] | list[str] | None = None,
) -> TrapezoidalMembershipSpec:
    return TrapezoidalMembershipSpec(
        left=tuple(float(value) for value in left),
        left_top=tuple(float(value) for value in left_top),
        right_top=tuple(float(value) for value in right_top),
        right=tuple(float(value) for value in right),
        term_names=None if term_names is None else tuple(term_names),
    )


def make_variable(
    name: str,
    membership: MembershipFunctionSpec,
    *,
    value_range: tuple[float, float] | list[float] | None = None,
    data_type: str = "continuous",
    role: str = "input",
    normalization: str | NormalizationMode = NormalizationMode.STANDARD,
) -> VariableSpec:
    resolved_normalization = (
        normalization if isinstance(normalization, NormalizationMode) else NormalizationMode(str(normalization))
    )
    resolved_role = role if isinstance(role, VariableRole) else VariableRole(str(role))
    return VariableSpec(
        name=name,
        membership=membership,
        value_range=None if value_range is None else (float(value_range[0]), float(value_range[1])),
        data_type=data_type,
        role=resolved_role,
        normalization=resolved_normalization,
    )


def auto_variable(
    name: str,
    value_range: tuple[float, float] | list[float],
    *,
    term_count: int = 3,
    membership_kind: str | MembershipKind = MembershipKind.GAUSSIAN.value,
    data_type: str = "continuous",
    role: str = "input",
    normalization: str | NormalizationMode = NormalizationMode.STANDARD,
) -> VariableSpec:
    kind = membership_kind if isinstance(membership_kind, MembershipKind) else MembershipKind(str(membership_kind))
    low, high = float(value_range[0]), float(value_range[1])
    if np.isclose(low, high):
        high = low + 1.0
    centers = np.linspace(low, high, term_count)
    span = max(high - low, 1e-6)
    term_names = tuple(f"term_{index + 1}" for index in range(term_count))

    if kind is MembershipKind.GAUSSIAN:
        membership = gaussian_mf(
            centers=tuple(float(value) for value in centers),
            spreads=tuple(float(max(span / max(term_count - 1, 1), 1e-3)) for _ in range(term_count)),
            term_names=term_names,
        )
    elif kind is MembershipKind.GENERALIZED_BELL:
        membership = gbell_mf(
            centers=tuple(float(value) for value in centers),
            widths=tuple(float(max(span / max(term_count, 1), 1e-3)) for _ in range(term_count)),
            slopes=tuple(2.0 for _ in range(term_count)),
            term_names=term_names,
        )
    elif kind is MembershipKind.TRIANGULAR:
        step = span / max(term_count - 1, 1)
        membership = triangular_mf(
            left=tuple(float(value - step) for value in centers),
            center=tuple(float(value) for value in centers),
            right=tuple(float(value + step) for value in centers),
            term_names=term_names,
        )
    else:
        step = span / max(term_count - 1, 1)
        membership = trapezoidal_mf(
            left=tuple(float(value - step) for value in centers),
            left_top=tuple(float(value - step / 2.0) for value in centers),
            right_top=tuple(float(value + step / 2.0) for value in centers),
            right=tuple(float(value + step) for value in centers),
            term_names=term_names,
        )

    return make_variable(
        name=name,
        membership=membership,
        value_range=(low, high),
        data_type=data_type,
        role=role,
        normalization=normalization,
    )


def new_project(
    name: str,
    task_type: str | TaskType = TaskType.REGRESSION.value,
    description: str | None = None,
) -> Project:
    return Project(
        name=name,
        task_type=task_type.value if isinstance(task_type, TaskType) else str(task_type),
        description=description,
    )


def attach_dataframe(
    project: Project,
    frame: pd.DataFrame,
    *,
    target_column: str,
    feature_columns: tuple[str, ...] | None = None,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    normalization: NormalizationMode = NormalizationMode.STANDARD,
    fill_missing: str = "median",
    random_state: int = 42,
) -> Project:
    return project.from_dataframe(
        frame,
        target_column=target_column,
        feature_columns=feature_columns,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        normalization=normalization,
        fill_missing=fill_missing,
        random_state=random_state,
    )


def attach_csv(
    project: Project,
    path: str | Path,
    *,
    target_column: str,
    feature_columns: tuple[str, ...] | None = None,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    normalization: NormalizationMode = NormalizationMode.STANDARD,
    fill_missing: str = "median",
    random_state: int = 42,
) -> Project:
    return project.from_csv(
        path,
        target_column=target_column,
        feature_columns=feature_columns,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        normalization=normalization,
        fill_missing=fill_missing,
        random_state=random_state,
    )


def attach_dataset(
    project: Project,
    dataset: TabularDataset,
    *,
    target_column: str,
    feature_columns: tuple[str, ...] | None = None,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    normalization: NormalizationMode = NormalizationMode.STANDARD,
    fill_missing: str = "median",
    random_state: int = 42,
) -> Project:
    return project.use_dataset(
        dataset,
        target_column=target_column,
        feature_columns=feature_columns,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        normalization=normalization,
        fill_missing=fill_missing,
        random_state=random_state,
    )


def article_benchmark_plan(project: Project) -> tuple[dict[str, Any], ...]:
    return _article_benchmark_plan(project)


def run_article_benchmark(
    project: Project,
    *,
    output_root: str | Path = "experiments/article_benchmark",
    variant_names: tuple[str, ...] | list[str] | None = None,
    training_preset_override: str | None = None,
    seeds: tuple[int, ...] | list[int] | None = None,
) -> dict[str, Any]:
    return _run_article_benchmark(
        project,
        output_root=output_root,
        variant_names=variant_names,
        training_preset_override=training_preset_override,
        seeds=seeds,
    )


def list_article_benchmark_runs(root_dir: str | Path = "experiments/article_benchmark") -> tuple[dict[str, Any], ...]:
    return _list_article_benchmark_runs(root_dir=root_dir)


def load_article_benchmark(benchmark_dir: str | Path) -> dict[str, Any]:
    return _load_article_benchmark(benchmark_dir)


def prepare_article_materials(
    benchmark_dir: str | Path,
    *,
    output_root: str | Path = "docs/article/assets",
) -> dict[str, Any]:
    return _prepare_article_materials(benchmark_dir, output_root=output_root)


def infer_variables(
    project: Project,
    term_count: int = 3,
    membership_kind: str | MembershipKind = MembershipKind.GAUSSIAN.value,
    normalization: NormalizationMode | None = None,
) -> Project:
    kind = membership_kind.value if isinstance(membership_kind, MembershipKind) else str(membership_kind)
    return project.infer_variables(term_count=term_count, membership_kind=kind, normalization=normalization)


def set_variables(project: Project, variables: tuple[VariableSpec, ...] | list[VariableSpec]) -> Project:
    return project.set_variables(variables)


def get_variable(project: Project, variable_name: str) -> VariableSpec:
    return project.get_variable(variable_name)


def set_variable(project: Project, variable_name: str, variable: VariableSpec) -> Project:
    return project.set_variable(variable_name, variable)


def variable_catalog(project: Project) -> dict[str, Any]:
    return project.variable_catalog()


def set_variable_catalog(
    project: Project,
    catalog: dict[str, Any] | list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> Project:
    return project.set_variable_catalog(catalog)


def save_variable_catalog(project: Project, path: str | Path) -> None:
    project.save_variable_catalog_json(path)


def load_variable_catalog(project: Project, path: str | Path) -> Project:
    return project.load_variable_catalog_json(path)


def model_preset(project: Project) -> dict[str, Any]:
    return project.model_preset()


def apply_model_preset(project: Project, payload: dict[str, Any]) -> Project:
    return project.apply_model_preset(payload)


def save_model_preset(project: Project, path: str | Path) -> None:
    project.save_model_preset_json(path)


def load_model_preset(project: Project, path: str | Path) -> Project:
    return project.load_model_preset_json(path)


def experiment_history(project: Project) -> tuple[dict[str, Any], ...]:
    return project.experiment_history()


def clear_experiment_history(project: Project) -> Project:
    return project.clear_experiment_history()


def list_workspace_templates(project: Project) -> tuple[dict[str, Any], ...]:
    return project.list_workspace_templates()


def apply_workspace_template(project: Project, template_name: str) -> Project:
    return project.apply_workspace_template(template_name)


def list_training_presets(project: Project) -> tuple[dict[str, Any], ...]:
    return project.list_training_presets()


def training_preset(project: Project, preset_name: str) -> ModelTrainingConfig:
    return project.training_preset(preset_name)


def list_study_pipelines(project: Project) -> tuple[dict[str, Any], ...]:
    return project.list_study_pipelines()


def study_pipeline(project: Project, pipeline_name: str) -> dict[str, Any]:
    return project.study_pipeline(pipeline_name)


def run_study_pipeline(
    project: Project,
    pipeline_name: str,
    *,
    export_root: str | Path | None = None,
    training_preset_override: str | None = None,
) -> dict[str, Any]:
    return project.run_study_pipeline(
        pipeline_name,
        export_root=export_root,
        training_preset_override=training_preset_override,
    )


def study_run_history(project: Project) -> tuple[dict[str, Any], ...]:
    return project.study_run_history()


def clear_study_run_history(project: Project) -> Project:
    return project.clear_study_run_history()


def export_study_run_artifacts(
    project: Project,
    root_dir: str | Path = "experiments",
    *,
    study_run_index: int = -1,
) -> dict[str, Any]:
    return project.export_study_run_artifacts(root_dir=root_dir, study_run_index=study_run_index)


def list_exported_studies(project: Project, root_dir: str | Path = "experiments") -> tuple[dict[str, Any], ...]:
    return project.list_exported_studies(root_dir=root_dir)


def load_exported_study(project: Project, export_dir: str | Path) -> dict[str, Any]:
    return project.load_exported_study(export_dir)


def compare_exported_studies(project: Project, root_dir: str | Path = "experiments") -> tuple[dict[str, Any], ...]:
    return project.compare_exported_studies(root_dir=root_dir)


def rank_exported_studies(
    project: Project,
    root_dir: str | Path = "experiments",
    *,
    metric_name: str,
    higher_is_better: bool | None = None,
    split_priority: tuple[str, ...] = ("test", "validation", "train"),
) -> tuple[dict[str, Any], ...]:
    return project.rank_exported_studies(
        root_dir=root_dir,
        metric_name=metric_name,
        higher_is_better=higher_is_better,
        split_priority=split_priority,
    )


def best_exported_study(
    project: Project,
    root_dir: str | Path = "experiments",
    *,
    metric_name: str,
    higher_is_better: bool | None = None,
    split_priority: tuple[str, ...] = ("test", "validation", "train"),
) -> dict[str, Any]:
    return project.best_exported_study(
        root_dir=root_dir,
        metric_name=metric_name,
        higher_is_better=higher_is_better,
        split_priority=split_priority,
    )


def apply_model_preset_from_exported_study(project: Project, export_dir: str | Path) -> Project:
    return project.apply_model_preset_from_exported_study(export_dir)


def configure_model(project: Project, mode: str, **kwargs) -> Project:
    return project.configure_model(mode, **kwargs)


def configure_flat_model(project: Project, **kwargs) -> Project:
    return project.configure_flat_model(**kwargs)


def configure_deep_model(project: Project, **kwargs) -> Project:
    return project.configure_deep_model(**kwargs)


def default_training_config(
    project: Project,
    *,
    stagewise: bool | None = None,
    refinement_cycles: int = 1,
    max_epochs: int = 120,
    batch_size: int | None = 64,
    learning_rate: float = 1e-3,
) -> ModelTrainingConfig:
    return project.default_training_config(
        stagewise=stagewise,
        refinement_cycles=refinement_cycles,
        max_epochs=max_epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
    )


def train(project: Project, training_config: ModelTrainingConfig | None = None):
    return project.train(training_config=training_config)


def fit(project: Project, training_config: ModelTrainingConfig | None = None):
    return train(project, training_config=training_config)


def evaluate(project: Project, features: pd.DataFrame | np.ndarray, targets: pd.DataFrame | np.ndarray) -> dict[str, float]:
    return project.evaluate(features, targets)


def predict(project: Project, features: pd.DataFrame | np.ndarray) -> np.ndarray:
    return project.predict(features)


def explain(
    project: Project,
    features: pd.DataFrame | np.ndarray,
    top_k_rules: int = 2,
    as_text: bool = False,
):
    return project.explain(features, top_k_rules=top_k_rules, as_text=as_text)


def dashboard(project: Project, features: pd.DataFrame | np.ndarray, top_k_rules: int = 2):
    return project.dashboard(features, top_k_rules=top_k_rules)


def concept_flow(
    project: Project,
    features: pd.DataFrame | np.ndarray,
    top_k_rules: int = 2,
    as_text: bool = False,
):
    return project.concept_flow(features, top_k_rules=top_k_rules, as_text=as_text)


def path_concept_flow(
    project: Project,
    features: pd.DataFrame | np.ndarray,
    top_k_rules: int = 2,
    as_text: bool = False,
):
    return project.path_concept_flow(features, top_k_rules=top_k_rules, as_text=as_text)


def rule_chain_flow(
    project: Project,
    features: pd.DataFrame | np.ndarray,
    top_k_rules: int = 2,
    as_text: bool = False,
):
    return project.rule_chain_flow(features, top_k_rules=top_k_rules, as_text=as_text)


def model_report(project: Project, decimals: int = 3) -> str:
    return project.model_report(decimals=decimals)


def project_report(project: Project, decimals: int = 3) -> str:
    return project.project_report(decimals=decimals)


def explainability_report(project: Project, decimals: int = 3):
    return project.explainability_report(decimals=decimals)


def rule_records(project: Project, decimals: int = 3):
    return project.rule_records(decimals=decimals)


def summary(project: Project) -> dict[str, Any]:
    return project.summary()


def dataset_summary(project: Project) -> dict[str, Any]:
    return project.dataset_summary()


def list_rule_targets(project: Project) -> tuple[dict[str, Any], ...]:
    return project.list_rule_targets()


def get_block_rule_base(project: Project, block_name: str, stage_name: str | None = None) -> RuleBaseSpec | None:
    return project.get_block_rule_base(block_name, stage_name=stage_name)


def set_block_rule_base(
    project: Project,
    block_name: str,
    rule_base: RuleBaseSpec | None,
    *,
    stage_name: str | None = None,
) -> Project:
    return project.set_block_rule_base(block_name, rule_base, stage_name=stage_name)


def get_decision_rule_base(project: Project) -> RuleBaseSpec | None:
    return project.get_decision_rule_base()


def set_decision_rule_base(project: Project, rule_base: RuleBaseSpec | None) -> Project:
    return project.set_decision_rule_base(rule_base)


def clear_all_rule_bases(project: Project) -> Project:
    return project.clear_all_rule_bases()


def rule_base_catalog(project: Project) -> dict[str, Any]:
    return project.rule_base_catalog()


def set_rule_base_catalog(project: Project, catalog: dict[str, Any], *, clear_missing: bool = False) -> Project:
    return project.set_rule_base_catalog(catalog, clear_missing=clear_missing)


def save_rule_base_catalog(project: Project, path: str | Path) -> None:
    project.save_rule_base_catalog_json(path)


def load_rule_base_catalog(project: Project, path: str | Path, *, clear_missing: bool = False) -> Project:
    return project.load_rule_base_catalog_json(path, clear_missing=clear_missing)


def make_rule_template(
    project: Project,
    *,
    block_name: str,
    stage_name: str | None = None,
    layer_kind: str = "hidden",
) -> RuleBaseSpec:
    return project.make_rule_template(block_name=block_name, stage_name=stage_name, layer_kind=layer_kind)


def plot_variable_memberships(project: Project, variable_name: str, points: int = 200):
    return plot_membership_functions(get_variable(project, variable_name), points=points)


def plot_project_training_history(project: Project):
    if project.training_summary is None:
        raise RuntimeError("Train the project before plotting training history.")
    return plot_training_history(project.training_summary)


def save_project(project: Project, path: str | Path, include_dataset: bool = False) -> None:
    project.save(path, include_dataset=include_dataset)


def load_project(path: str | Path) -> Project:
    return Project.load(path)


def save_project_manifest(project: Project, path: str | Path) -> None:
    project.save_manifest_json(path)


def load_project_manifest(path: str | Path, frame: pd.DataFrame | None = None) -> Project:
    return Project.load_manifest_json(path, frame=frame)


def load_project_from_exported_study(export_dir: str | Path, frame: pd.DataFrame | None = None) -> Project:
    return Project.load_project_from_exported_study(export_dir, frame=frame)


def list_functions() -> tuple[ToolboxFunctionInfo, ...]:
    function_names = (
        "make_antecedent",
        "make_rule",
        "make_rule_base",
        "gaussian_mf",
        "gbell_mf",
        "triangular_mf",
        "trapezoidal_mf",
        "make_variable",
        "auto_variable",
        "new_project",
        "attach_dataframe",
        "attach_csv",
        "attach_dataset",
        "article_benchmark_plan",
        "run_article_benchmark",
        "list_article_benchmark_runs",
        "load_article_benchmark",
        "prepare_article_materials",
        "infer_variables",
        "set_variables",
        "get_variable",
        "set_variable",
        "variable_catalog",
        "set_variable_catalog",
        "save_variable_catalog",
        "load_variable_catalog",
        "model_preset",
        "apply_model_preset",
        "save_model_preset",
        "load_model_preset",
        "experiment_history",
        "clear_experiment_history",
        "list_workspace_templates",
        "apply_workspace_template",
        "list_training_presets",
        "training_preset",
        "list_study_pipelines",
        "study_pipeline",
        "run_study_pipeline",
        "study_run_history",
        "clear_study_run_history",
        "export_study_run_artifacts",
        "list_exported_studies",
        "load_exported_study",
        "compare_exported_studies",
        "rank_exported_studies",
        "best_exported_study",
        "apply_model_preset_from_exported_study",
        "configure_model",
        "configure_flat_model",
        "configure_deep_model",
        "default_training_config",
        "train",
        "fit",
        "evaluate",
        "predict",
        "explain",
        "dashboard",
        "concept_flow",
        "path_concept_flow",
        "rule_chain_flow",
        "model_report",
        "project_report",
        "explainability_report",
        "rule_records",
        "summary",
        "dataset_summary",
        "list_rule_targets",
        "get_block_rule_base",
        "set_block_rule_base",
        "get_decision_rule_base",
        "set_decision_rule_base",
        "clear_all_rule_bases",
        "rule_base_catalog",
        "set_rule_base_catalog",
        "save_rule_base_catalog",
        "load_rule_base_catalog",
        "make_rule_template",
        "plot_variable_memberships",
        "plot_project_training_history",
        "save_project",
        "load_project",
        "save_project_manifest",
        "load_project_manifest",
        "load_project_from_exported_study",
    )
    categories = {
        "make_antecedent": "rules",
        "make_rule": "rules",
        "make_rule_base": "rules",
        "gaussian_mf": "constructors",
        "gbell_mf": "constructors",
        "triangular_mf": "constructors",
        "trapezoidal_mf": "constructors",
        "make_variable": "constructors",
        "auto_variable": "constructors",
        "new_project": "project",
        "attach_dataframe": "data",
        "attach_csv": "data",
        "attach_dataset": "data",
        "article_benchmark_plan": "project",
        "run_article_benchmark": "project",
        "list_article_benchmark_runs": "io",
        "load_article_benchmark": "io",
        "prepare_article_materials": "io",
        "infer_variables": "variables",
        "set_variables": "variables",
        "get_variable": "variables",
        "set_variable": "variables",
        "variable_catalog": "variables",
        "set_variable_catalog": "variables",
        "save_variable_catalog": "io",
        "load_variable_catalog": "io",
        "model_preset": "project",
        "apply_model_preset": "project",
        "save_model_preset": "io",
        "load_model_preset": "io",
        "experiment_history": "reports",
        "clear_experiment_history": "project",
        "list_workspace_templates": "project",
        "apply_workspace_template": "project",
        "list_training_presets": "training",
        "training_preset": "training",
        "list_study_pipelines": "project",
        "study_pipeline": "project",
        "run_study_pipeline": "project",
        "study_run_history": "reports",
        "clear_study_run_history": "project",
        "export_study_run_artifacts": "io",
        "list_exported_studies": "io",
        "load_exported_study": "io",
        "compare_exported_studies": "reports",
        "rank_exported_studies": "reports",
        "best_exported_study": "reports",
        "apply_model_preset_from_exported_study": "project",
        "configure_model": "models",
        "configure_flat_model": "models",
        "configure_deep_model": "models",
        "default_training_config": "training",
        "train": "training",
        "fit": "training",
        "evaluate": "evaluation",
        "predict": "evaluation",
        "explain": "explainability",
        "dashboard": "explainability",
        "concept_flow": "explainability",
        "path_concept_flow": "explainability",
        "rule_chain_flow": "explainability",
        "model_report": "reports",
        "project_report": "reports",
        "explainability_report": "reports",
        "rule_records": "reports",
        "summary": "reports",
        "dataset_summary": "reports",
        "list_rule_targets": "rules",
        "get_block_rule_base": "rules",
        "set_block_rule_base": "rules",
        "get_decision_rule_base": "rules",
        "set_decision_rule_base": "rules",
        "clear_all_rule_bases": "rules",
        "rule_base_catalog": "rules",
        "set_rule_base_catalog": "rules",
        "save_rule_base_catalog": "io",
        "load_rule_base_catalog": "io",
        "make_rule_template": "rules",
        "plot_variable_memberships": "visualization",
        "plot_project_training_history": "visualization",
        "save_project": "io",
        "load_project": "io",
        "save_project_manifest": "io",
        "load_project_manifest": "io",
        "load_project_from_exported_study": "io",
    }
    descriptions = {
        "make_antecedent": "Create a single antecedent condition.",
        "make_rule": "Create a manual rule specification.",
        "make_rule_base": "Create a manual rule base specification.",
        "gaussian_mf": "Create a Gaussian membership function specification.",
        "gbell_mf": "Create a generalized bell membership function specification.",
        "triangular_mf": "Create a triangular membership function specification.",
        "trapezoidal_mf": "Create a trapezoidal membership function specification.",
        "make_variable": "Create a VariableSpec from a prepared membership function.",
        "auto_variable": "Create a VariableSpec from a value range and membership family.",
        "new_project": "Create a new RuFLEX project.",
        "attach_dataframe": "Attach a pandas DataFrame as the project dataset.",
        "attach_csv": "Attach a CSV file as the project dataset.",
        "attach_dataset": "Attach an existing TabularDataset instance.",
        "article_benchmark_plan": "Return the default article-oriented benchmark suite for the current dataset.",
        "run_article_benchmark": "Run the article benchmark suite, export variant artifacts, and save summary tables.",
        "list_article_benchmark_runs": "List saved article benchmark runs under a benchmark root.",
        "load_article_benchmark": "Load a saved article benchmark summary from disk.",
        "prepare_article_materials": "Convert one saved benchmark run into article-ready tables and summary files.",
        "infer_variables": "Infer fuzzy variables from the attached dataset.",
        "set_variables": "Assign a prepared list of VariableSpec objects.",
        "get_variable": "Fetch a variable from the project by name.",
        "set_variable": "Replace a named project variable and propagate it into the current model spec.",
        "variable_catalog": "Return all current project variables as a dictionary.",
        "set_variable_catalog": "Replace the full project variable catalog from serialized VariableSpec payloads.",
        "save_variable_catalog": "Save the variable catalog as JSON.",
        "load_variable_catalog": "Load the variable catalog from JSON and apply it to the project.",
        "model_preset": "Return a portable model preset containing variables, model kind, and model spec.",
        "apply_model_preset": "Apply a portable model preset to the current project.",
        "save_model_preset": "Save the model preset as JSON.",
        "load_model_preset": "Load the model preset from JSON and apply it to the project.",
        "experiment_history": "Return the stored training and evaluation history for the project.",
        "clear_experiment_history": "Clear the stored experiment history records.",
        "list_workspace_templates": "List ready-to-apply workspace templates for variable inference and model configuration.",
        "apply_workspace_template": "Infer variables and configure the model from a named workspace template.",
        "list_training_presets": "List ready-to-use training presets for the current project.",
        "training_preset": "Build a ModelTrainingConfig from a named training preset.",
        "list_study_pipelines": "List full reproducible study pipelines that combine workspace and training presets.",
        "study_pipeline": "Return a single study pipeline definition by name.",
        "run_study_pipeline": "Apply a study pipeline, optionally override the training preset, export artifacts, and store a structured study-run record.",
        "study_run_history": "Return the stored study-run history records.",
        "clear_study_run_history": "Clear the stored study-run history records.",
        "export_study_run_artifacts": "Export one stored study run into an experiment folder with manifests, metrics, presets, and reports.",
        "list_exported_studies": "List study-run artifact folders found under an experiment root.",
        "load_exported_study": "Load the full payload of one exported study directory.",
        "compare_exported_studies": "Return flattened comparison rows across exported study artifacts.",
        "rank_exported_studies": "Rank exported study artifacts by a selected metric and split priority.",
        "best_exported_study": "Return the best exported study for a selected metric and split priority.",
        "apply_model_preset_from_exported_study": "Apply the stored model preset from an exported study to the current project.",
        "configure_model": "Configure a model by mode name.",
        "configure_flat_model": "Configure the flat neuro-fuzzy baseline model.",
        "configure_deep_model": "Configure the deep fuzzy feature learning model.",
        "default_training_config": "Create a default training config for the project.",
        "train": "Train the configured project.",
        "fit": "Alias for train(project, ...).",
        "evaluate": "Evaluate the trained project on explicit features and targets.",
        "predict": "Run inference with the trained project.",
        "explain": "Return sample-level explanations.",
        "dashboard": "Return structured dashboard payloads for sample inspection.",
        "concept_flow": "Return hidden concept contribution flows.",
        "path_concept_flow": "Return path-based hidden concept attribution flows.",
        "rule_chain_flow": "Return exact/path-based hidden rule chain flows.",
        "model_report": "Return a text model report.",
        "project_report": "Return a text project report.",
        "explainability_report": "Return a structured explainability report payload.",
        "rule_records": "Return structured exported rules.",
        "summary": "Return a compact project summary dictionary.",
        "dataset_summary": "Return a compact dataset summary dictionary.",
        "list_rule_targets": "List block and decision-layer targets that can accept manual rule bases.",
        "get_block_rule_base": "Fetch the current manual rule base for a hidden block.",
        "set_block_rule_base": "Assign a manual rule base to a hidden block.",
        "get_decision_rule_base": "Fetch the current manual rule base for the decision layer.",
        "set_decision_rule_base": "Assign a manual rule base to the decision layer.",
        "clear_all_rule_bases": "Remove all manually assigned rule bases from the project spec.",
        "rule_base_catalog": "Return all current manual rule bases as a dictionary.",
        "set_rule_base_catalog": "Apply a serialized rule-base catalog across hidden blocks and the decision layer.",
        "save_rule_base_catalog": "Save the rule-base catalog as JSON.",
        "load_rule_base_catalog": "Load the rule-base catalog from JSON and apply it to the project.",
        "make_rule_template": "Create a starter manual rule base for a selected block or decision layer.",
        "plot_variable_memberships": "Plot membership functions for a named variable.",
        "plot_project_training_history": "Plot the project training history.",
        "save_project": "Save a project bundle to disk.",
        "load_project": "Load a project bundle from disk.",
        "save_project_manifest": "Save the project manifest as JSON.",
        "load_project_manifest": "Load a project manifest JSON.",
        "load_project_from_exported_study": "Load a project workspace directly from an exported study directory.",
    }
    current_module = globals()
    return tuple(
        ToolboxFunctionInfo(
            name=name,
            category=categories[name],
            signature=f"{name}{signature(current_module[name])}",
            description=descriptions[name],
        )
        for name in function_names
    )


def format_function_catalog() -> str:
    lines = ["RUFLEX TOOLBOX FUNCTIONS"]
    for item in list_functions():
        lines.append(f"[{item.category}] {item.signature}")
        lines.append(f"  {item.description}")
    return "\n".join(lines)
