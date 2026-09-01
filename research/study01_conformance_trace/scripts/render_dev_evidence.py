from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = ROOT / "artifacts" / "raw" / "dev_vertical_slice.json"
    data = json.loads(source.read_text())
    rows = data["rows"]
    table = ROOT / "tables" / "T00_dev_vertical_slice.csv"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text("fixture_id,x,ruflex_output,pyfuzzylite_output,absolute_error,trace_error\n" + "\n".join(
        f'{row["fixture_id"]},{row["input"]["x"]},{row["ruflex_output"]},{row["pyfuzzylite_output"]},{row["cross_engine"]["absolute_error"]},{row["trace_reconstruction"]["absolute_error"]}' for row in rows
    ) + "\n")
    width, height, left, bottom = 760, 300, 50, 250
    points = []
    maximum = max(abs(row["cross_engine"]["absolute_error"] or 0.0) for row in rows) or 1.0
    for index, row in enumerate(rows):
        x = left + index * 120
        value = abs(row["cross_engine"]["absolute_error"] or 0.0)
        bar = value / maximum * 180
        color = "#b45309" if row["system_type"] == "mamdani" else "#15803d"
        points.append(f'<rect x="{x}" y="{bottom-bar}" width="58" height="{bar}" fill="{color}"/><text x="{x}" y="275" font-size="12">{row["fixture_id"]} {row["input"]["x"]}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><text x="50" y="28" font-size="16">DEV cross-engine absolute error (diagnostic; not a locked result)</text><line x1="{left}" y1="{bottom}" x2="720" y2="{bottom}" stroke="black"/>{"".join(points)}</svg>'
    figure = ROOT / "figures" / "F00_dev_cross_engine_error.svg"
    figure.parent.mkdir(parents=True, exist_ok=True)
    figure.write_text(svg)
    provenance = ROOT / "artifacts" / "aggregated" / "dev_evidence_provenance.json"
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps({"schema_version": 1, "source": str(source.relative_to(ROOT)), "table": str(table.relative_to(ROOT)), "figure": str(figure.relative_to(ROOT)), "classification": "DEV_ONLY"}, indent=2) + "\n")
    print(json.dumps({"table": str(table.relative_to(ROOT)), "figure": str(figure.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
