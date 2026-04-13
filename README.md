# RuFLEX

RuFLEX is a research-oriented platform for hybrid deep fuzzy learning.

Recommended repository naming:

- canonical project name: `RuFLEX`
- recommended repo slug: `ruflex-platform`
- acceptable short repo slug: `ruflex`

If the repository is renamed later, `RuFLEX` should stay the primary public-facing name, while the repo slug can remain implementation-oriented.

This repository now contains:

- a new platform layer under `src/ruflex`;
- a vendored snapshot of the `ruanfis` deep fuzzy engine under `src/ruanfis`;
- upstream reference materials under `docs/upstream`, `examples/upstream`, and `tests/upstream`.

The old ideas from earlier branches should be treated as legacy. The current implementation direction is:

`RuFLEX platform -> own SDK / project model / data flow / explainability -> deep fuzzy backend snapshot`

## What Comes From Deep Repo

Deep fuzzy backend behavior should come from the vendored snapshot of
`deep-neuro-fuzzy`, not be reimplemented ad hoc in `RuFLEX`.

Vendored upstream areas:

- `src/ruanfis`
- `tests/upstream`
- `examples/upstream`
- `docs/upstream/deep_fuzzy_feature_learning.md`

Platform-owned areas:

- `src/ruflex`
- non-upstream tests, examples, UI, project serialization, SDK, and data flow

To refresh the vendored snapshot from the upstream repository:

```bash
python scripts/sync_deep_fuzzy_vendor.py
```

The current boundary is documented in
[`docs/upstream/vendor_boundary.md`](docs/upstream/vendor_boundary.md).

## Article Docs

Current Q2 article materials are collected in:

- [`docs/article/article_final_ru.md`](docs/article/article_final_ru.md)
- [`docs/article/article_final_ru.docx`](docs/article/article_final_ru.docx)
- [`docs/article/article_final_ru.pdf`](docs/article/article_final_ru.pdf)
- [`docs/article/article_extended_materials_ru.md`](docs/article/article_extended_materials_ru.md)
- [`docs/article/article_extended_materials_ru.docx`](docs/article/article_extended_materials_ru.docx)
- [`docs/article/article_extended_materials_ru.pdf`](docs/article/article_extended_materials_ru.pdf)
- [`docs/article/benchmark_summary_q2_final_plus.md`](docs/article/benchmark_summary_q2_final_plus.md)
- [`docs/article/visual_package_ru.md`](docs/article/visual_package_ru.md)
- [`docs/article/q2_submission_checklist_ru.md`](docs/article/q2_submission_checklist_ru.md)
- [`docs/article/q2_build_report_ru.md`](docs/article/q2_build_report_ru.md)
- [`docs/article/readiness_report.md`](docs/article/readiness_report.md)
- [`docs/article/q2_submission_package`](docs/article/q2_submission_package)
- [`docs/article/q2_submission_package.zip`](docs/article/q2_submission_package.zip)

Article-oriented benchmark helpers are also available:

- `python scripts/prepare_article_datasets.py --output-root experiments/datasets`
- `python scripts/run_article_benchmark.py --csv <dataset.csv> --target <target_column>`
- `python scripts/run_article_suite.py --dataset-root experiments/datasets`
- `python scripts/prepare_article_materials.py --benchmark-dir <experiments/article_benchmark/...>`
- `python scripts/build_article_final_package.py --skip-suite`
- `python scripts/check_article_readiness.py`

Recommended pre-submission flow:

```bash
.venv/bin/python scripts/build_article_final_package.py --skip-suite
.venv/bin/python scripts/check_article_readiness.py
.venv/bin/python scripts/check_article_readiness.py --run-tests
.venv/bin/python scripts/check_article_readiness.py --strict-submission
```

The build command rebuilds the current Q2 article package, refreshes the
`docx`/`pdf` outputs and rewrites `docs/article/q2_submission_package(.zip)`.
The readiness command writes a current `docs/article/readiness_report.md`
summary for the same Q2 package instead of the archived legacy article flow.
For a real final gate, use `--strict-submission`: it exits with non-zero status
until the package is technically green and the article header contains the
required author metadata for the target venue.

The old profile/reference/submission-state tooling now belongs to the archived
legacy article flow under `docs/article/archive/legacy_versions` and is no
longer part of the primary Q2 submission pipeline. The corresponding legacy
entrypoint scripts were removed from `scripts/`; only the archived materials
and reports are kept for historical reference.

## Toolbox-Style Functions

Besides the `Project` class, `RuFLEX` now exposes a flat toolbox-style API
so the workflow can feel closer to a MATLAB toolbox:

