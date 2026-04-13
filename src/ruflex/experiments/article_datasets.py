from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.datasets import fetch_california_housing, fetch_covtype

from ruflex.io.project import save_manifest


@dataclass(frozen=True)
class ArticleDatasetRecipe:
    name: str
    label: str
    task_type: str
    description: str
    source_dataset: str
    target_column: str
    feature_columns: tuple[str, ...]
    sample_size: int
    random_state: int = 42
    default_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "task_type": self.task_type,
            "description": self.description,
            "source_dataset": self.source_dataset,
            "target_column": self.target_column,
            "feature_columns": list(self.feature_columns),
            "sample_size": self.sample_size,
            "random_state": self.random_state,
            "default_enabled": self.default_enabled,
        }


def list_article_dataset_recipes() -> tuple[dict[str, Any], ...]:
    return tuple(recipe.to_dict() for recipe in _recipe_catalog())


def prepare_article_dataset(
    recipe_name: str,
    *,
    output_root: str | Path = "experiments/datasets",
    sample_size_override: int | None = None,
    random_state_override: int | None = None,
    output_name_suffix: str | None = None,
) -> dict[str, Any]:
    base_recipe = _recipe_by_name(recipe_name)
    recipe = _resolved_recipe(
        base_recipe,
        sample_size_override=sample_size_override,
        random_state_override=random_state_override,
        output_name_suffix=output_name_suffix,
    )
    output_dir = Path(output_root).expanduser().resolve() / recipe.name
    output_dir.mkdir(parents=True, exist_ok=True)

    if base_recipe.name == "california_housing_regression":
        frame, extra_manifest = _prepare_california_housing(recipe)
    elif base_recipe.name == "california_value_binary_geo":
        frame, extra_manifest = _prepare_california_value_binary_geo(recipe)
    elif base_recipe.name == "covtype_binary_geo":
        frame, extra_manifest = _prepare_covtype_binary_geo(recipe)
    else:
        raise ValueError(f"Unsupported article dataset recipe: {base_recipe.name!r}.")

    csv_path = output_dir / "dataset.csv"
    frame.to_csv(csv_path, index=False)

    manifest = {
        **recipe.to_dict(),
        "base_recipe_name": base_recipe.name,
        "base_recipe_label": base_recipe.label,
        **extra_manifest,
        "output_dir": str(output_dir),
        "csv_path": str(csv_path),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": list(frame.columns),
    }
    manifest_path = output_dir / "dataset_manifest.json"
    save_manifest(manifest, manifest_path)

    description_path = output_dir / "README.md"
    description_path.write_text(_dataset_readme(manifest), encoding="utf-8")

    return manifest


def prepare_article_datasets(
    recipe_names: tuple[str, ...] | list[str] | None = None,
    *,
    output_root: str | Path = "experiments/datasets",
    sample_size_override: int | None = None,
    random_state_override: int | None = None,
    output_name_suffix: str | None = None,
) -> tuple[dict[str, Any], ...]:
    selected = _select_recipes(recipe_names)
    return tuple(
        prepare_article_dataset(
            recipe.name,
            output_root=output_root,
            sample_size_override=sample_size_override,
            random_state_override=random_state_override,
            output_name_suffix=output_name_suffix,
        )
        for recipe in selected
    )


def _recipe_catalog() -> tuple[ArticleDatasetRecipe, ...]:
    return (
        ArticleDatasetRecipe(
            name="california_housing_regression",
            label="California Housing Regression",
            task_type="regression",
            description=(
                "Geo-oriented tabular regression benchmark based on California Housing "
                "with latitude and longitude preserved as explicit spatial predictors."
            ),
            source_dataset="sklearn.fetch_california_housing",
            target_column="MedHouseVal",
            feature_columns=(
                "MedInc",
                "HouseAge",
                "AveRooms",
                "AveBedrms",
                "Population",
                "AveOccup",
                "Latitude",
                "Longitude",
            ),
            sample_size=4096,
        ),
        ArticleDatasetRecipe(
            name="california_value_binary_geo",
            label="California Value Binary Geo",
            task_type="binary_classification",
            description=(
                "Balanced spatially informed binary classification benchmark derived from California Housing "
                "by thresholding median house value and preserving latitude/longitude as explicit geo-features."
            ),
            source_dataset="sklearn.fetch_california_housing",
            target_column="HighValue",
            feature_columns=(
                "MedInc",
                "HouseAge",
                "AveRooms",
                "AveBedrms",
                "Population",
                "AveOccup",
                "Latitude",
                "Longitude",
            ),
            sample_size=4096,
        ),
        ArticleDatasetRecipe(
            name="covtype_binary_geo",
            label="Covertype Binary Geo",
            task_type="binary_classification",
            description=(
                "Binary cartographic classification benchmark derived from the Forest CoverType dataset "
                "using the original continuous geo-features and a balanced class-1 vs class-2 subset."
            ),
            source_dataset="sklearn.fetch_covtype",
            target_column="CoverTypeBinary",
            feature_columns=(
                "Elevation",
                "Aspect",
                "Slope",
                "Horizontal_Distance_To_Hydrology",
                "Vertical_Distance_To_Hydrology",
                "Horizontal_Distance_To_Roadways",
                "Hillshade_9am",
                "Hillshade_Noon",
                "Hillshade_3pm",
                "Horizontal_Distance_To_Fire_Points",
            ),
            sample_size=6000,
            default_enabled=True,
        ),
    )


