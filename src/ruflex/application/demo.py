from __future__ import annotations
import json
from pathlib import Path
from uuid import UUID
from ruflex.application.evidence import _atomic_write_text
from ruflex.application.selective import apply_selective_policy, load_latest_selective_policy, load_selective_policy
from ruflex.application.evidence import check_explanation, create_occlusion_explanation
from ruflex.application.assurance import create_assurance_case
from ruflex.application.verification_bundle import export_verification_bundle
from ruflex.domain.demo import ConditionMonitoringDemo

def run_condition_monitoring_demo(root: Path, telemetry: dict[str, float], *, policy_id: UUID | None = None, metadata: dict[str, object] | None = None, generalization_contract_id: UUID | None = None) -> ConditionMonitoringDemo:
    policy = load_latest_selective_policy(root) if policy_id is None else load_selective_policy(root, policy_id)
    decision = apply_selective_policy(root, policy.policy_id, telemetry, metadata=metadata, generalization_contract_id=generalization_contract_id)
    explanation = create_occlusion_explanation(root, policy.run_id, telemetry)
    check = check_explanation(root, explanation.explanation_id)
    assurance = create_assurance_case(root)
    bundle = export_verification_bundle(root)
    result = ConditionMonitoringDemo(policy_id=policy.policy_id, telemetry=telemetry, predicted_class=decision.predicted_label, probability=decision.probability, confidence=decision.confidence, decision=decision.disposition, scope_disposition=decision.scope_disposition, explanation_id=explanation.explanation_id, explanation_check_id=check.check_id, assurance_id=assurance.assurance_id, verification_bundle_sha256=bundle["sha256"])
    directory = Path(root).resolve() / "evidence" / "condition-monitoring-demo"; directory.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(directory / f"{result.demo_id}.json", result.model_dump_json(indent=2))
    _atomic_write_text(directory / "active-demo.json", json.dumps({"demo_id": str(result.demo_id)}))
    return result


def load_latest_condition_monitoring_demo(root: Path) -> ConditionMonitoringDemo:
    directory = Path(root).resolve() / "evidence" / "condition-monitoring-demo"
    pointer = json.loads((directory / "active-demo.json").read_text())
    return ConditionMonitoringDemo.model_validate_json((directory / f"{pointer['demo_id']}.json").read_text())
