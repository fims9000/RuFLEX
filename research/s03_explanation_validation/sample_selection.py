"""Frozen S03 validation-sample selection; independent of explanations."""
from __future__ import annotations
from collections.abc import Iterable

def select_validation_samples(rows: Iterable[dict], *, required: int = 8) -> list[dict]:
    """Select up to two per truth/prediction stratum, then source-row fallback."""
    values=sorted((dict(row) for row in rows),key=lambda row:int(row["source_row"]))
    if len(values)<required: raise ValueError("VALIDATION_SUPPORT_LT_8")
    selected=[]; used=set()
    for stratum in ((0,0),(0,1),(1,0),(1,1)):
        members=[row for row in values if (int(row["truth"]),int(row["prediction"]))==stratum]
        for row in members[:2]: selected.append(row);used.add(int(row["source_row"]))
    for row in values:
        if len(selected)>=required: break
        if int(row["source_row"]) not in used: selected.append(row);used.add(int(row["source_row"]))
    if len(selected)!=required: raise ValueError("VALIDATION_SUPPORT_LT_8")
    return selected
