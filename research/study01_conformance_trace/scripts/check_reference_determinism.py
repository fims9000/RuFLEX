from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fuzzylite
import numpy

from research.study01_conformance_trace.adapters.analytic_oracle import symmetric_mamdani_centroid, zero_order_sugeno
from research.study01_conformance_trace.adapters.pyfuzzylite_adapter import evaluate
from research.study01_conformance_trace.fixtures.catalog import dev_mamdani, dev_sugeno


ROOT = Path(__file__).resolve().parents[1]


def run() -> dict[str, object]:
    cases = [(dev_mamdani(), {"x": x}) for x in (0.25, 0.5, 0.75)] + [(dev_sugeno(), {"x": x}) for x in (0.25, 0.5, 0.75)]
    first = [evaluate(spec, inputs) for spec, inputs in cases]
    repeated = [[evaluate(spec, inputs) for spec, inputs in cases] for _ in range(5)]
    deterministic = all(run_values == first for run_values in repeated)
    return {
        "schema_version": 1,
        "reference": {"pyfuzzylite": fuzzylite.__version__, "numpy": numpy.__version__},
        "outputs": first,
        "repeat_count": len(repeated),
        "deterministic_bitwise_float_equality": deterministic,
        "analytic_oracles": {"symmetric_mamdani": symmetric_mamdani_centroid().__dict__, "zero_order_sugeno_x_0_25": zero_order_sugeno(0.25).__dict__},
        "output_sha256": hashlib.sha256(json.dumps(first, separators=(",", ":")).encode()).hexdigest(),
    }


def main() -> None:
    result = run()
    path = ROOT / "artifacts" / "raw" / "reference_environment_determinism.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"deterministic": result["deterministic_bitwise_float_equality"], "output_sha256": result["output_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
