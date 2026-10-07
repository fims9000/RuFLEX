from __future__ import annotations

import pytest

from ruflex.application import runtime_training
from ruflex.application.training import train_model
from ruflex.runtime.errors import RuntimeIncompatibleError


def test_train_model_preserves_typed_runtime_incompatibility(monkeypatch, tmp_path) -> None:
    expected = RuntimeIncompatibleError("The frozen split is incompatible with this training request.")

    def reject(*args, **kwargs):
        raise expected

    monkeypatch.setattr(runtime_training, "train_with_adapter", reject)

    with pytest.raises(RuntimeIncompatibleError) as captured:
        train_model(tmp_path, model_kind="logistic_regression", seed=5)

    assert captured.value.code == "RUNTIME_INCOMPATIBLE"
    assert str(captured.value) == str(expected)
