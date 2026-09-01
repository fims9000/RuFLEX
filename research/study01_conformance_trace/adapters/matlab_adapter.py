from __future__ import annotations


class MatlabUnavailable(RuntimeError):
    pass


def availability() -> dict[str, str]:
    return {"status": "NOT_AVAILABLE", "reason": "MATLAB Engine is not installed/licensed in this environment."}


def evaluate(*_args: object, **_kwargs: object) -> float:
    raise MatlabUnavailable(availability()["reason"])
