"""Deepchecks detector. Run inside the Deepchecks environment: ``pytest -m deepchecks``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("deepchecks")
from helpers import assert_contract, ids, run_detector  # noqa: E402

pytestmark = pytest.mark.deepchecks


def test_leaky_detects_l1_to_l5_with_two_datasets(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    f = run_detector(write_cfg, "deepchecks", "leaky", attach=tmp_path / "att")
    assert_contract(f, "deepchecks")
    crit = ids(f, "CRITICAL")
    # L2 needs index_name=customer_id; L5 needs index_name=application_id (two Datasets).
    assert "group_overlap:customer_id" in crit
    assert "identifier_label:application_id" in crit
    assert {
        "row_overlap:row",
        "temporal:application_date",
        "pps_train:kolektibilitas_akhir",
    } <= crit
    assert sorted(p.name for p in (tmp_path / "att").glob("*.html")) == [
        "deepchecks_entity_time.html",
        "deepchecks_samples_features.html",
    ]


def test_clean_has_no_critical(write_cfg: Callable[..., Path]) -> None:
    f = run_detector(write_cfg, "deepchecks", "clean")
    assert_contract(f, "deepchecks")
    assert not ids(f, "CRITICAL")


def test_html_has_no_pii_or_quasi_identifier_values(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    run_detector(write_cfg, "deepchecks", "leaky", attach=tmp_path / "att")
    for html in (tmp_path / "att").glob("*.html"):
        text = html.read_text(encoding="utf-8")
        assert "PII-MARKER" not in text and "POS-MARKER" not in text


def test_no_html_when_disabled(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    run_detector(
        write_cfg, "deepchecks", "clean", attach=tmp_path / "att", report={"attach_html": False}
    )
    att = tmp_path / "att"
    assert not att.exists() or not list(att.glob("*.html"))