def _recipe_by_name(recipe_name: str) -> ArticleDatasetRecipe:
    for recipe in _recipe_catalog():
        if recipe.name == recipe_name:
            return recipe
    raise ValueError(f"Unknown article dataset recipe: {recipe_name!r}.")


def _resolved_recipe(
    recipe: ArticleDatasetRecipe,
    *,
    sample_size_override: int | None,
    random_state_override: int | None,
    output_name_suffix: str | None,
) -> ArticleDatasetRecipe:
    sample_size = recipe.sample_size if sample_size_override is None else int(sample_size_override)
    random_state = recipe.random_state if random_state_override is None else int(random_state_override)
    if sample_size <= 0:
        raise ValueError("sample_size_override must be positive when provided.")

    suffix_parts: list[str] = []
    label_parts: list[str] = []
    if sample_size != recipe.sample_size:
        suffix_parts.append(f"n{sample_size}")
        label_parts.append(f"n={sample_size}")
    if random_state != recipe.random_state:
        suffix_parts.append(f"rs{random_state}")
        label_parts.append(f"rs={random_state}")
    if output_name_suffix:
        suffix_parts.append(_slug(output_name_suffix))
        label_parts.append(str(output_name_suffix).strip())

    if suffix_parts:
        name = f"{recipe.name}_{'_'.join(suffix_parts)}"
        label = f"{recipe.label} ({', '.join(label_parts)})"
    else:
        name = recipe.name
        label = recipe.label

    return replace(recipe, name=name, label=label, sample_size=sample_size, random_state=random_state)


def _select_recipes(recipe_names: tuple[str, ...] | list[str] | None) -> tuple[ArticleDatasetRecipe, ...]:
    if recipe_names is None:
        return tuple(recipe for recipe in _recipe_catalog() if recipe.default_enabled)
    selected_names = tuple(str(name) for name in recipe_names)
    selected = tuple(recipe for recipe in _recipe_catalog() if recipe.name in selected_names)
    missing = [name for name in selected_names if name not in {recipe.name for recipe in selected}]
    if missing:
        raise ValueError(f"Unknown article dataset recipe(s): {missing}.")
    return selected


def _prepare_california_housing(recipe: ArticleDatasetRecipe) -> tuple[pd.DataFrame, dict[str, Any]]:
    bundle = fetch_california_housing(as_frame=True)
    frame = bundle.frame.loc[:, list(recipe.feature_columns) + [recipe.target_column]].copy()
    actual_sample_size = min(len(frame), recipe.sample_size)
    if len(frame) > recipe.sample_size:
        frame = frame.sample(n=recipe.sample_size, random_state=recipe.random_state).reset_index(drop=True)
    return frame, {
        "sampling": {
            "kind": "random_subsample",
            "sample_size": actual_sample_size,
            "requested_sample_size": recipe.sample_size,
            "original_row_count": int(len(bundle.frame)),
            "random_state": recipe.random_state,
        },
        "task_notes": {
            "problem_type": "regression",
            "geo_features": ["Latitude", "Longitude"],
        },
    }


