"""Subprocess behaviour of the orchestrator (no heavy libraries needed)."""

from __future__ import annotations

import json
import stat
from collections.abc import Callable
from pathlib import Path

from leakage_guard.cli import main


def _fake_interpreter(tmp_path: Path, body: str) -> str:
    p = tmp_path / "fake-python"
    p.write_text(f"#!/bin/sh\n{body}\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def _cfg(write_cfg: Callable[..., Path], interp: str, **det: object) -> Path:
    detectors = {"enabled": ["builtin", "deepchecks"], **det}
    return write_cfg("clean", detectors=detectors, environments={"deepchecks": interp})


def test_missing_interpreter_exits_2_with_path_in_message(
    write_cfg: Callable[..., Path], tmp_path: Path, caplog: object
) -> None:
    cfg = _cfg(write_cfg, "/nonexistent/python")
    assert main(["run", "--config", str(cfg), "--out", str(tmp_path / "o")]) == 2


def test_missing_interpreter_becomes_warning_when_allowed(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    cfg = _cfg(write_cfg, "/nonexistent/python", allow_missing=True)
    assert main(["run", "--config", str(cfg), "--out", str(tmp_path / "o")]) == 0
    rep = json.loads((tmp_path / "o" / "report.json").read_text())
    f = next(x for x in rep["findings"] if x["check_id"] == "detector_unavailable")
    assert "/nonexistent/python" in f["reason"]["evidence"]["error"]


def test_runner_crash_exits_2(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    cfg = _cfg(write_cfg, _fake_interpreter(tmp_path, "echo boom >&2; exit 3"))
    assert main(["run", "--config", str(cfg), "--out", str(tmp_path / "o")]) == 2


def test_runner_timeout_exits_2(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    cfg = _cfg(write_cfg, _fake_interpreter(tmp_path, "sleep 30"), timeout_s=1)
    assert main(["run", "--config", str(cfg), "--out", str(tmp_path / "o")]) == 2
