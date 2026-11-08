"""Pipeline integrity test (SPEC 6.2).

Checks the artifact is a clone-able ``Pipeline`` and compares CV score of the correct pipeline
(preprocessing fit per training fold) against a deliberately leaky variant (preprocessing fit on
all data). A large gap means a step is sensitive to leakage.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline

from leakage_guard.config import Band, GuardConfig
from leakage_guard.detectors.common import classify, make_raw
from leakage_guard.models import Metric, RawFinding, Severity


def score_gap(model: Any, X: Any, y: Any, *, cv: Any = 5, scoring: str | None = None) -> float:
    """Leaky-variant CV score minus correct-pipeline CV score (higher = more leakage).

    Raises TypeError if ``model`` is not a ``Pipeline`` with >= 2 steps, or cannot be cloned.
    """
    if not isinstance(model, Pipeline):
        raise TypeError(f"model must be sklearn Pipeline, got {type(model).__name__}")
    if len(model.steps) < 2:
        raise TypeError("Pipeline has no preprocessing step to check")
    try:
        pipe = clone(model)
    except Exception as exc:  # noqa: BLE001 - surface any clone failure uniformly
        raise TypeError(f"Pipeline is not clone-able: {exc}") from exc
    correct = float(np.mean(cross_val_score(pipe, X, y, cv=cv, scoring=scoring)))
    prep, final = clone(model[:-1]), clone(model.steps[-1][1])
    leaky_X = prep.fit(X, y).transform(X)  # fit on ALL data: the deliberate leak
    leaky = float(np.mean(cross_val_score(final, leaky_X, y, cv=cv, scoring=scoring)))
    return leaky - correct


def pipeline_integrity_findings(
    model: Any,
    X: Any,
    y: Any,
    config: GuardConfig,
    *,
    cv: Any = 5,
    scoring: str | None = None,
) -> list[RawFinding]:
    """Wrap ``score_gap`` as a ``pipeline_integrity`` finding (empty if below warn)."""
    gap = score_gap(model, X, y, cv=cv, scoring=scoring)
    band: Band = config.thresholds.pipeline_gap
    sev = classify(gap, band.warn, band.crit, warn_strict=False)
    if sev is None:
        return []
    return [
        make_raw(
            "prevention",
            "pipeline_integrity",
            sev,
            "pipeline",
            f"Selisih skor CV varian bocor vs pipeline benar = {gap:.3f}.",
            metric=Metric(
                name="score_gap",
                value=gap,
                threshold=band.crit if sev is Severity.CRITICAL else band.warn,
            ),
            evidence={"score_gap": gap},
        )
    ]