def _prepare_covtype_binary_geo(recipe: ArticleDatasetRecipe) -> tuple[pd.DataFrame, dict[str, Any]]:
    bundle = fetch_covtype(as_frame=True)
    frame = bundle.frame.loc[:, list(recipe.feature_columns) + ["Cover_Type"]].copy()
    frame = frame[frame["Cover_Type"].isin((1, 2))].reset_index(drop=True)
    max_balanced_sample_size = 2 * min(
        int((frame["Cover_Type"] == 1).sum()),
        int((frame["Cover_Type"] == 2).sum()),
    )
    if recipe.sample_size > max_balanced_sample_size:
        raise ValueError(
            "Requested sample_size exceeds the maximum balanced sample for covtype_binary_geo: "
            f"requested={recipe.sample_size}, max_balanced={max_balanced_sample_size}."
        )

    half = recipe.sample_size // 2
    class_1 = frame[frame["Cover_Type"] == 1].sample(n=half, random_state=recipe.random_state)
    class_2 = frame[frame["Cover_Type"] == 2].sample(n=recipe.sample_size - half, random_state=recipe.random_state)
    balanced = (
        pd.concat([class_1, class_2], axis=0)
        .sample(frac=1.0, random_state=recipe.random_state)
        .reset_index(drop=True)
    )
    balanced[recipe.target_column] = (balanced["Cover_Type"] == 2).astype(int)
    balanced = balanced.drop(columns=["Cover_Type"])

    return balanced, {
        "sampling": {
            "kind": "balanced_binary_subsample",
            "sample_size": recipe.sample_size,
            "max_balanced_sample_size": max_balanced_sample_size,
            "original_row_count": int(len(bundle.frame)),
            "eligible_binary_row_count": int(len(frame)),
            "random_state": recipe.random_state,
        },
        "task_notes": {
            "problem_type": "binary_classification",
            "positive_class_label": 1,
            "positive_class_meaning": "original Cover_Type == 2",
            "negative_class_meaning": "original Cover_Type == 1",
        },
    }


def _prepare_california_value_binary_geo(recipe: ArticleDatasetRecipe) -> tuple[pd.DataFrame, dict[str, Any]]:
    bundle = fetch_california_housing(as_frame=True)
    frame = bundle.frame.loc[:, list(recipe.feature_columns) + ["MedHouseVal"]].copy()
    threshold = float(frame["MedHouseVal"].median())
    frame[recipe.target_column] = (frame["MedHouseVal"] >= threshold).astype(int)
    frame = frame.drop(columns=["MedHouseVal"])

    class_0 = frame[frame[recipe.target_column] == 0]
    class_1 = frame[frame[recipe.target_column] == 1]
    max_balanced_sample_size = 2 * min(len(class_0), len(class_1))
    if recipe.sample_size > max_balanced_sample_size:
        raise ValueError(
            "Requested sample_size exceeds the maximum balanced sample for california_value_binary_geo: "
            f"requested={recipe.sample_size}, max_balanced={max_balanced_sample_size}."
        )
    half = recipe.sample_size // 2
    balanced = (
        pd.concat(
            [
                class_0.sample(n=half, random_state=recipe.random_state),
                class_1.sample(n=recipe.sample_size - half, random_state=recipe.random_state),
            ],
            axis=0,
        )
        .sample(frac=1.0, random_state=recipe.random_state)
        .reset_index(drop=True)
    )

    return balanced, {
        "sampling": {
            "kind": "balanced_threshold_subsample",
            "sample_size": recipe.sample_size,
            "max_balanced_sample_size": max_balanced_sample_size,
            "original_row_count": int(len(bundle.frame)),
            "threshold": threshold,
            "random_state": recipe.random_state,
        },
        "task_notes": {
            "problem_type": "binary_classification",
            "positive_class_label": 1,
            "positive_class_meaning": f"original MedHouseVal >= {threshold:.6f}",
            "negative_class_meaning": f"original MedHouseVal < {threshold:.6f}",
            "geo_features": ["Latitude", "Longitude"],
        },
    }


def _dataset_readme(manifest: dict[str, Any]) -> str:
    lines = [
        f"# {manifest['label']}",
        "",
        f"- recipe_name: {manifest['name']}",
        f"- task_type: {manifest['task_type']}",
        f"- source_dataset: {manifest['source_dataset']}",
        f"- target_column: {manifest['target_column']}",
        f"- row_count: {manifest['row_count']}",
        f"- column_count: {manifest['column_count']}",
        f"- csv_path: {manifest['csv_path']}",
        "",
        "## Description",
        "",
        manifest["description"],
        "",
        "## Feature Columns",
        "",
    ]
    lines.extend(f"- {column}" for column in manifest["feature_columns"])
    sampling = manifest.get("sampling")
    if sampling is not None:
        lines.extend(["", "## Sampling", ""])
        lines.extend(f"- {key}: {value}" for key, value in sampling.items())
    task_notes = manifest.get("task_notes")
    if task_notes is not None:
        lines.extend(["", "## Task Notes", ""])
        lines.extend(f"- {key}: {value}" for key, value in task_notes.items())
    return "\n".join(lines)


def _slug(value: str) -> str:
    slug = "".join(character if character.isalnum() else "_" for character in str(value).strip().lower())
    slug = slug.strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "variant"
