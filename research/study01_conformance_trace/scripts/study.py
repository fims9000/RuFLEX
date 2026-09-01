from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from research.study01_conformance_trace.adapters.analytic_oracle import symmetric_mamdani_centroid, zero_order_sugeno
from research.study01_conformance_trace.adapters.pyfuzzylite_adapter import evaluate as reference_evaluate
from research.study01_conformance_trace.adapters.ruflex_adapter import evaluate as subject_evaluate
from research.study01_conformance_trace.core.metrics import compare
from research.study01_conformance_trace.core.roundtrip import canonical_roundtrip, preserves_semantics
from research.study01_conformance_trace.core.trace_reconstructor import reconstruct
from research.study01_conformance_trace.fixtures.catalog import dev_mamdani, dev_sugeno
from research.study01_conformance_trace.fixtures.generator import write_fixture_inventory


ROOT = Path(__file__).resolve().parents[1]


def dev_vertical_slice() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for fixture, xs in ((dev_mamdani(), [0.25, 0.5, 0.75]), (dev_sugeno(), [0.25, 0.5, 0.75])):
        for x in xs:
            subject = subject_evaluate(fixture, {"x": x})
            reference = reference_evaluate(fixture, {"x": x})
            reconstructed = reconstruct(subject.trace, fixture)
            rows.append({
                "fixture_id": "M01" if fixture.system_type == "mamdani" else "S01", "system_type": fixture.system_type, "input": {"x": x},
                "ruflex_output": subject.output, "pyfuzzylite_output": reference,
                "cross_engine": compare(subject.output, reference, output_range=1.0, atol=1e-10, rtol=1e-10).__dict__,
                "trace_reconstruction": compare(subject.output, reconstructed, output_range=1.0, atol=1e-12, rtol=1e-12).__dict__,
                "roundtrip_semantics": preserves_semantics(fixture),
                "roundtrip_output": subject_evaluate(canonical_roundtrip(fixture), {"x": x}).output,
            })
    result = {
        "schema_version": 1, "kind": "DEV_VERTICAL_SLICE", "generated_at": datetime.now(UTC).isoformat(),
        "analytic_oracles": {"mamdani_symmetry": symmetric_mamdani_centroid().__dict__, "sugeno_x_0_25": zero_order_sugeno(0.25).__dict__},
        "rows": rows,
        "interpretation": "DEV-only. Mamdani cross-engine status is diagnostic and must not alter pre-freeze tolerances.",
    }
    destination = ROOT / "artifacts" / "raw" / "dev_vertical_slice.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["dev-vertical-slice", "prepare-fixtures"])
    args = parser.parse_args()
    if args.command == "dev-vertical-slice":
        result = dev_vertical_slice()
        print(json.dumps({"artifact": "artifacts/raw/dev_vertical_slice.json", "rows": len(result["rows"])}, sort_keys=True))
    elif args.command == "prepare-fixtures":
        outputs = write_fixture_inventory()
        print(json.dumps({"fixture_count": len(outputs), "status": "PRE_FREEZE_ONLY"}, sort_keys=True))


if __name__ == "__main__":
    main()
