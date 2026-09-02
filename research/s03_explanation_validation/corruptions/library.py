"""Deterministic S03 corruption constructors; never mutate clean evidence in place."""
from __future__ import annotations
import hashlib, json, random
from copy import deepcopy
from typing import Any

from ruflex.domain.evidence import ExplanationContract

def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

def corrupt_contract(clean: ExplanationContract, *, family: str, subtype: str, severity: str, seed: int) -> tuple[ExplanationContract, list[str]]:
    """Return a new declared corruption and exactly the fields changed."""
    data=clean.model_dump(mode="json"); rng=random.Random(seed); changed=[]
    if family == "M1_MODEL_MISMATCH": data["model_artifact_sha256"]="0"*64; changed=["model_artifact_sha256"]
    elif family == "P1_PREPROCESSING_MISMATCH": data["preprocessing_identity"]="corrupt-preprocessing-identity"; changed=["preprocessing_identity"]
    elif family == "S1_SAMPLE_TARGET_MISMATCH": data["sample_identity"]="corrupt-sample-identity"; changed=["sample_identity"]
    elif family == "R1_REFERENCE_BACKGROUND_MISMATCH": data["reference_identity"]="corrupt-reference-identity"; changed=["reference_identity"]
    elif family in {"A1_ATTRIBUTION_MUTATION","L1_LOW_FIDELITY","ADV_EXPLAINER_AWARE"}:
        magnitudes={"LOW":.05,"MEDIUM":.25,"HIGH":.75}; amount=magnitudes[severity]
        attrs=deepcopy(data["attributions"])
        if subtype == "permutation": rng.shuffle(attrs)
        elif subtype == "sign_flip":
            for a in attrs:a["attribution"]=-a["attribution"]
        else:
            for a in attrs:a["attribution"] += amount * (1 if rng.random()>.5 else -1)
        data["attributions"]=attrs;changed=["attributions"]
    else: raise ValueError(f"Unsupported S03 corruption {family}/{subtype}")
    # A fresh ID makes the corrupt persisted product evidence distinct; all
    # other undeclared contract fields remain copied exactly.
    data.pop("explanation_id",None);corrupt=ExplanationContract.model_validate(data)
    return corrupt,changed

def mutation_receipt(clean: ExplanationContract, corrupt: ExplanationContract, *, family: str, subtype: str, severity: str, seed: int, changed_fields: list[str]) -> dict[str,Any]:
    return {"schema_version":1,"source_clean_sha256":_sha(clean.model_dump(mode="json")),"output_sha256":_sha(corrupt.model_dump(mode="json")),"failure_family":family,"subtype":subtype,"severity":severity,"seed":seed,"changed_fields":changed_fields,"unchanged_fields":"all ExplanationContract fields other than changed_fields and generated explanation_id"}
