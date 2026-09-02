"""POST_EXECUTION_READ_ONLY: independently reproduce A01 final statistics."""
from __future__ import annotations
import argparse
from pathlib import Path
from research.a01_stability_aware_review.post_execution import RESULTS, independent_audit

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", type=Path, default=RESULTS)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or args.result_root / "A01_PHASE2_INDEPENDENT_RECOMPUTATION.json"
    audit = independent_audit(args.result_root, output=output)
    print(f"{audit['status']}: {audit['cell_count']} cells; mismatches={len(audit['mismatches'])}")
    if audit["mismatches"]: raise SystemExit(1)

if __name__ == "__main__": main()
