# RuFLEX Python access

Studio and Python use the same persisted project objects. The Product V1 Python escape hatch is intentionally **read-only by default** so a notebook/script cannot silently mutate a Studio project or invalidate its provenance.

```python
from ruflex.sdk import open_studio_project

project = open_studio_project("/path/to/project")

print(project.manifest.name)
print(project.dataset_contract())
print(project.dataset_profile())
print(project.active_fis())
print(project.fis_revisions())
print(project.training_runs())
print(project.jobs())  # persisted LocalExecutor state; no resubmission
print(project.explanation_validator_plugins())
print(project.lineage())
```

## Persisted analyses and evidence

Object IDs shown in the Studio/lineage graph can be reopened directly:

```python
evaluation = project.evaluation(evaluation_id)
calibration = project.calibration(calibration_id)
threshold = project.threshold(threshold_id)
final_test = project.final_test(final_test_id)
comparison = project.comparison(comparison_id)
slices = project.slice_analysis(slice_analysis_id)

explanation = project.explanation(explanation_id)
check = project.explanation_check(check_id)
correction = project.expert_correction(correction_id)
generalization = project.generalization_contract()  # active contract
```

`project.final_test(...)` returns the separately persisted final-test evidence object; it does not refit calibration, select a threshold or mutate the original TrainingRun. Likewise, explanation objects expose their saved epistemic category and identity/provenance rather than recomputing a new explanation implicitly.

## Canonical FIS JSON/YAML

The Studio API exposes the active canonical FIS in both JSON and YAML representations. These are representations of the same executable FIS object used by the GUI; they are not a parallel GUI-only schema.

API routes:

```text
GET /api/projects/{session_id}/fis/canonical.json
GET /api/projects/{session_id}/fis/canonical.yaml
```

## Extension boundary

For custom integrations, `ruflex.plugins` exposes narrow protocol boundaries for model adapters, explainers, explanation validators, metrics and exporters. Plugins are expected to return canonical/persistable objects through the application layer instead of maintaining parallel state.

The supported Product V1 principle is:

```text
GUI object == persisted canonical object == Python-readable object
```

Mutating SDK helpers can be added later behind explicit revision/provenance semantics; the current escape hatch stays conservative on purpose.
