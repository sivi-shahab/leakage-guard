from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from leakage_guard.config import GuardConfig
from leakage_guard.prevention.pipeline_integrity import pipeline_integrity_findings, score_gap
from leakage_guard.prevention.splits import group_split, purged_kfold, time_split


def _df() -> pd.DataFrame:
    d = pd.date_range("2024-01-01", periods=100, freq="D")
    return pd.DataFrame({"t": d, "g": np.arange(100) % 20, "v": np.arange(100)})


def test_time_split_embargo_and_maturity() -> None:
    df = _df()
    tr, te = time_split(df, "t", "2024-02-15", embargo_days=5)
    assert tr.t.max() <= pd.Timestamp("2024-02-10") and te.t.min() > pd.Timestamp("2024-02-15")
    tr, te = time_split(df, "t", "2024-02-15", maturity_window_days=30)
    assert te.t.max() <= df.t.max() - pd.Timedelta(days=30)  # immature rows dropped


def test_group_split_no_group_overlap() -> None:
    tr, te = group_split(_df(), "g", test_size=0.3, seed=1)
    assert not set(tr.g) & set(te.g) and len(tr) + len(te) == 100


def test_purged_kfold_purges_around_test_block() -> None:
    df = _df()
    folds = list(purged_kfold(df, "t", 4, embargo_days=3))
    assert len(folds) == 4
    for tr, te in folds:
        assert not set(tr) & set(te)
        lo, hi = df.t.iloc[te].min(), df.t.iloc[te].max()
        gap = pd.Timedelta(days=3)
        assert not ((df.t.iloc[tr] >= lo - gap) & (df.t.iloc[tr] <= hi + gap)).any()


def _noise() -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(0)
    return pd.DataFrame(rng.normal(size=(120, 400))), rng.integers(0, 2, 120)


def test_integrity_flags_leaky_feature_selection() -> None:
    X, y = _noise()
    pipe = Pipeline([("sel", SelectKBest(f_classif, k=10)), ("m", LogisticRegression())])
    assert score_gap(pipe, X, y) > 0.05
    f = pipeline_integrity_findings(pipe, X, y, GuardConfig.model_validate(_cfg()))
    assert f and f[0].check_id == "pipeline_integrity" and f[0].severity.value == "CRITICAL"


def test_integrity_clean_pipeline_no_finding() -> None:
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.normal(size=(300, 5)))
    y = (X[0] + rng.normal(size=300) > 0).astype(int)
    pipe = Pipeline([("s", StandardScaler()), ("m", RandomForestClassifier(random_state=0))])
    assert pipeline_integrity_findings(pipe, X, y, GuardConfig.model_validate(_cfg())) == []


def test_integrity_rejects_non_pipeline() -> None:
    X, y = _noise()
    with pytest.raises(TypeError):
        score_gap(LogisticRegression(), X, y)


def _cfg() -> dict[str, object]:
    return {"model_id": "m", "data": {"train": "a", "test": "b", "target": "y"}}
