"""Cleanlab Datalab detector (SPEC 4.5). Needs ``cleanlab[datalab]``."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd

from leakage_guard.detectors.base import DetectorContext, register
from leakage_guard.detectors.common import classify, make_raw, sample
from leakage_guard.models import DetectorError, Metric, RawFinding, Severity

NAME = "cleanlab"
_MAX_ONEHOT = 20


def feature_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Numeric matrix for Datalab: z-scored numerics, one-hot for low-cardinality categoricals.

    High-cardinality categoricals are skipped (their one-hot scale would dominate distances).
    """
    parts: list[pd.DataFrame] = []
    for c in cols:
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            s = (s - s.min()).dt.total_seconds()
        if (
            pd.api.types.is_bool_dtype(s)
            or pd.api.types.is_numeric_dtype(s)
            or str(s.dtype) == "float64"
        ):
            x = s.astype(float)
            x = x.fillna(x.median())
            sd = x.std()
            parts.append(((x - x.mean()) / (sd if sd > 0 else 1.0)).to_frame(c))
        elif s.nunique() <= _MAX_ONEHOT:
            parts.append(pd.get_dummies(s, prefix=c, dtype=float))
    if not parts:
        raise DetectorError("cleanlab: no usable numeric/low-cardinality features")
    return pd.concat(parts, axis=1)


@register
class CleanlabDetector:
    name = NAME

    def run(self, ctx: DetectorContext) -> list[RawFinding]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from cleanlab import Datalab
        except (ImportError, AttributeError, ValueError) as exc:
            raise DetectorError(f"cleanlab unavailable in this environment: {exc}") from exc

        cfg, roles = ctx.config, ctx.roles
        half, seed = cfg.runtime.max_rows // 2, cfg.runtime.seed
        tr = sample(ctx.train, half, seed)
        te = sample(ctx.test, half, seed)
        both = pd.concat([tr, te], ignore_index=True)
        is_test = np.r_[np.zeros(len(tr), dtype=bool), np.ones(len(te), dtype=bool)]
        X = feature_matrix(both, roles.features)
        data = X.copy()
        data["__label__"] = pd.factorize(both[roles.target])[0]
        lab = Datalab(data=data, label_name="__label__", verbosity=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lab.find_issues(
                features=X.to_numpy(dtype=float),
                issue_types={
                    "near_duplicate": {"threshold": cfg.thresholds.near_dup_threshold},
                    "label": {},
                },
            )
        return self._near_dup(ctx, lab, is_test) + self._labels(lab, is_test)

    def _near_dup(
        self, ctx: DetectorContext, lab: Any, is_test: np.ndarray[Any, Any]
    ) -> list[RawFinding]:
        iss = lab.get_issues("near_duplicate")
        flagged = np.flatnonzero(iss["is_near_duplicate_issue"].to_numpy())
        sets: set[frozenset[int]] = set()
        test_rows = 0
        for i in flagged:
            members = frozenset([int(i), *map(int, iss["near_duplicate_sets"].iloc[i])])
            splits = {bool(is_test[m]) for m in members}
            if len(splits) < 2:
                continue
            sets.add(members)
            test_rows += bool(is_test[i]) and any(not is_test[m] for m in members)
        if not sets:
            return []
        pct = 100.0 * test_rows / int(is_test.sum())
        band = ctx.config.thresholds.near_dup_cross_split
        sev = classify(pct, band.warn_pct, band.crit_pct, warn_strict=True) or Severity.WARNING
        return [
            make_raw(
                NAME,
                "near_dup_cross_split",
                sev,
                "row",
                "Sampel hampir identik ada di train dan test.",
                metric=Metric(
                    name="pct_test_rows",
                    value=pct,
                    threshold=band.crit_pct if sev is Severity.CRITICAL else band.warn_pct,
                ),
                evidence={"n_sets_cross_split": len(sets), "pct_test_rows": pct},
            )
        ]

    def _labels(self, lab: Any, is_test: np.ndarray[Any, Any]) -> list[RawFinding]:
        flagged = lab.get_issues("label")["is_label_issue"].to_numpy() & ~is_test
        n = int(flagged.sum())
        if n == 0:
            return []
        return [
            make_raw(
                NAME,
                "label_errors",
                Severity.INFO,
                "dataset",
                "Diduga ada label yang salah di train.",
                evidence={"n_label_issues": n, "pct_train_rows": 100.0 * n / int((~is_test).sum())},
            )
        ]
