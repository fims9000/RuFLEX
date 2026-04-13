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

Working materials for the paper are collected in:

- [`docs/article/status_matrix.md`](docs/article/status_matrix.md)
- [`docs/article/submission_checklist.md`](docs/article/submission_checklist.md)
- [`docs/article/article_brief.md`](docs/article/article_brief.md)
- [`docs/article/final_status.md`](docs/article/final_status.md)
- [`docs/article/final_metadata.md`](docs/article/final_metadata.md)
- [`docs/article/paper_draft.md`](docs/article/paper_draft.md)
- [`docs/article/paper_draft.docx`](docs/article/paper_draft.docx)
- [`docs/article/article_profile.json`](docs/article/article_profile.json)
- [`docs/article/article_profile_card.md`](docs/article/article_profile_card.md)
- [`docs/article/article_references.json`](docs/article/article_references.json)
- [`docs/article/submission_state.json`](docs/article/submission_state.json)
- [`docs/article/template_mapping.md`](docs/article/template_mapping.md)
- [`docs/article/shablon_dokladov_ready.md`](docs/article/shablon_dokladov_ready.md)
- [`docs/article/conference_template_ready_en.md`](docs/article/conference_template_ready_en.md)
- [`docs/article/shablon_dokladov_illustrated.docx`](docs/article/shablon_dokladov_illustrated.docx)
- [`docs/article/conference_template_illustrated_en.docx`](docs/article/conference_template_illustrated_en.docx)
- [`docs/article/shablon_dokladov_illustrated.pdf`](docs/article/shablon_dokladov_illustrated.pdf)
- [`docs/article/conference_template_illustrated_en.pdf`](docs/article/conference_template_illustrated_en.pdf)
- [`docs/article/figure_manifest.md`](docs/article/figure_manifest.md)
- [`docs/article/manual_finish.md`](docs/article/manual_finish.md)
- [`docs/article/readiness_report.md`](docs/article/readiness_report.md)
- [`docs/article/rinc_draft.md`](docs/article/rinc_draft.md)
- [`docs/article/submission_bundle`](docs/article/submission_bundle)
- [`docs/article/submission_bundle.zip`](docs/article/submission_bundle.zip)

Article-oriented benchmark helpers are also available:

- `python scripts/prepare_article_datasets.py --output-root experiments/datasets`
- `python scripts/run_article_benchmark.py --csv <dataset.csv> --target <target_column>`
- `python scripts/run_article_suite.py --dataset-root experiments/datasets`
- `python scripts/prepare_article_materials.py --benchmark-dir <experiments/article_benchmark/...>`
- `python scripts/check_article_readiness.py`
- `python scripts/build_article_final_package.py --skip-suite`

Recommended pre-submission flow:

```bash
.venv/bin/python scripts/manage_article_profile.py --show
.venv/bin/python scripts/manage_article_references.py --show
.venv/bin/python scripts/manage_submission_state.py --show
.venv/bin/python scripts/render_article_profile_docs.py
.venv/bin/python scripts/build_article_final_package.py --skip-suite
.venv/bin/python scripts/check_article_readiness.py --run-tests
.venv/bin/python scripts/check_article_readiness.py --run-tests --strict-submission
```

The first command syncs author/title/keyword/ORCID/funding data from
`docs/article/article_profile.json` into the generated article docs. The
second command rebuilds the article boards, docx drafts, and
`submission_bundle(.zip)`. The third command writes a compact
`docs/article/readiness_report.md` summary and rechecks the article-related
pytest suite. The profile sync also updates the template-ready markdown
documents and the RINC draft, so author changes should be made in one place
only. Manual submission completion is tracked separately in
`docs/article/submission_state.json`. The readiness report now also exposes
`profile_status`, so placeholder author data is surfaced explicitly even when
the technical article bundle is otherwise green.
For a real final gate, use `--strict-submission`: it exits with non-zero status
until the profile is real and all submission flags are marked done.

For profile edits from the terminal, use:

```bash
.venv/bin/python scripts/manage_article_profile.py --show
.venv/bin/python scripts/manage_article_profile.py \
  --author-set "1:name_ru=Иван Иванов" \
  --author-set "1:name_en=Ivan Ivanov" \
  --author-set "1:email=ivan.ivanov@example.org" \
  --author-set "1:orcid=0000-0001-2345-6789"

.venv/bin/python scripts/manage_article_profile.py \
  --author-add "name_ru=Петр Петров|name_en=Petr Petrov|email=petr.petrov@example.org|orcid=0000-0002-3456-7890|affiliation_ru=Институт, Санкт-Петербург, Россия|affiliation_en=Institute, Saint Petersburg, Russia"

.venv/bin/python scripts/manage_article_profile.py --author-remove 3

.venv/bin/python scripts/manage_article_references.py --show
.venv/bin/python scripts/manage_article_references.py \
  --add "key=new_reference|ru=Новая русская ссылка.|en=New English reference."
.venv/bin/python scripts/manage_article_references.py \
  --set "new_reference:en=Updated English reference."
.venv/bin/python scripts/manage_article_references.py --remove new_reference
```

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
`docs/article/assets/`.

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
