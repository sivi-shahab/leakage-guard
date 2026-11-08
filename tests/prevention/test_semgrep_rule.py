"""Semgrep rule ml-fit-before-split: positives flagged, negatives (correct usage) not."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SEMGREP = ROOT / ".envs" / "sg" / "bin" / "semgrep"
pytestmark = pytest.mark.skipif(not SEMGREP.exists(), reason="semgrep env .envs/sg not available")


def _hits(*targets: Path) -> list[int]:
    out = subprocess.run(  # noqa: S603 - fixed local semgrep binary
        [
            str(SEMGREP),
            "scan",
            "--metrics=off",
            "--disable-version-check",
            "--json",
            "-q",
            "--no-git-ignore",
            "--config",
            str(ROOT / "rules/semgrep"),
            *map(str, targets),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return [r["start"]["line"] for r in json.loads(out.stdout)["results"]]


def test_positive_examples_flagged() -> None:
    assert _hits(ROOT / "tests/semgrep/positive.py") == [8, 16, 23]


def test_negative_examples_not_flagged() -> None:
    assert _hits(ROOT / "tests/semgrep/negative.py") == []


def test_no_false_positive_on_own_code() -> None:
    # explicit file list: directory scans walk the whole enclosing git repo and take minutes
    files = [*(ROOT / "src").rglob("*.py"), *(ROOT / "examples").glob("*.py")]
    assert files and _hits(*files) == []
