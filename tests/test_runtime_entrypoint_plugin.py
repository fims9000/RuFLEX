from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.runtime_training import train_with_adapter
from ruflex.application.training import load_training_run
from ruflex.runtime.errors import RuntimeDuplicateError
from ruflex.runtime.registry import RuntimeRegistry


def test_real_importlib_metadata_entrypoint_discovers_fixture(monkeypatch, tmp_path: Path) -> None:
    fixture_root = Path(__file__).parent / "fixtures"
    monkeypatch.syspath_prepend(str(fixture_root))
    distribution = tmp_path / "ruflex_fixture-0.0.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text("Metadata-Version: 2.1\nName: ruflex-fixture\nVersion: 0.0\n", encoding="utf-8")
    (distribution / "entry_points.txt").write_text("[ruflex.plugins]\nentrypoint_fixture = ruflex_test_runtime_plugin:factory\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    registry = RuntimeRegistry()
    discovered = registry.discover_entry_points()
    assert [item.identity.key for item in discovered] == ["entrypoint_fixture"]
    assert registry.resolve_model_adapter("entrypoint_fixture").descriptor.training_model_kinds == ("entrypoint_fixture_model",)
    try:
        registry.register_model_adapter(registry.resolve_model_adapter("entrypoint_fixture"))
    except RuntimeDuplicateError as error:
        assert error.code == "RUNTIME_DUPLICATE"
    else:
        raise AssertionError("duplicate runtime identity must fail closed")


def test_entrypoint_fixture_runs_generic_persistence_and_reopen(monkeypatch, tmp_path: Path) -> None:
    fixture_root = Path(__file__).parent / "fixtures"
    monkeypatch.syspath_prepend(str(fixture_root))
    distribution = tmp_path / "ruflex_fixture-0.0.dist-info"; distribution.mkdir()
    (distribution / "METADATA").write_text("Metadata-Version: 2.1\nName: ruflex-fixture\nVersion: 0.0\n", encoding="utf-8")
    (distribution / "entry_points.txt").write_text("[ruflex.plugins]\nentrypoint_fixture = ruflex_test_runtime_plugin:factory\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path)); importlib.invalidate_caches()
    registry = RuntimeRegistry(); registry.discover_entry_points(); registry.freeze()
    root = tmp_path / "project"
    frame = pd.DataFrame({"x": range(32), "target": [index % 2 for index in range(32)]})
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    run = train_with_adapter(root, registry=registry, adapter_key="entrypoint_fixture", model_kind="entrypoint_fixture_model", seed=3)
    assert load_training_run(root, run.run_id).adapter_key == "entrypoint_fixture"
