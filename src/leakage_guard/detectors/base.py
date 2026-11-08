"""Detector protocol and registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

import pandas as pd

from leakage_guard.config import GuardConfig
from leakage_guard.models import DetectorError, RawFinding
from leakage_guard.preflight import Roles


@dataclass(frozen=True)
class DetectorContext:
    """Clean (PII-free) data plus configuration handed to a detector."""

    train: pd.DataFrame
    test: pd.DataFrame
    roles: Roles
    config: GuardConfig
    attach_dir: Path | None = None  # where a detector may write report attachments (e.g. HTML)


class Detector(Protocol):
    name: str

    def run(self, ctx: DetectorContext) -> list[RawFinding]: ...


_D = TypeVar("_D", bound=type[Detector])

REGISTRY: dict[str, type[Detector]] = {}


def register(cls: _D) -> _D:
    """Class decorator: register a detector under its ``name``."""
    REGISTRY[cls.name] = cls
    return cls


def get_detector(name: str) -> Detector:
    cls = REGISTRY.get(name)
    if cls is None:
        raise DetectorError(f"detector '{name}' is not registered/available in this build")
    return cls()
