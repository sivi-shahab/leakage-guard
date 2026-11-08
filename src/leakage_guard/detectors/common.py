"""Helpers shared by detectors."""

from __future__ import annotations

from typing import Any

import pandas as pd

from leakage_guard.models import Metric, RawFinding, Scope, Severity
from leakage_guard.reasons.catalog import THRESHOLD_BASIS

MAX_CLASSES = 20


def classify(value: float, warn: float, crit: float, *, warn_strict: bool) -> Severity | None:
    """Severity for ``value`` against a warn/crit band; ``None`` if below warn."""
    if value >= crit:
        return Severity.CRITICAL
    if (value > warn) if warn_strict else (value >= warn):
        return Severity.WARNING
    return None


def make_raw(
    source: str,
    check_id: str,
    severity: Severity,
    scope: Scope,
    message: str,
    *,
    column: str | None = None,
    metric: Metric | None = None,
    evidence: dict[str, Any] | None = None,
) -> RawFinding:
    return RawFinding(
        check_id=check_id,
        severity=severity,
        scope=scope,
        column=column,
        metric=metric,
        threshold_basis=THRESHOLD_BASIS[check_id],
        evidence=evidence or {},
        source=source,
        message=message,
    )


def sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    return df.sample(n=n, random_state=seed) if len(df) > n else df


def is_classification(y: pd.Series) -> bool:
    return not (pd.api.types.is_float_dtype(y) and y.nunique() > MAX_CLASSES)
