"""Acceptance criteria AC-1..AC-10 (docs/SPEC.md section 12) that apply to Milestone 1."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from leakage_guard.cli import main
from leakage_guard.config import load_config
from leakage_guard.detectors.base import REGISTRY, DetectorContext
from leakage_guard.models import RawFinding, Severity
from leakage_guard.orchestrator import run_guard

CRIT_LEAKY = {
    "blocklist_hit:kolektibilitas_akhir",
    "group_overlap:customer_id",
    "row_overlap:row",
    "single_feature:kolektibilitas_akhir",
    "temporal:application_date",
}


def _run(cfg: Path, out: Path) -> tuple[int, dict[str, Any]]:
    code = main(["run", "--config", str(cfg), "--out", str(out)])
    return code, json.loads((out / "report.json").read_text(encoding="utf-8"))


def test_ac1_leaky_detects_l1_to_l4_and_blocks(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    """AC-1 (partial): L1-L4 detected, exit 1. L5 needs Deepchecks/ppscore (Milestone 2)."""
    code, rep = _run(write_cfg("leaky"), tmp_path / "o")
    assert code == 1 and rep["gate"] == "FAILED"
    crit = {f["finding_id"] for f in rep["findings"] if f["severity"] == "CRITICAL"}
    assert crit >= CRIT_LEAKY
    types = {f["leakage_type"] for f in rep["findings"]}
    assert {"L1", "L2", "L3", "L4"} <= types


def test_ac1_drift_detects_l7(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    code, rep = _run(write_cfg("drift"), tmp_path / "o")
    assert code == 1
    assert "adversarial:channel_code" in {f["finding_id"] for f in rep["findings"]}


def test_ac2_clean_passes_without_false_critical(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    code, rep = _run(write_cfg("clean"), tmp_path / "o")
    assert code == 0 and rep["gate"] == "PASSED"
    assert rep["summary"]["critical"] == 0


def test_ac3_one_finding_per_id(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    _, rep = _run(write_cfg("leaky"), tmp_path / "o")
    ids = [f["finding_id"] for f in rep["findings"]]
    assert len(ids) == len(set(ids))


def _waivers(path: Path, expires: str) -> Path:
    items = [
        {
            "finding_id": fid,
            "owner": "o@x",
            "approved_by": "a@x",
            "reason": "kaji",
            "expires": expires,
        }
        for fid in sorted(CRIT_LEAKY)
    ]
    path.write_text(yaml.safe_dump({"waivers": items}), encoding="utf-8")
    return path


def test_ac4_expired_waiver_blocks_again(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    active = _waivers(tmp_path / "w_active.yaml", "2999-01-01")
    code, rep = _run(
        write_cfg("leaky", gate={"fail_on": ["CRITICAL"], "waivers_file": str(active)}),
        tmp_path / "a",
    )
    assert code == 0 and rep["summary"]["waived"] == len(CRIT_LEAKY)
    expired = _waivers(tmp_path / "w_expired.yaml", "2000-01-01")
    code, _ = _run(
        write_cfg("leaky", gate={"fail_on": ["CRITICAL"], "waivers_file": str(expired)}),
        tmp_path / "e",
    )
    assert code == 1


def test_ac5_no_pii_in_artifacts(
    write_cfg: Callable[..., Path], tmp_path: Path, data_dir: Path
) -> None:
    import pandas as pd

    raw = pd.read_parquet(data_dir / "leaky_train.parquet")
    assert (
        raw["nik"].str.contains("PII-MARKER").all()
        and raw["kode_pos"].str.contains("POS-MARKER").all()
    )
    out = tmp_path / "o"
    _run(write_cfg("leaky"), out)
    for name in ("report.json", "report.md"):
        text = (out / name).read_text(encoding="utf-8")
        assert "PII-MARKER" not in text and "POS-MARKER" not in text


def test_ac8_finding_without_reason_exits_2(
    write_cfg: Callable[..., Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Stub:
        name = "stub"

        def run(self, ctx: DetectorContext) -> list[RawFinding]:
            return [
                RawFinding(
                    check_id="no_such_check",
                    severity=Severity.WARNING,
                    scope="dataset",
                    source="stub",
                    message="x",
                )
            ]

    monkeypatch.setitem(REGISTRY, "stub", Stub)
    cfg = write_cfg("clean", detectors={"enabled": ["stub"]})
    assert main(["run", "--config", str(cfg), "--out", str(tmp_path / "o")]) == 2


def test_ac8_every_finding_has_complete_reason(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    _, rep = _run(write_cfg("leaky"), tmp_path / "o")
    for f in rep["findings"]:
        r = f["reason"]
        assert all(
            r[k]
            for k in (
                "why_leakage",
                "evidence",
                "impact",
                "likely_root_causes",
                "remediation",
                "verification_question",
                "confidence",
            )
        )


def test_ac9_deterministic_output(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    cfg_path = write_cfg("leaky")
    cfg = load_config(cfg_path)
    when = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    for d in ("a", "b"):
        run_guard(cfg, cfg_path.parent, tmp_path / d, [], run_at=when)
    for name in ("report.json", "report.md"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_ac10_reason_names_column_and_metric(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    _, rep = _run(write_cfg("leaky"), tmp_path / "o")
    f = next(x for x in rep["findings"] if x["finding_id"] == "single_feature:kolektibilitas_akhir")
    assert "kolektibilitas_akhir" in f["reason"]["why_leakage"]
    assert f"{f['metric']['value']:.3f}" in f["reason"]["why_leakage"]
    assert f["reason"]["evidence"]["next_best_score"] < 0.9
