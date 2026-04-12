from __future__ import annotations


class ExperimentalSpatialFuzzyModel:
    def __init__(self) -> None:
        self.kind = "spatial_fuzzy_experimental"

    def fit(self, *args, **kwargs):
        raise NotImplementedError(
            "The spatial fuzzy mode is still an experimental scaffold in the first RuFLEX iteration."
        )

