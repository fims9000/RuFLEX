"""Deterministic, pre-final-test orchestration helpers for A01.

This module deliberately does not implement another training or stability
algorithm.  It prepares declared tables and invokes the canonical RuFLEX API
for the smoke route only.  It has no function that evaluates a final test.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pandas as pd


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
PRODUCT_SNAPSHOT = "c610f5740f2b26d60eabd9069a298dc6022c9548"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_csv_bytes(frame: pd.DataFrame) -> bytes:
    # A single serialization contract makes the materialized-table identity
    # independent of platform newline conventions.
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _one_hot(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return pd.get_dummies(frame, columns=columns, dtype=int)


def materialize_table(dataset_id: str, raw_path: Path, spec: dict[str, Any]) -> pd.DataFrame:
    """Apply the declared, deterministic source-to-product transformation."""
    transform = spec["materialization"]
    if dataset_id == "ai4i_2020":
        frame = pd.read_csv(raw_path)
        frame["source_row_id"] = frame["UDI"].astype(int)
        frame = frame.drop(columns=transform["excluded_columns"])
        frame = _one_hot(frame, transform["categorical_columns"])
        frame[spec["target"]] = frame[spec["target"]].astype(int)
    elif dataset_id == "uci_bank_marketing":
        with zipfile.ZipFile(raw_path) as archive:
            with archive.open(transform["archive_member"]) as handle:
                frame = pd.read_csv(handle, sep=";")
        frame["source_row_id"] = range(len(frame))
        frame = frame.drop(columns=transform["excluded_columns"])
        frame[spec["target"]] = (frame[spec["target"]] == spec["positive_class_mapping"]["positive_source_value"]).astype(int)
        frame = _one_hot(frame, transform["categorical_columns"])
    elif dataset_id == "wisconsin_diagnostic":
        names = transform["column_names"]
        frame = pd.read_csv(raw_path, header=None, names=names)
        frame[spec["target"]] = (frame[spec["target"]] == spec["positive_class_mapping"]["positive_source_value"]).astype(int)
    else:
        raise ValueError(f"Unsupported A01 dataset {dataset_id!r}.")
    expected = [*spec["row_identity"], *spec["feature_columns"], spec["target"]]
    frame = frame.loc[:, expected]
    if list(frame.columns) != expected:
        raise ValueError(f"Materialized {dataset_id} columns differ from its locked feature-order identity.")
    if frame.isna().any().any():
        raise ValueError(f"Materialized {dataset_id} violates its declared no-missing-values policy.")
    return frame


def materialize_dataset(spec: dict[str, Any], *, source_path: Path, output_root: Path) -> dict[str, Any]:
    """Verify one raw source and persist its declared canonical numeric table."""
    # Only materialization needs product split semantics. Keeping this import
    # local lets the pure lock builder run without importing the whole app.
    from ruflex.core.enums import NormalizationMode
    from ruflex.data.datasets import DatasetConfig, TabularDataset
    source_path = source_path.resolve()
    raw_hash = sha256_file(source_path)
    if raw_hash != spec["raw_file_sha256"]:
        raise ValueError(f"Raw SHA-256 mismatch for {spec['canonical_dataset_id']}: expected locked source bytes.")
    table = materialize_table(spec["canonical_dataset_id"], source_path, spec)
    table_bytes = canonical_csv_bytes(table)
    table_hash = sha256_bytes(table_bytes)
    expected_hash = spec.get("materialized_table_sha256")
    if expected_hash and table_hash != expected_hash:
        raise ValueError(f"Materialized SHA-256 mismatch for {spec['canonical_dataset_id']}.")
    fractions = spec["split_fractions"]
    split = TabularDataset.from_dataframe(table).split(DatasetConfig(
        target_column=spec["target"], feature_columns=tuple(spec["feature_columns"]),
        validation_fraction=fractions["validation"], test_fraction=fractions["final_test"],
        normalization=NormalizationMode.STANDARD, fill_missing="median", random_state=spec["split_seed"],
    ))
    row_id = spec["row_identity"][0]
    split_identities = {
        "train": sha256_bytes(canonical_json(sorted(table.loc[split.train_indices, row_id].astype(str).tolist())).encode("utf-8")),
        "validation": sha256_bytes(canonical_json(sorted(table.loc[split.validation_indices, row_id].astype(str).tolist())).encode("utf-8")),
        "final_test": sha256_bytes(canonical_json(sorted(table.loc[split.test_indices, row_id].astype(str).tolist())).encode("utf-8")),
    }
    expected_split_identities = spec.get("split_identities")
    if expected_split_identities and split_identities != expected_split_identities:
        raise ValueError(f"Frozen split identities differ for {spec['canonical_dataset_id']}.")
    destination = output_root / spec["canonical_dataset_id"]
    destination.mkdir(parents=True, exist_ok=True)
    table_path = destination / "canonical.csv"
    table_path.write_bytes(table_bytes)
    manifest = {
        "study": "A01 — Stability-Aware Selective Review",
        "status": "PRE_FREEZE_DATA_MATERIALIZATION_ONLY",
        "canonical_dataset_id": spec["canonical_dataset_id"],
        "source_url": spec["source_url"],
        "source_path": str(source_path),
        "raw_file_sha256": raw_hash,
        "materialized_table_sha256": table_hash,
        "materialized_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(table)),
        "column_count": int(len(table.columns)),
        "target": spec["target"],
        "feature_columns": spec["feature_columns"],
        "row_identity": spec["row_identity"],
        "preprocessing_declaration": spec["preprocessing"],
        "split_identities": split_identities,
        "license_source_note": spec["license_source_note"],
        "final_test_accessed": False,
    }
    (destination / "dataset-manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest


def obtain_source(spec: dict[str, Any], *, source_dir: Path | None, download: bool, destination: Path) -> Path:
    """Resolve an explicit local source or perform the declared download."""
    filename = spec["source_filename"]
    if source_dir is not None:
        local = source_dir / filename
        if not local.exists():
            raise FileNotFoundError(f"Expected {filename} under --source-dir.")
        return local
    if not download:
        raise ValueError("Provide --source-dir or explicitly pass --download; A01 never uses an implicit fetcher.")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / filename
    with urllib.request.urlopen(spec["source_url"], timeout=60) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return target


def build_execution_plan(dataset_specs: dict[str, Any], model_specs: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in dataset_specs["datasets"]:
        for model in model_specs["models"]:
            for training_seed in plan["training_seeds"]:
                identity = canonical_json({
                    "dataset_id": dataset["canonical_dataset_id"], "dataset_spec_sha256": dataset_specs["dataset_spec_sha256"],
                    "materialized_table_sha256": dataset["materialized_table_sha256"], "split_identities": dataset["split_identities"],
                    "model_family": model["model_family"], "model_spec_sha256": model_specs["model_spec_sha256"],
                    "split_seed": plan["split_seed"], "training_seed": training_seed,
                    "validation_fraction": plan["split_fractions"]["validation"], "test_fraction": plan["split_fractions"]["final_test"],
                })
                rows.append({
                    "execution_id": str(uuid5(NAMESPACE_URL, f"ruflex-a01/{identity}")),
                    "protocol": "TRAINING_VARIABILITY", "dataset_id": dataset["canonical_dataset_id"],
                    "dataset_spec_sha256": dataset_specs["dataset_spec_sha256"], "model_family": model["model_family"],
                    "materialized_table_sha256": dataset["materialized_table_sha256"], "split_identities": dataset["split_identities"],
                    "model_spec_sha256": model_specs["model_spec_sha256"], "split_seed": plan["split_seed"],
                    "training_seed": training_seed, "split_fractions": plan["split_fractions"],
                    "preprocessing_identity": model["preprocessing_identity"], "execution_identity_sha256": sha256_bytes(identity.encode("utf-8")),
                    "final_test_execution": "FORBIDDEN_UNTIL_SEPARATE_AUTHORIZATION",
                })
    return rows


def declared_run_support_status(declared_seeds: list[int], run_states: dict[int, str]) -> dict[str, Any]:
    """Fail closed for the A01 20-fit primary protocol.

    This contract is consumed by a future validation executor.  It never
    replaces a failed seed and never turns an incomplete cell into a partial
    stability analysis.
    """
    expected = list(declared_seeds)
    missing = [seed for seed in expected if run_states.get(seed) != "SUCCEEDED"]
    unexpected = sorted(set(run_states) - set(expected))
    return {
        "status": "READY_FOR_PRE_FINAL_EVIDENCE" if not missing and not unexpected else "INCOMPLETE_DECLARED_RUN_SUPPORT",
        "declared_run_count": len(expected), "successful_run_count": len(expected) - len(missing),
        "missing_or_failed_training_seeds": missing, "unexpected_training_seeds": unexpected,
        "replacement_seed_permitted": False,
    }


def write_locked_plan(path: Path, rows: list[dict[str, Any]]) -> str:
    content = "".join(canonical_json(row) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")
    return sha256_bytes(content.encode("utf-8"))


def config_hash(path: Path) -> str:
    return sha256_file(path)
