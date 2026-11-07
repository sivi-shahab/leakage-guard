"""Shared fixtures: synthetic datasets and config writer."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from make_synthetic import make_dataset  # noqa: E402

BASE: dict[str, Any] = {
    "version": 1,
    "model_id": "test-model",
    "data": {
        "train": "",
        "test": "",
        "target": "default_flag",
        "entity_col": "customer_id",
        "time_col": "application_date",
        "index_col": "application_id",
        "pii_columns": ["nik", "npwp", "nama", "no_rekening"],
    },
    "prediction": {"prediction_date_col": "application_date", "embargo_days": 30},
    "blocklist": {
        "forbidden_columns": ["kolektibilitas_akhir"],
        "suspicious_name_patterns": ["default", "kolek", "dpd", "npl"],
    },
    "gate": {"fail_on": ["CRITICAL"], "waivers_file": None},
    "detectors": {"enabled": ["builtin"]},
    "privacy": {"quasi_identifier_columns": ["kode_pos"]},
}


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("data")
    for v in ("clean", "leaky", "drift"):
        train, test = make_dataset(v)  # type: ignore[arg-type]
        train.to_parquet(d / f"{v}_train.parquet", index=False)
        test.to_parquet(d / f"{v}_test.parquet", index=False)
    return d


@pytest.fixture
def write_cfg(data_dir: Path, tmp_path: Path) -> Callable[..., Path]:
    """Write a guard.yaml for a variant; ``over`` deep-merges one level (section -> dict)."""

    def _write(variant: str = "clean", **over: Any) -> Path:
        cfg = yaml.safe_load(yaml.safe_dump(BASE))
        cfg["data"]["train"] = str(data_dir / f"{variant}_train.parquet")
        cfg["data"]["test"] = str(data_dir / f"{variant}_test.parquet")
        for k, v in over.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
        p = tmp_path / "guard.yaml"
        p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        return p

    return _write
