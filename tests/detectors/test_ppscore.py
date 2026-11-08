"""ppscore detector. Run inside the Deepchecks environment: ``pytest -m ppscore``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("ppscore")
from helpers import assert_contract, ids, run_detector  # noqa: E402

pytestmark = pytest.mark.ppscore


def test_leaky_flags_leaking_feature_and_id(write_cfg: Callable[..., Path]) -> None:
    f = run_detector(write_cfg, "ppscore", "leaky")
    assert_contract(f, "ppscore")
    crit = ids(f, "CRITICAL")
    assert "pps_train:kolektibilitas_akhir" in crit and "identifier_label:application_id" in crit
    top = next(x for x in f if x.check_id == "pps_train" and x.column == "kolektibilitas_akhir")
    assert top.evidence["pps_train"] > 0.9


def test_clean_has_no_critical(write_cfg: Callable[..., Path]) -> None:
    f = run_detector(write_cfg, "ppscore", "clean")
    assert_contract(f, "ppscore")
    assert not ids(f, "CRITICAL")


def test_string_id_is_reported_as_blind_spot(
    write_cfg: Callable[..., Path], data_dir: Path
) -> None:
    import pandas as pd

    for split in ("train", "test"):
        df = pd.read_parquet(data_dir / f"leaky_{split}.parquet")
        df["application_id"] = "APP-" + df["application_id"].astype(str)
        df.to_parquet(data_dir / f"leaky_str_{split}.parquet", index=False)
    f = run_detector(
        write_cfg,
        "ppscore",
        "leaky",
        data={
            "train": str(data_dir / "leaky_str_train.parquet"),
            "test": str(data_dir / "leaky_str_test.parquet"),
        },
    )
    assert_contract(f, "ppscore")
    assert "pps_blind_spot:application_id" in ids(f, "INFO")
    assert "identifier_label:application_id" not in ids(f)
