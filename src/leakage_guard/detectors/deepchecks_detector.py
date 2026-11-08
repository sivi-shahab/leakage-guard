"""Deepchecks detector (SPEC 4.3). Needs ``deepchecks==0.19.1`` and its pinned env.

Findings come from two ``Dataset`` pairs because a ``Dataset`` has a single ``index_name``:
entity/time checks use ``entity_col`` as index (L2, L3);
the other checks use ``index_col`` (L1, L4, L5).
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

import pandas as pd

from leakage_guard.detectors.base import DetectorContext, register
from leakage_guard.detectors.common import classify, is_classification, make_raw, sample
from leakage_guard.models import DetectorError, Metric, RawFinding, Severity

log = logging.getLogger(__name__)
NAME = "deepchecks"


def _find(results: list[Any], check_name: str, header_part: str | None = None) -> Any | None:
    for r in results:
        if type(r.check).__name__ == check_name and (
            header_part is None or header_part in r.header
        ):
            return r
    return None


def warn_if_pins_unmet() -> None:
    """Warn (not fail) when numpy/pyarrow break the tested pins, e.g. in a shared environment."""
    from importlib import metadata

    np_major = int(metadata.version("numpy").split(".")[0])
    pa = metadata.version("pyarrow") if _has("pyarrow") else "0"
    pa_t = tuple(int(x) for x in pa.split(".")[:3] if x.isdigit())
    if np_major >= 2 or pa_t > (19, 0, 1):
        log.warning(
            "deepchecks pins not met (numpy=%s, pyarrow=%s; need numpy<2, pyarrow<=19.0.1). "
            "Use the dedicated environment.",
            metadata.version("numpy"),
            pa,
        )


def _has(dist: str) -> bool:
    from importlib import metadata

    try:
        metadata.version(dist)
    except metadata.PackageNotFoundError:
        return False
    return True


@register
class DeepchecksDetector:
    name = NAME

    def run(self, ctx: DetectorContext) -> list[RawFinding]:
        warn_if_pins_unmet()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from deepchecks.tabular import Dataset, Suite
                from deepchecks.tabular.checks import (
                    DateTrainTestLeakageDuplicates,
                    DateTrainTestLeakageOverlap,
                    FeatureLabelCorrelation,
                    IdentifierLabelCorrelation,
                    IndexTrainTestLeakage,
                    TrainTestSamplesMix,
                )
        except (ImportError, AttributeError, ValueError) as exc:
            raise DetectorError(f"deepchecks unavailable in this environment: {exc}") from exc

        cfg, roles = ctx.config, ctx.roles
        quasi = set(
            cfg.privacy.quasi_identifier_columns
        )  # never show their values in HTML displays
        feats = [c for c in roles.features if c not in quasi]
        seed = cfg.runtime.seed
        train = sample(ctx.train, cfg.runtime.max_rows, seed)
        test = sample(ctx.test, cfg.runtime.max_rows, seed)
        clf = is_classification(train[roles.target])
        label_type = (
            ("binary" if train[roles.target].nunique() == 2 else "multiclass")
            if clf
            else "regression"
        )
        cat = [c for c in feats if not pd.api.types.is_numeric_dtype(train[c])]
        with_display = cfg.report.attach_html and ctx.attach_dir is not None

        def datasets(index: str | None, dt: str | None) -> tuple[Any, Any]:
            cols = list(dict.fromkeys([*feats, roles.target, *(c for c in (index, dt) if c)]))

            def mk(df: pd.DataFrame) -> Any:
                d = df[cols].copy()
                if dt:
                    d[dt] = pd.to_datetime(d[dt])
                return Dataset(
                    d,
                    label=roles.target,
                    features=feats,
                    cat_features=cat,
                    index_name=index,
                    datetime_name=dt,
                    label_type=label_type,
                )

            return mk(train), mk(test)

        def run_suite(tag: str, checks: list[Any], pair: tuple[Any, Any]) -> list[Any]:
            suite = Suite(tag, *checks)
            res = suite.run(pair[0], pair[1], with_display=with_display)
            if with_display and ctx.attach_dir is not None:
                ctx.attach_dir.mkdir(parents=True, exist_ok=True)
                res.save_as_html(str(ctx.attach_dir / f"deepchecks_{tag}.html"))
            for r in res.results:
                if not hasattr(r, "value"):  # CheckFailure: fail closed
                    raise DetectorError(
                        f"deepchecks check {type(r.check).__name__} failed: {r.exception!r}"
                    )
            return list(res.results)

        out: list[RawFinding] = []
        ent_checks: list[Any] = []
        if roles.entity:
            ent_checks.append(IndexTrainTestLeakage())
        if roles.time:
            ent_checks += [DateTrainTestLeakageOverlap(), DateTrainTestLeakageDuplicates()]
        if ent_checks:
            res = run_suite("entity_time", ent_checks, datasets(roles.entity, roles.time))
            out += self._entity_time(ctx, res, train, test)

        id_checks: list[Any] = [TrainTestSamplesMix(), FeatureLabelCorrelation()]
        if roles.index:
            id_checks.append(IdentifierLabelCorrelation())
        res = run_suite("samples_features", id_checks, datasets(roles.index, None))
        out += self._samples_features(ctx, res, len(test), len(feats))
        return out

    def _entity_time(
        self, ctx: DetectorContext, res: list[Any], train: pd.DataFrame, test: pd.DataFrame
    ) -> list[RawFinding]:
        roles, bands = ctx.roles, ctx.config.thresholds
        out: list[RawFinding] = []
        r = _find(res, "IndexTrainTestLeakage")
        if r is not None and r.value > 0 and roles.entity:
            pct = 100.0 * float(r.value)
            out.append(
                make_raw(
                    NAME,
                    "group_overlap",
                    Severity.CRITICAL,
                    "entity",
                    "Entitas yang sama ada di train dan test.",
                    column=roles.entity,
                    metric=Metric(name="pct_test_entities", value=pct, threshold=0.0),
                    evidence={"pct_test_entities": pct},
                )
            )
        if roles.time is None:
            return out
        r = _find(res, "DateTrainTestLeakageOverlap")
        if r is not None:
            pct = 100.0 * float(r.value)
            band = bands.temporal
            sev = classify(pct, band.warn_pct, band.crit_pct, warn_strict=True)
            if sev is not None:
                tr_max = pd.to_datetime(train[roles.time]).max()
                te_min = pd.to_datetime(test[roles.time]).min()
                out.append(
                    make_raw(
                        NAME,
                        "temporal",
                        sev,
                        "time",
                        "Sebagian data test lebih lama dari data train terakhir.",
                        column=roles.time,
                        metric=Metric(
                            name="pct_test_before_train_max",
                            value=pct,
                            threshold=band.crit_pct if sev is Severity.CRITICAL else band.warn_pct,
                        ),
                        evidence={
                            "train_max": tr_max.date().isoformat(),
                            "test_min": te_min.date().isoformat(),
                            "pct_test_before_train_max": pct,
                        },
                    )
                )
        r = _find(res, "DateTrainTestLeakageDuplicates")
        if r is not None and r.value > 0:
            out.append(
                make_raw(
                    NAME,
                    "date_shared",
                    Severity.INFO,
                    "time",
                    "Tanggal test juga ada di train (bukan urutan waktu).",
                    column=roles.time,
                    evidence={"pct_test_dates_shared": 100.0 * float(r.value)},
                )
            )
        return out

    def _samples_features(
        self, ctx: DetectorContext, res: list[Any], n_test: int, n_feats: int
    ) -> list[RawFinding]:
        bands = ctx.config.thresholds
        out: list[RawFinding] = []
        r = _find(res, "TrainTestSamplesMix")
        if r is not None:
            ratio = float(r.value["ratio"])
            pct = 100.0 * ratio
            sev = classify(
                pct, bands.row_overlap.warn_pct, bands.row_overlap.crit_pct, warn_strict=True
            )
            if sev is not None:
                out.append(
                    make_raw(
                        NAME,
                        "row_overlap",
                        sev,
                        "row",
                        "Baris test identik dengan baris train.",
                        metric=Metric(
                            name="pct_test_rows",
                            value=pct,
                            threshold=bands.row_overlap.crit_pct
                            if sev is Severity.CRITICAL
                            else bands.row_overlap.warn_pct,
                        ),
                        evidence={
                            "n_duplicate_rows": round(ratio * n_test),
                            "pct_test_rows": pct,
                            "n_columns_compared": n_feats,
                        },
                    )
                )
        tr = _find(res, "FeatureLabelCorrelation", "Train")
        te = _find(res, "FeatureLabelCorrelation", "Test")
        if tr is not None:
            for col, score in tr.value.items():
                sev = classify(float(score), bands.pps.warn, bands.pps.crit, warn_strict=False)
                if sev is None:
                    continue
                ev: dict[str, Any] = {"pps_train": float(score)}
                if te is not None and col in te.value:
                    ev["pps_test"] = float(te.value[col])
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
                            threshold=bands.pps.crit
                            if sev is Severity.CRITICAL
                            else bands.pps.warn,
                        ),
                        evidence=ev,
                    )
                )
        r = _find(res, "IdentifierLabelCorrelation")
        if r is not None:
            for col, score in r.value.items():
                band = bands.identifier_label
                sev = classify(float(score), band.warn, band.crit, warn_strict=False)
                if sev is not None:
                    out.append(
                        make_raw(
                            NAME,
                            "identifier_label",
                            sev,
                            "feature",
                            "Kolom ID berkorelasi dengan target.",
                            column=col,
                            metric=Metric(
                                name="pps_value",
                                value=float(score),
                                threshold=band.crit if sev is Severity.CRITICAL else band.warn,
                            ),
                            evidence={"pps_value": float(score)},
                        )
                    )
        return out
