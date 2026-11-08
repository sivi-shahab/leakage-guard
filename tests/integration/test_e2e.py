"""End to end: the CLI with the three dedicated environments (AC-1, AC-2, AC-5 across detectors)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from conftest import external_python
from leakage_guard.cli import main

DC, CL = external_python("dc"), external_python("cl")
pytestmark = pytest.mark.skipif(not (DC and CL), reason="dedicated environments not available")


def _cfg(write_cfg: Callable[..., Path], variant: str) -> Path:
    return write_cfg(
        variant,
        detectors={"enabled": ["builtin", "deepchecks", "ppscore", "cleanlab"]},
        environments={"deepchecks": DC, "ppscore": DC, "cleanlab": CL},
    )


def _run(cfg: Path, out: Path) -> tuple[int, dict[str, Any]]:
    code = main(["run", "--config", str(cfg), "--out", str(out)])
    return code, json.loads((out / "report.json").read_text(encoding="utf-8"))


def test_ac1_full_leaky_detects_l1_to_l5(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    code, rep = _run(_cfg(write_cfg, "leaky"), tmp_path / "o")
    assert code == 1
    crit = {f["finding_id"]: f for f in rep["findings"] if f["severity"] == "CRITICAL"}
    assert {
        "row_overlap:row",
        "group_overlap:customer_id",
        "temporal:application_date",
        "pps_train:kolektibilitas_akhir",
        "identifier_label:application_id",
        "near_dup_cross_split:row",
    } <= crit.keys()
    assert {f["leakage_type"] for f in crit.values()} >= {"L1", "L2", "L3", "L4", "L5", "L8"}
    # independent detectors agreeing -> high confidence
    assert crit["group_overlap:customer_id"]["sources"] == ["builtin", "deepchecks"]
    assert crit["group_overlap:customer_id"]["reason"]["confidence"] == "high"


def test_ac2_clean_passes_with_all_detectors(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    code, rep = _run(_cfg(write_cfg, "clean"), tmp_path / "o")
    assert code == 0 and rep["summary"]["critical"] == 0


def test_ac5_no_pii_in_any_artifact_including_html(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    out = tmp_path / "o"
    _run(_cfg(write_cfg, "leaky"), out)
    files = [p for p in out.iterdir() if p.suffix in {".json", ".md", ".html"}]
    assert {p.name for p in files} >= {"report.json", "report.md", "deepchecks_entity_time.html"}
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "PII-MARKER" not in text and "POS-MARKER" not in text, p.name


def test_no_html_flag_skips_attachments(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    cfg = write_cfg(
        "clean",
        detectors={"enabled": ["builtin", "deepchecks"]},
        environments={"deepchecks": DC},
        report={"attach_html": False},
    )
    _run(cfg, tmp_path / "o")
    assert not list((tmp_path / "o").glob("*.html"))
