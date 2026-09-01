from __future__ import annotations

import json
import platform
import sys
from importlib.metadata import distributions
from pathlib import Path

import fuzzylite
import numpy


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    path = ROOT / "config" / "environments.json"
    data = json.loads(path.read_text())
    packages = {distribution.metadata["Name"].lower(): distribution.version for distribution in distributions() if distribution.metadata.get("Name")}
    data["pyfuzzylite"]["captured_runtime"] = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "numpy": numpy.__version__,
        "fuzzylite_import_version": fuzzylite.__version__,
        "executable_basename": Path(sys.executable).name,
        "locked_requirements_sha256": __import__("hashlib").sha256((ROOT / "config" / "reference-requirements.txt").read_bytes()).hexdigest(),
        "installed_packages": dict(sorted(packages.items())),
    }
    data["pyfuzzylite"]["status"] = "PINNED_REFERENCE_READY"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(json.dumps(data["pyfuzzylite"]["captured_runtime"], sort_keys=True))


if __name__ == "__main__":
    main()
