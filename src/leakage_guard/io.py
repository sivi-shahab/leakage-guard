"""Table I/O. Only local files; remote URIs are rejected (no network at runtime)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from leakage_guard.models import PreflightError


def read_table(path: str | Path) -> pd.DataFrame:
    """Read parquet, csv, or feather from a local path."""
    p = Path(path)
    if "://" in str(path):
        raise PreflightError(f"remote URI not supported (no network at runtime): {path}")
    if not p.is_file():
        raise PreflightError(f"data file not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(p)
    if suffix == ".csv":
        return pd.read_csv(p)
    if suffix in {".feather", ".arrow"}:
        return pd.read_feather(p)
    raise PreflightError(f"unsupported data format: {suffix}")


def write_parquet(df: pd.DataFrame, path: str | Path) -> None:
    df.to_parquet(path, index=False)
