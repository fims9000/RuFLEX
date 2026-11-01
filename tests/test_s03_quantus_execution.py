from __future__ import annotations

import random

import numpy as np
import torch

from research.s03_explanation_validation.quantus_execution import controlled_rng, effective_seed


def test_s03_quantus_effective_seed_is_parent_metric_specific_and_stable() -> None:
    first = effective_seed("clean-parent-a", "faithfulness_correlation")
    assert first == effective_seed("clean-parent-a", "faithfulness_correlation")
    assert first != effective_seed("clean-parent-a", "max_sensitivity")
    assert first != effective_seed("clean-parent-b", "faithfulness_correlation")
    assert 0 <= first < 2**32


def test_s03_quantus_rng_context_restores_process_rng_state() -> None:
    random.seed(91); np.random.seed(91); torch.manual_seed(91)
    python_state, numpy_state, torch_state = random.getstate(), np.random.get_state(), torch.random.get_rng_state().clone()
    with controlled_rng(3003):
        _ = random.random(), np.random.random(), torch.rand(1)
    assert random.getstate() == python_state
    restored = np.random.get_state()
    assert restored[0] == numpy_state[0] and restored[2:] == numpy_state[2:] and np.array_equal(restored[1], numpy_state[1])
    assert torch.equal(torch.random.get_rng_state(), torch_state)