```python
from ruflex import (
    auto_variable,
    attach_dataframe,
    configure_deep_model,
    gaussian_mf,
    infer_variables,
    make_variable,
    model_report,
    new_project,
    predict,
    train,
)
```

```python
project = new_project("demo")
attach_dataframe(project, frame, target_column="y")
infer_variables(project, term_count=3)
configure_deep_model(project, block_size=2, hidden_stage_count=2, concept_width=2)
train(project)
predictions = predict(project, frame[["x1", "x2", "x3", "x4"]])
report = model_report(project)
```

To inspect the available toolbox commands:

```python
from ruflex import format_function_catalog

print(format_function_catalog())
```

You can also construct variables explicitly with toolbox functions:

```python
from ruflex import auto_variable, gaussian_mf, make_variable

temperature = auto_variable("temperature", (0.0, 100.0), term_count=3)
pressure = make_variable(
    "pressure",
    gaussian_mf(
        centers=(10.0, 20.0, 30.0),
        spreads=(4.0, 4.0, 4.0),
        term_names=("low", "mid", "high"),
    ),
    value_range=(0.0, 40.0),
)
```

Manual editing is also available from the toolbox layer, including:

- variable replacement via `get_variable`, `set_variable`, and `variable_catalog`;
- manual rule authoring via `make_antecedent`, `make_rule`, `make_rule_base`;
- block and decision-layer assignment via `list_rule_targets`, `set_block_rule_base`,
  `set_decision_rule_base`, `rule_base_catalog`, and `make_rule_template`.

The Streamlit workbench now mirrors this flow with separate `Variables` and `Rules`
editor tabs on top of the same project API, including structured table editors
for membership terms and manual rules, a guided rule builder with explicit
antecedent/consequent controls, JSON fallback for advanced editing, and
catalog-level import/export for variables and rule bases. The workbench also
now includes a project-management flow for manifests, model presets, and
experiment history, plus quick workspace templates and training presets for
fast switching between flat, compact deep, and article-demo configurations.
On top of that, RuFLEX now includes reproducible study pipelines that run a
full template + training preset + report generation flow in one step. Each
stored study run can now also be exported into an `experiments/<timestamp>_<pipeline>/`
folder with manifest, metrics, variable/rule catalogs, model preset, and text reports,
either manually or directly from `run_study_pipeline(...)`.
The workbench and toolbox can now also browse exported experiment folders and
compare saved runs across one experiment root, as well as restore a workspace
directly from a selected exported study. Exported runs can also be ranked by a
chosen metric and reused through fast model-preset application. For article work,
RuFLEX now includes an article benchmark flow that can run flat/deep comparison
variants, prepare reproducible article datasets, execute a full multi-dataset
article suite, and write article-ready summary tables and figure assets under
`docs/article/assets_q2_final_plus/`.

## Current scope

- platform entities for variables, terms, rules, datasets, projects, and model specs;
- flat neuro-fuzzy and deep fuzzy feature learning adapters on top of `ruanfis`;
- manual variable/rule editing with manifest persistence for user-defined rule bases;
- project serialization, training history, study-run artifact export, and basic plots;
- an optional lightweight Streamlit UI scaffold.

## Install

```bash
python -m pip install -e .[dev]
```

If later we decide to use the backend as an external dependency instead of the vendored copy, the project already reserves an optional extra:

```bash
python -m pip install -e .[external-backend]
```

## Quick start

```python
import pandas as pd

from ruflex import Project

frame = pd.DataFrame(
    {
        "x1": [0.1, 0.2, 0.3, 0.4, 0.5],
        "x2": [0.9, 0.7, 0.5, 0.3, 0.1],
        "y": [0.8, 0.7, 0.5, 0.4, 0.2],
    }
)

project = Project(name="demo", task_type="regression")
project.from_dataframe(frame, target_column="y")
project.infer_variables(term_count=3)
project.configure_model("flat_neuro_fuzzy", max_rules=6)
project.train()
predictions = project.predict(frame[["x1", "x2"]])
summary = project.summary()
dashboard = project.dashboard(frame[["x1", "x2"]].head(1))
report = project.model_report()
```

For a deeper example centered on deep fuzzy feature learning, see
[`examples/train_ruflex_deep_model.py`](examples/train_ruflex_deep_model.py).
For the flat functional workflow, see
[`examples/ruflex_toolbox_workflow.py`](examples/ruflex_toolbox_workflow.py).

## Repository layout

```text
src/ruflex/     RuFLEX platform code
src/ruanfis/    vendored deep fuzzy backend snapshot
docs/article/   article status, checklists, and working paper materials
experiments/    reproducible study runs and exported artifacts
tests/          RuFLEX tests
tests/upstream/ upstream backend reference tests kept for sync
examples/upstream/ upstream backend examples kept for sync
```
