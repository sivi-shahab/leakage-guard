"""Time- and group-based splits with embargo and maturity window.

All durations are in DAYS. If you wrap a library whose purge/embargo is in observations
(e.g. skfolio ``purged_size``), convert: observations = days * rows_per_day.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


def drop_immature(
    df: pd.DataFrame, time_col: str, as_of: pd.Timestamp, maturity_window_days: int
) -> pd.DataFrame:
    """Drop rows whose outcome is not yet observable: ``time + window > as_of``."""
    t = pd.to_datetime(df[time_col])
    return df[t + pd.Timedelta(days=maturity_window_days) <= as_of]


def time_split(
    df: pd.DataFrame,
    time_col: str,
    cutoff: pd.Timestamp | str,
    *,
    embargo_days: int = 0,
    maturity_window_days: int = 0,
    as_of: pd.Timestamp | str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train: ``time <= cutoff - embargo``. Test: ``time > cutoff``. Immature rows are dropped.

    ``as_of`` defaults to the latest timestamp in ``df`` (only used if maturity_window_days > 0).
    """
    cut = pd.Timestamp(cutoff)
    t = pd.to_datetime(df[time_col])
    if maturity_window_days > 0:
        end = pd.Timestamp(as_of) if as_of is not None else t.max()
        df = drop_immature(df, time_col, end, maturity_window_days)
        t = pd.to_datetime(df[time_col])
    train = df[t <= cut - pd.Timedelta(days=embargo_days)]
    test = df[t > cut]
    return train, test


def group_split(
    df: pd.DataFrame, group_col: str, *, test_size: float = 0.2, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Random split where no group (e.g. customer) appears on both sides."""
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    tr, te = next(gss.split(df, groups=df[group_col]))
    return df.iloc[tr], df.iloc[te]


def purged_kfold(
    df: pd.DataFrame, time_col: str, n_splits: int = 5, *, embargo_days: int = 0
) -> Iterator[tuple[npt.NDArray[np.intp], npt.NDArray[np.intp]]]:
    """Time-ordered K-fold yielding positional (train, test) indices.

    Folds are contiguous time blocks. Training rows within ``embargo_days`` before or after the
    test block are purged.
    """
    t = pd.to_datetime(df[time_col]).reset_index(drop=True)
    order = np.argsort(t.to_numpy(), kind="stable")
    emb = pd.Timedelta(days=embargo_days)
    for block in np.array_split(order, n_splits):
        lo, hi = t.iloc[block].min(), t.iloc[block].max()
        mask = (t < lo - emb) | (t > hi + emb)
        yield np.flatnonzero(mask.to_numpy()), np.sort(block)
