"""Synthetic credit-scoring datasets with deliberate leakage.

Variants:
    clean : time + entity split, no leakage.
    leaky : random row split plus planted L1/L2/L3/L4 (and an ID correlated with the target for L5).
    drift : clean split but one feature shifted in test (L7).

All identifying values are synthetic markers (``PII-MARKER-*``, ``POS-MARKER-*``) so tests can
assert they never appear in any report artifact.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

Variant = Literal["clean", "leaky", "drift"]

PII_COLUMNS = ["nik", "npwp", "nama", "no_rekening"]
QUASI_COLUMN = "kode_pos"


def _population(n_customers: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2024-01-01") + pd.to_timedelta(
        rng.integers(0, 640, n_customers), unit="D"
    )
    rows = []
    for cid in range(n_customers):
        for _ in range(int(rng.integers(1, 4))):
            rows.append((cid, start[cid] + pd.Timedelta(days=int(rng.integers(0, 14)))))
    df = pd.DataFrame(rows, columns=["customer_id", "application_date"])
    n = len(df)
    income = rng.normal(0, 1, n)
    debt = rng.normal(0, 1, n)
    age = rng.normal(0, 1, n)
    logit = -1.6 - 0.5 * income + 0.5 * debt + 0.2 * age
    df["income"] = income
    df["debt_ratio"] = debt
    df["age"] = age
    df["tenure"] = rng.integers(0, 120, n)
    df["channel_code"] = rng.uniform(0, 10, n)
    df[QUASI_COLUMN] = [f"POS-MARKER-{v:03d}" for v in rng.integers(0, 40, n)]
    df["default_flag"] = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(int)
    df["application_id"] = rng.permutation(n) + 100000
    for col in PII_COLUMNS:
        df[col] = [f"PII-MARKER-{col}-{i}" for i in range(n)]
    return df


def make_dataset(
    variant: Variant, n_customers: int = 2400, seed: int = 7
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train, test) for the requested variant."""
    df = _population(n_customers, seed)
    rng = np.random.default_rng(seed + 1)
    if variant in ("clean", "drift"):
        first = df.groupby("customer_id")["application_date"].transform("min")
        train = df[first < pd.Timestamp("2025-05-01")].copy()
        test = df[first >= pd.Timestamp("2025-07-01")].copy()
        if variant == "drift":
            test["channel_code"] = test["channel_code"] + 9.0
        return train.reset_index(drop=True), test.reset_index(drop=True)

    # leaky
    df["kolektibilitas_akhir"] = 1 + 3 * df["default_flag"]  # post-outcome feature (L4)
    # L5: application_id ordered by outcome (sequential IDs encode the target)
    order = np.argsort(df["default_flag"].to_numpy() + rng.uniform(0, 0.4, len(df)))
    df["application_id"] = np.empty(len(df), dtype=int)
    df.loc[df.index[order], "application_id"] = np.arange(len(df)) + 100000
    mask = rng.uniform(size=len(df)) < 0.8  # random row split: L2 + L3
    train, test = df[mask].copy(), df[~mask].copy()
    dup = train.sample(frac=0.05, random_state=seed)  # L1
    test = pd.concat([test, dup], ignore_index=True)
    return train.reset_index(drop=True), test


def main(out: str = "examples/data") -> None:
    path = Path(out)
    path.mkdir(parents=True, exist_ok=True)
    for variant in ("clean", "leaky", "drift"):
        train, test = make_dataset(variant)  # type: ignore[arg-type]
        train.to_parquet(path / f"{variant}_train.parquet", index=False)
        test.to_parquet(path / f"{variant}_test.parquet", index=False)


if __name__ == "__main__":
    main(*sys.argv[1:2])
