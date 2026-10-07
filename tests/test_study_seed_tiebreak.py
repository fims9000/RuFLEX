from types import SimpleNamespace

from ruflex.application.training import _select_study_run


def test_equal_validation_quality_selects_lowest_split_seed_when_training_seed_is_fixed() -> None:
    runs = [
        SimpleNamespace(seed=5, training_seed=5, split_seed=17),
        SimpleNamespace(seed=5, training_seed=5, split_seed=11),
        SimpleNamespace(seed=5, training_seed=5, split_seed=13),
    ]
    for ordered in (runs, list(reversed(runs))):
        selected, value, rule = _select_study_run([(run, 0.8) for run in ordered], "f1")
        assert selected.split_seed == 11
        assert value == 0.8
        assert rule == "max"


def test_training_seed_remains_primary_exact_tie_break() -> None:
    runs = [
        SimpleNamespace(seed=9, training_seed=9, split_seed=3),
        SimpleNamespace(seed=7, training_seed=7, split_seed=42),
    ]
    selected, value, rule = _select_study_run([(run, 0.2) for run in runs], "rmse")
    assert selected.training_seed == 7
    assert value == 0.2
    assert rule == "min"
