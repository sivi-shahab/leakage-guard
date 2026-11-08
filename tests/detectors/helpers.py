"""Helpers to run a detector in-process on a synthetic variant."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path

from leakage_guard.config import load_config
from leakage_guard.detectors.base import DetectorContext, get_detector
from leakage_guard.models import RawFinding
from leakage_guard.preflight import run_preflight
from leakage_guard.reasons.catalog import CATALOG, THRESHOLD_BASIS


def run_detector(
    write_cfg: Callable[..., Path],
    name: str,
    variant: str,
    attach: Path | None = None,
    **over: object,
) -> list[RawFinding]:
    importlib.import_module(f"leakage_guard.detectors.{name}_detector")
    cfg = load_config(write_cfg(variant, **over))
    pre = run_preflight(cfg, Path("."))
    ctx = DetectorContext(pre.train, pre.test, pre.roles, cfg, attach_dir=attach)
    return get_detector(name).run(ctx)


def assert_contract(findings: list[RawFinding], source: str) -> None:
    """Every finding validates, names its source, and carries the evidence its template needs."""
    for f in findings:
        RawFinding.model_validate(f.model_dump())
        assert f.source == source
        assert CATALOG[f.check_id].evidence_keys <= f.evidence.keys(), f.check_id
        assert f.threshold_basis == THRESHOLD_BASIS[f.check_id]


def ids(findings: list[RawFinding], sev: str | None = None) -> set[str]:
    return {
        f"{f.check_id}:{f.column or f.scope}"
        for f in findings
        if sev is None or f.severity.value == sev
    }
