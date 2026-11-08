"""Cleanlab detector. Run inside the Cleanlab environment: ``pytest -m cleanlab``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("cleanlab")
from helpers import assert_contract, ids, run_detector  # noqa: E402

from leakage_guard.detectors.cleanlab_detector import feature_matrix  # noqa: E402

pytestmark = pytest.mark.cleanlab


def test_leaky_flags_cross_split_near_duplicates(write_cfg: Callable[..., Path]) -> None:
    f = run_detector(write_cfg, "cleanlab", "leaky")
    assert_contract(f, "cleanlab")
    assert "near_dup_cross_split:row" in ids(f, "CRITICAL")
    nd = next(x for x in f if x.check_id == "near_dup_cross_split")
    assert nd.evidence["pct_test_rows"] >= 1.0 and nd.evidence["n_sets_cross_split"] > 0


def test_clean_is_not_blocked_and_threshold_is_configurable(
    write_cfg: Callable[..., Path],
) -> None:
    # Default threshold 0.13 flags a small chance fraction on Gaussian data (< 1% of test): WARNING.
    f = run_detector(write_cfg, "cleanlab", "clean")
    assert_contract(f, "cleanlab")
    assert not ids(f, "CRITICAL")
    for x in f:
        if x.check_id == "near_dup_cross_split":
            assert x.evidence["pct_test_rows"] < 1.0
    # A tighter threshold removes the chance matches but still catches planted duplicates.
    f = run_detector(write_cfg, "cleanlab", "clean", thresholds={"near_dup_threshold": 0.01})
    assert "near_dup_cross_split:row" not in ids(f)
    f = run_detector(write_cfg, "cleanlab", "leaky", thresholds={"near_dup_threshold": 0.01})
    assert "near_dup_cross_split:row" in ids(f, "CRITICAL")


def test_mixed_numeric_and_categorical_features(
    write_cfg: Callable[..., Path], data_dir: Path
) -> None:
    df = pd.read_parquet(data_dir / "leaky_train.parquet")
    assert df["region"].dtype == object or str(df["region"].dtype).startswith("str")
    x = feature_matrix(df, ["income", "tenure", "region", "application_date"])
    assert {"income", "tenure", "application_date"} <= set(x.columns)
    assert {c for c in x.columns if c.startswith("region_")}  # one-hot columns present
    assert x.notna().all().all()
    f = run_detector(write_cfg, "cleanlab", "leaky")  # region is a feature in this run
    assert_contract(f, "cleanlab")


def test_high_cardinality_categorical_is_skipped() -> None:
    df = pd.DataFrame({"a": range(100), "cat": [f"k{i}" for i in range(100)]})
    assert list(feature_matrix(df, ["a", "cat"]).columns) == ["a"]
