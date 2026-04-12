from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_manifest(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_manifest(manifest: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def save_project_bundle(project, path: str | Path, include_dataset: bool = False) -> None:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    (root / "artifacts").mkdir(exist_ok=True)

    manifest = project.to_manifest()
    save_manifest(manifest, root / "project.json")

    if project.model is not None:
        project.model.save_bundle(root / "artifacts" / "model.pt", metadata={"project_name": project.name})

    if include_dataset and project.dataset is not None:
        project.dataset.frame.to_csv(root / "artifacts" / "dataset.csv", index=False)


def load_project_bundle(path: str | Path):
    from ruflex.sdk.project import Project

    root = Path(path)
    manifest = load_manifest(root / "project.json")
    dataset_path = root / "artifacts" / "dataset.csv"
    frame = None
    if dataset_path.exists():
        frame = pd.read_csv(dataset_path)
    else:
        source_path = manifest.get("dataset_source_path")
        if source_path:
            source_candidate = Path(source_path)
            if source_candidate.exists() and source_candidate.suffix.lower() == ".csv":
                frame = pd.read_csv(source_candidate)
    project = Project.from_manifest(manifest, frame=frame)
    model_path = root / "artifacts" / "model.pt"
    if model_path.exists():
        project._load_model_bundle(model_path)
    return project
