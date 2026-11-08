"""Builtin detector: no heavy dependencies (SPEC 4.2).

Written from the SPEC (the legacy ``leakage_check.py`` was not available), so thresholds
and behaviour are the SPEC defaults, not a port.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from leakage_guard.config import GuardConfig
from leakage_guard.detectors.base import DetectorContext, register
from leakage_guard.detectors.common import classify, is_classification, make_raw, sample
from leakage_guard.models import Metric, RawFinding, Severity


def _encode(s: pd.Series) -> npt.NDArray[np.float64]:
    """Numeric encoding for a single-feature tree. Categories become arbitrary ordinal codes."""
    # ponytail: ordinal codes for categoricals; a depth-3 tree can only split them coarsely,
    # so single_feature may under-report high-cardinality categoricals.
    # Upgrade: out-of-fold target encoding.
    if pd.api.types.is_datetime64_any_dtype(s):
        return np.asarray((s - s.min()).dt.total_seconds(), dtype=np.float64)
    if pd.api.types.is_bool_dtype(s) or pd.api.types.is_numeric_dtype(s):
        return np.asarray(s.to_numpy(dtype=float, na_value=np.nan), dtype=np.float64)
    codes, _ = pd.factorize(s)
    return np.asarray(np.where(codes < 0, np.nan, codes), dtype=np.float64)


def _cv_score(x: npt.NDArray[np.float64], y: Any, classification: bool, seed: int) -> float | None:
    X = x.reshape(-1, 1)
    model: Any
    cv: Any
    if classification:
        counts = np.bincount(y)
        present = counts[counts > 0]
        folds = min(5, int(present.min()))
        if folds < 2:
            return None
        model = DecisionTreeClassifier(max_depth=3, random_state=seed)
        cv = StratifiedKFold(folds, shuffle=True, random_state=seed)
        scoring = "roc_auc" if len(present) == 2 else "roc_auc_ovr"
    else:
        model = DecisionTreeRegressor(max_depth=3, random_state=seed)
        cv = KFold(5, shuffle=True, random_state=seed)
        scoring = "r2"
    return float(np.mean(cross_val_score(model, X, y, cv=cv, scoring=scoring)))


def _top(scores: dict[str, float], n: int = 5) -> dict[str, float]:
    return dict(sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:n])


@register
class BuiltinDetector:
    name = "builtin"

    def run(self, ctx: DetectorContext) -> list[RawFinding]:
        out: list[RawFinding] = []
        out += self._row_overlap(ctx)
        out += self._group_overlap(ctx)
        out += self._temporal(ctx)
        out += self._names(ctx)
        out += self._single_feature(ctx)
        out += self._adversarial(ctx)
        return out

    # L1
    def _row_overlap(self, ctx: DetectorContext) -> list[RawFinding]:
        cols = [c for c in ctx.train.columns if c != ctx.roles.index]
        h_tr = pd.util.hash_pandas_object(ctx.train[cols], index=False).to_numpy()
        h_te = pd.util.hash_pandas_object(ctx.test[cols], index=False).to_numpy()
        dup = np.isin(h_te, h_tr)
        n_dup = int(dup.sum())
        pct = 100.0 * n_dup / len(ctx.test)
        band = ctx.config.thresholds.row_overlap
        sev = classify(pct, band.warn_pct, band.crit_pct, warn_strict=True)
        if sev is None:
            return []
        thr = band.crit_pct if sev is Severity.CRITICAL else band.warn_pct
        return [
            make_raw(
                "builtin",
                "row_overlap",
                sev,
                "row",
                "Baris test identik dengan baris train.",
                metric=Metric(name="pct_test_rows", value=pct, threshold=thr),
                evidence={
                    "n_duplicate_rows": n_dup,
                    "pct_test_rows": pct,
                    "n_columns_compared": len(cols),
                },
            )
        ]

    # L2
    def _group_overlap(self, ctx: DetectorContext) -> list[RawFinding]:
        ent = ctx.roles.entity
        if ent is None:
            return []
        te = pd.Index(ctx.test[ent].dropna().unique())
        n_overlap = int(te.isin(ctx.train[ent].dropna().unique()).sum())
        if n_overlap == 0:
            return []
        pct = 100.0 * n_overlap / len(te)
        return [
            make_raw(
                "builtin",
                "group_overlap",
                Severity.CRITICAL,
                "entity",
                "Entitas yang sama ada di train dan test.",
                column=ent,
                metric=Metric(name="n_entities_overlap", value=float(n_overlap), threshold=0.0),
                evidence={"n_entities_overlap": n_overlap, "pct_test_entities": pct},
            )
        ]

    # L3
    def _temporal(self, ctx: DetectorContext) -> list[RawFinding]:
        tcol = ctx.roles.time
        if tcol is None:
            return []
        tr = pd.to_datetime(ctx.train[tcol])
        te = pd.to_datetime(ctx.test[tcol])
        train_max, test_min = tr.max(), te.min()
        out: list[RawFinding] = []
        pct = 100.0 * float((te < train_max).mean())
        band = ctx.config.thresholds.temporal
        sev = classify(pct, band.warn_pct, band.crit_pct, warn_strict=True)
        if sev is not None:
            thr = band.crit_pct if sev is Severity.CRITICAL else band.warn_pct
            out.append(
                make_raw(
                    "builtin",
                    "temporal",
                    sev,
                    "time",
                    "Sebagian data test lebih lama dari data train terakhir.",
                    column=tcol,
                    metric=Metric(name="pct_test_before_train_max", value=pct, threshold=thr),
                    evidence={
                        "train_max": train_max.date().isoformat(),
                        "test_min": test_min.date().isoformat(),
                        "pct_test_before_train_max": pct,
                    },
                )
            )
        embargo = ctx.config.prediction.embargo_days
        gap = (test_min - train_max).days
        if embargo > 0 and gap < embargo:
            out.append(
                make_raw(
                    "builtin",
                    "temporal_embargo",
                    Severity.WARNING,
                    "time",
                    "Jarak train-test kurang dari embargo.",
                    column=tcol,
                    metric=Metric(name="gap_days", value=float(gap), threshold=float(embargo)),
                    evidence={"gap_days": gap, "embargo_days": embargo},
                )
            )
        return out

    # L4 (name based)
    def _names(self, ctx: DetectorContext) -> list[RawFinding]:
        cfg: GuardConfig = ctx.config
        out: list[RawFinding] = []
        forbidden = set(cfg.blocklist.forbidden_columns)
        pats = [p.lower() for p in cfg.blocklist.suspicious_name_patterns]
        for col in ctx.roles.features:
            if col in forbidden:
                out.append(
                    make_raw(
                        "builtin",
                        "blocklist_hit",
                        Severity.CRITICAL,
                        "feature",
                        "Kolom terlarang dipakai sebagai fitur.",
                        column=col,
                        evidence={"blocklist_entry": col},
                    )
                )
            hit = next((p for p in pats if p in col.lower()), None)
            if hit is not None:
                out.append(
                    make_raw(
                        "builtin",
                        "suspicious_names",
                        Severity.WARNING,
                        "feature",
                        "Nama kolom mengisyaratkan informasi pasca-outcome.",
                        column=col,
                        evidence={"matched_pattern": hit},
                    )
                )
        return out

    def _feature_scores(self, ctx: DetectorContext) -> tuple[dict[str, float], bool]:
        cfg = ctx.config
        tr = sample(ctx.train, cfg.runtime.max_rows, cfg.runtime.seed)
        y_raw = tr[ctx.roles.target]
        clf = is_classification(y_raw)
        y = pd.factorize(y_raw)[0] if clf else y_raw.to_numpy(dtype=float)
        scores: dict[str, float] = {}
        for col in ctx.roles.features:
            s = _cv_score(_encode(tr[col]), y, clf, cfg.runtime.seed)
            if s is not None:
                scores[col] = s
        return scores, clf

    # L4 (statistical)
    def _single_feature(self, ctx: DetectorContext) -> list[RawFinding]:
        scores, clf = self._feature_scores(ctx)
        band = ctx.config.thresholds.single_feature
        name = "cv_roc_auc" if clf else "cv_r2"
        out: list[RawFinding] = []
        for col, sc in scores.items():
            sev = classify(sc, band.warn, band.crit, warn_strict=False)
            if sev is None:
                continue
            others = [v for c, v in scores.items() if c != col]
            out.append(
                make_raw(
                    "builtin",
                    "single_feature",
                    sev,
                    "feature",
                    "Fitur tunggal memprediksi target hampir sempurna.",
                    column=col,
                    metric=Metric(
                        name=name,
                        value=sc,
                        threshold=band.crit if sev is Severity.CRITICAL else band.warn,
                    ),
                    evidence={
                        "score": sc,
                        "next_best_score": max(others) if others else 0.0,
                        "top_scores": _top(scores),
                    },
                )
            )
        return out

    # L7
    def _adversarial(self, ctx: DetectorContext) -> list[RawFinding]:
        cfg = ctx.config
        half = cfg.runtime.max_rows // 2
        feats = ctx.roles.features
        tr = sample(ctx.train[feats], half, cfg.runtime.seed)
        te = sample(ctx.test[feats], half, cfg.runtime.seed)
        y = np.r_[np.zeros(len(tr), dtype=int), np.ones(len(te), dtype=int)]
        both = pd.concat([tr, te], ignore_index=True)
        band = cfg.thresholds.adversarial
        scores: dict[str, float] = {}
        for col in feats:
            s = _cv_score(_encode(both[col]), y, True, cfg.runtime.seed)
            if s is not None:
                scores[col] = s
        out: list[RawFinding] = []
        for col, auc in scores.items():
            sev = classify(auc, band.warn, band.crit, warn_strict=False)
            if sev is None:
                continue
            out.append(
                make_raw(
                    "builtin",
                    "adversarial",
                    sev,
                    "feature",
                    "Fitur ini membedakan train dari test.",
                    column=col,
                    metric=Metric(
                        name="adversarial_auc",
                        value=auc,
                        threshold=band.crit if sev is Severity.CRITICAL else band.warn,
                    ),
                    evidence={"auc": auc, "top_scores": _top(scores)},
                )
            )
        return out
