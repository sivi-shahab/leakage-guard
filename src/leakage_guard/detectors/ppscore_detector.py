"""ppscore detector (SPEC 4.4). Needs the ``ppscore`` package (pinned in the Deepchecks env)."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

import pandas as pd

from leakage_guard.detectors.base import DetectorContext, register
from leakage_guard.detectors.common import classify, is_classification, make_raw, sample
from leakage_guard.models import DetectorError, Metric, RawFinding, Severity

NAME = "ppscore"


def _numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """ppscore cannot score datetimes; convert them to seconds since the minimum."""
    out = df[cols].copy()
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = (out[c] - out[c].min()).dt.total_seconds()
    return out


@register
class PpscoreDetector:
    name = NAME

    def run(self, ctx: DetectorContext) -> list[RawFinding]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import ppscore as pps
        except (ImportError, AttributeError, ValueError) as exc:
            raise DetectorError(f"ppscore unavailable in this environment: {exc}") from exc

        cfg, roles = ctx.config, ctx.roles
        n, seed, tgt = cfg.runtime.max_rows, cfg.runtime.seed, roles.target
        clf = is_classification(ctx.train[tgt])

        def frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
            f = _numeric(sample(df, n, seed), cols)
            if clf:  # integer 0/1 targets would otherwise be scored as regression
                f[tgt] = f[tgt].astype(str)
            return f

        cols = [*roles.features, tgt]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s_tr = pps.predictors(frame(ctx.train, cols), y=tgt, sample=n, random_seed=seed)
            s_te = pps.predictors(frame(ctx.test, cols), y=tgt, sample=n, random_seed=seed)
        test_scores = dict(zip(s_te["x"], s_te["ppscore"], strict=True))
        band = cfg.thresholds.pps
        out: list[RawFinding] = []
        for col, score in zip(s_tr["x"], s_tr["ppscore"], strict=True):
            sev = classify(float(score), band.warn, band.crit, warn_strict=False)
            if sev is None:
                continue
            out.append(
                make_raw(
                    NAME,
                    "pps_train",
                    sev,
                    "feature",
                    "Fitur berkorelasi sangat kuat dengan target.",
                    column=col,
                    metric=Metric(
                        name="pps_train",
                        value=float(score),
                        threshold=band.crit if sev is Severity.CRITICAL else band.warn,
                    ),
                    evidence={
                        "pps_train": float(score),
                        "pps_test": float(test_scores.get(col, 0.0)),
                    },
                )
            )
        if roles.index is not None:
            out += self._identifier(ctx, pps, frame)
        return out

    def _identifier(
        self,
        ctx: DetectorContext,
        pps: Any,
        frame: Callable[[pd.DataFrame, list[str]], pd.DataFrame],
    ) -> list[RawFinding]:
        roles, cfg = ctx.roles, ctx.config
        idx = roles.index
        if idx is None:
            return []
        dtype = ctx.train[idx].dtype
        if not (
            pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_datetime64_any_dtype(dtype)
        ):
            return [
                make_raw(
                    NAME,
                    "pps_blind_spot",
                    Severity.INFO,
                    "feature",
                    "PPS tidak dapat menilai kolom ID bertipe string.",
                    column=idx,
                    evidence={"id_dtype": str(dtype)},
                )
            ]
        df = frame(ctx.train, [idx, roles.target])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            score = float(
                pps.score(
                    df, idx, roles.target, sample=cfg.runtime.max_rows, random_seed=cfg.runtime.seed
                )["ppscore"]
            )
        band = cfg.thresholds.identifier_label
        sev = classify(score, band.warn, band.crit, warn_strict=False)
        if sev is None:
            return []
        return [
            make_raw(
                NAME,
                "identifier_label",
                sev,
                "feature",
                "Kolom ID berkorelasi dengan target.",
                column=idx,
                metric=Metric(
                    name="pps_value",
                    value=score,
                    threshold=band.crit if sev is Severity.CRITICAL else band.warn,
                ),
                evidence={"pps_value": score},
            )
        ]
