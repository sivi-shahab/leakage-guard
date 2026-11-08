"""Benchmark (AC-7): time a full run on ~N synthetic rows. Not part of default CI.

    .venv/bin/python benchmarks/run_benchmark.py --rows 1000000 --work lg-bench
Prints JSON with wall-clock seconds for the whole run and rows actually generated.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

from make_synthetic import make_dataset  # noqa: E402

from leakage_guard.cli import main  # noqa: E402


def run(rows: int, work: Path, variant: str = "leaky") -> dict[str, object]:
    work.mkdir(parents=True, exist_ok=True)
    probe_tr, probe_te = make_dataset(variant, n_customers=2400)  # type: ignore[arg-type]
    per_customer = (len(probe_tr) + len(probe_te)) / 2400
    train, test = make_dataset(variant, n_customers=int(rows / per_customer))  # type: ignore[arg-type]
    train.to_parquet(work / "train.parquet")
    test.to_parquet(work / "test.parquet")
    cfg = yaml.safe_load((ROOT / "examples/guard_m2.yaml").read_text())
    cfg["data"].update(train="train.parquet", test="test.parquet")
    (work / "guard.yaml").write_text(yaml.safe_dump(cfg))
    t0 = time.perf_counter()
    code = main(
        ["run", "--config", str(work / "guard.yaml"), "--out", str(work / "out"), "--no-html"]
    )
    return {
        "rows": len(train) + len(test),
        "max_rows": cfg["runtime"]["max_rows"],
        "seconds": round(time.perf_counter() - t0, 1),
        "exit_code": code,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000)
    ap.add_argument("--work", type=Path, default=Path("lg-bench"))
    a = ap.parse_args()
    print(json.dumps(run(a.rows, a.work)))
