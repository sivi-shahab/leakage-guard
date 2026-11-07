"""Preflight: validate inputs, drop PII, resolve column roles (SPEC 4.1)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from leakage_guard.config import GuardConfig
from leakage_guard.io import read_table, write_parquet
from leakage_guard.models import Metric, PreflightError, RawFinding, Severity

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Roles:
    target: str
    entity: str | None
    time: str | None
    index: str | None
    features: list[str]


@dataclass
class PreflightResult:
    train: pd.DataFrame
    test: pd.DataFrame
    roles: Roles
    fingerprint: dict[str, Any]
    findings: list[RawFinding] = field(default_factory=list)


def _hash_values(s: pd.Series) -> pd.Series:
    """Deterministic pseudonym so overlap checks still work on identifier columns."""
    return s.astype(str).map(lambda v: hashlib.sha256(f"lg:{v}".encode()).hexdigest()[:16])


def _schema_hash(df: pd.DataFrame) -> str:
    blob = "|".join(f"{c}:{df[c].dtype}" for c in df.columns)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def run_preflight(cfg: GuardConfig, base_dir: Path) -> PreflightResult:
    """Load train/test, validate, drop PII, and return clean frames plus roles."""
    d = cfg.data

    def resolve(p: str) -> Path:
        q = Path(p)
        return q if q.is_absolute() or "://" in p else base_dir / q

    train = read_table(resolve(d.train))
    test = read_table(resolve(d.test))

    if train.empty or test.empty:
        raise PreflightError("train and test must not be empty")
    if list(train.columns) != list(test.columns) and set(train.columns) != set(test.columns):
        diff = sorted(set(train.columns) ^ set(test.columns))
        raise PreflightError(f"train and test columns differ: {diff}")
    test = test[list(train.columns)]

    required = {
        "data.target": d.target,
        "data.entity_col": d.entity_col,
        "data.time_col": d.time_col,
        "data.index_col": d.index_col,
        "prediction.prediction_date_col": cfg.prediction.prediction_date_col,
    }
    for fld, col in required.items():
        if col is not None and col not in train.columns:
            raise PreflightError(f"{fld}: column '{col}' not found in data")
    for col in cfg.privacy.quasi_identifier_columns:
        if col not in train.columns:
            raise PreflightError(f"privacy.quasi_identifier_columns: '{col}' not found in data")
    if pd.concat([train[d.target], test[d.target]]).nunique() < 2 or train[d.target].nunique() < 2:
        raise PreflightError("target has fewer than two classes in train")

    findings = _quasi_identifier_findings(cfg, train, test)

    # Role columns that are also declared PII are pseudonymised (needed for overlap checks);
    # every other PII column is dropped before detectors see the data.
    roles_cols = {c for c in (d.entity_col, d.time_col, d.index_col, d.target) if c}
    for col in d.pii_columns:
        if col in roles_cols and col in train.columns:
            train[col] = _hash_values(train[col])
            test[col] = _hash_values(test[col])
    drop = [c for c in d.pii_columns if c in train.columns and c not in roles_cols]
    train = train.drop(columns=drop)
    test = test.drop(columns=drop)

    features = [c for c in train.columns if c not in roles_cols]
    roles = Roles(d.target, d.entity_col, d.time_col, d.index_col, features)
    fingerprint = {
        "train_rows": len(train),
        "test_rows": len(test),
        "schema_hash": _schema_hash(train),
    }
    log.info(
        "preflight ok: %d train rows, %d test rows, %d features",
        len(train),
        len(test),
        len(features),
    )
    return PreflightResult(train, test, roles, fingerprint, findings)


def _quasi_identifier_findings(
    cfg: GuardConfig, train: pd.DataFrame, test: pd.DataFrame
) -> list[RawFinding]:
    cols = cfg.privacy.quasi_identifier_columns
    if not cols:
        return []
    sizes = pd.concat([train[cols], test[cols]]).groupby(cols, dropna=False).size()
    k = cfg.privacy.min_group_size
    small = int((sizes < k).sum())
    if small == 0:
        return []
    return [
        RawFinding(
            check_id="quasi_identifier_risk",
            severity=Severity.WARNING,
            scope="dataset",
            metric=Metric(name="min_group_size", value=float(sizes.min()), threshold=float(k)),
            evidence={
                "min_group_size": int(sizes.min()),
                "k_threshold": k,
                "n_small_groups": small,
            },
            source="preflight",
            message="Kombinasi kuasi-identifier menghasilkan kelompok yang sangat kecil.",
        )
    ]


def write_clean_copies(result: PreflightResult, workdir: Path) -> tuple[Path, Path]:
    """Write PII-free copies for subprocess detectors (used from Milestone 2)."""
    workdir.mkdir(parents=True, exist_ok=True)
    tr, te = workdir / "train.parquet", workdir / "test.parquet"
    write_parquet(result.train, tr)
    write_parquet(result.test, te)
    return tr, te
