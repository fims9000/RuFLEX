from __future__ import annotations

import json

from ruflex.application.fis import semantic_hash, with_semantic_hash
from ruflex.domain.fis import FISSpec


def canonical_roundtrip(spec: FISSpec) -> FISSpec:
    """Round-trip the declarative canonical payload, never an executable pickle."""
    return with_semantic_hash(FISSpec.model_validate(json.loads(spec.model_dump_json())))


def preserves_semantics(spec: FISSpec) -> bool:
    return semantic_hash(spec) == semantic_hash(canonical_roundtrip(spec))
