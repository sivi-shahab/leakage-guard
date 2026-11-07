"""Unit tests for config, preflight, reasons, aggregator, waivers, gate, CLI."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from leakage_guard.aggregator import aggregate
from leakage_guard.cli import main
from leakage_guard.config import load_config
from leakage_guard.detectors.base import DetectorContext
from leakage_guard.detectors.builtin import BuiltinDetector
from leakage_guard.gate import exit_code
from leakage_guard.models import (
    ConfigError,
    Metric,
    PreflightError,
    RawFinding,
    ReasonError,
    Severity,
    Waiver,
)
from leakage_guard.preflight import run_preflight
from leakage_guard.reasons.catalog import CATALOG, LEAKAGE_TYPE, THRESHOLD_BASIS
from leakage_guard.reasons.engine import render, validate_catalog
from leakage_guard.waivers import is_active, load_waivers


def test_config_rejects_warn_above_crit(write_cfg: Callable[..., Path]) -> None:
    p = write_cfg("clean", thresholds={"single_feature": {"warn": 0.9, "crit": 0.8}})
    with pytest.raises(ConfigError, match=r"thresholds\.single_feature"):
        load_config(p)


def test_config_rejects_negative_embargo_unknown_key_and_language(
    write_cfg: Callable[..., Path],
) -> None:
    for over in (
        {"prediction": {"embargo_days": -1}},
        {"bogus": 1},
        {"report": {"language": "en"}},
    ):
        with pytest.raises(ConfigError):
            load_config(write_cfg("clean", **over))


def test_preflight_drops_pii_and_hashes_role_pii(write_cfg: Callable[..., Path]) -> None:
    cfg = load_config(
        write_cfg(
            "clean", data={"pii_columns": ["nik", "npwp", "nama", "no_rekening", "customer_id"]}
        )
    )
    pre = run_preflight(cfg, Path("."))
    assert not {"nik", "npwp", "nama", "no_rekening"} & set(pre.train.columns)
    assert pre.train["customer_id"].str.len().eq(16).all()  # pseudonymised, still a role column
    assert "customer_id" not in pre.roles.features


def test_preflight_errors(write_cfg: Callable[..., Path], tmp_path: Path) -> None:
    with pytest.raises(PreflightError, match="not found"):
        run_preflight(load_config(write_cfg("clean", data={"entity_col": "nope"})), Path("."))
    tr = pd.DataFrame({"a": [1, 2], "default_flag": [0, 0]})
    tr.to_csv(tmp_path / "t.csv", index=False)
    cfg = load_config(
        write_cfg(
            "clean",
            data={
                "train": str(tmp_path / "t.csv"),
                "test": str(tmp_path / "t.csv"),
                "entity_col": None,
                "time_col": None,
                "index_col": None,
            },
            prediction={"prediction_date_col": None},
            privacy={"quasi_identifier_columns": []},
        )
    )
    with pytest.raises(PreflightError, match="fewer than two classes"):
        run_preflight(cfg, Path("."))


def test_preflight_quasi_identifier_warning(write_cfg: Callable[..., Path]) -> None:
    cfg = load_config(
        write_cfg("clean", privacy={"quasi_identifier_columns": ["kode_pos", "tenure"]})
    )
    pre = run_preflight(cfg, Path("."))
    assert [f.check_id for f in pre.findings] == ["quasi_identifier_risk"]


def test_catalog_is_consistent() -> None:
    validate_catalog()
    assert set(CATALOG) == set(THRESHOLD_BASIS) == set(LEAKAGE_TYPE)


def test_render_is_safe_and_strict() -> None:
    assert render("{a:.2f}", {"a": 1.234}) == "1.23"
    assert render("{a}", {"a": None}) == "n/a"
    assert render("{a.__class__}", {"a": 1}) == "{a.__class__}"  # attribute access never evaluated
    with pytest.raises(ReasonError):
        render("{missing}", {})


def test_builtin_contract_evidence_covers_templates(write_cfg: Callable[..., Path]) -> None:
    cfg = load_config(write_cfg("leaky"))
    pre = run_preflight(cfg, Path("."))
    raws = BuiltinDetector().run(DetectorContext(pre.train, pre.test, pre.roles, cfg))
    assert raws
    for r in raws:
        RawFinding.model_validate(r.model_dump())
        assert CATALOG[r.check_id].evidence_keys <= r.evidence.keys(), r.check_id
        assert r.threshold_basis == THRESHOLD_BASIS[r.check_id]


def test_aggregator_merges_sources_and_raises_confidence(write_cfg: Callable[..., Path]) -> None:
    cfg = load_config(write_cfg("clean"))
    ev = {"score": 1.0, "next_best_score": 0.5}
    mk = lambda src, sev: RawFinding(  # noqa: E731
        check_id="single_feature",
        severity=sev,
        scope="feature",
        column="x",
        metric=Metric(name="cv_roc_auc", value=1.0, threshold=0.95),
        evidence=dict(ev),
        source=src,
        message="m",
    )
    out = aggregate(
        [mk("builtin", Severity.WARNING), mk("deepchecks", Severity.CRITICAL)],
        cfg,
        [],
        date(2026, 1, 1),
    )
    assert len(out) == 1
    f = out[0]
    assert f.sources == ["builtin", "deepchecks"] and f.severity is Severity.CRITICAL
    assert f.reason.confidence == "high"


def test_orphan_waiver_reported_as_info(write_cfg: Callable[..., Path]) -> None:
    cfg = load_config(write_cfg("clean"))
    w = Waiver(
        finding_id="group_overlap:x",
        owner="o",
        approved_by="a",
        reason="r",
        expires=date(2999, 1, 1),
    )
    out = aggregate([], cfg, [w], date(2026, 1, 1))
    assert [(f.check_id, f.severity) for f in out] == [("orphan_waiver", Severity.INFO)]


def test_waiver_expiry_boundary_and_validation(tmp_path: Path) -> None:
    w = Waiver(finding_id="a:b", owner="o", approved_by="a", reason="r", expires=date(2026, 2, 28))
    assert is_active(w, date(2026, 2, 28)) and not is_active(w, date(2026, 3, 1))
    p = tmp_path / "w.yaml"
    p.write_text(yaml.safe_dump({"waivers": [{"finding_id": "a:b", "owner": "o"}]}))
    with pytest.raises(ConfigError):
        load_waivers(p)
    assert load_waivers(None) == []
    with pytest.raises(ConfigError):
        load_waivers(tmp_path / "missing.yaml")


def test_gate_fail_on(write_cfg: Callable[..., Path]) -> None:
    cfg = load_config(write_cfg("clean"))
    raw = RawFinding(
        check_id="suspicious_names",
        severity=Severity.WARNING,
        scope="feature",
        column="dpd_x",
        evidence={"matched_pattern": "dpd"},
        source="builtin",
        message="m",
    )
    fs = aggregate([raw], cfg, [], date(2026, 1, 1))
    assert exit_code(fs, [Severity.CRITICAL]) == 0
    assert exit_code(fs, [Severity.CRITICAL, Severity.WARNING]) == 1


def test_cli_validate_explain_version(
    write_cfg: Callable[..., Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write_cfg("leaky")
    assert main(["validate-config", "--config", str(p)]) == 0
    assert main(["validate-config", "--config", str(tmp_path / "nope.yaml")]) == 2
    out = tmp_path / "o"
    assert main(["run", "--config", str(p), "--out", str(out)]) == 1
    capsys.readouterr()
    assert (
        main(["explain", "--report", str(out / "report.json"), "--finding-id", "row_overlap:row"])
        == 0
    )
    assert "why_leakage" in json.loads(capsys.readouterr().out)
    assert main(["explain", "--report", str(out / "report.json"), "--finding-id", "nope"]) == 2
    assert main(["version"]) == 0


def test_missing_detector_follows_allow_missing(
    write_cfg: Callable[..., Path], tmp_path: Path
) -> None:
    strict = write_cfg(
        "clean", detectors={"enabled": ["builtin", "deepchecks"], "allow_missing": False}
    )
    assert main(["run", "--config", str(strict), "--out", str(tmp_path / "s")]) == 2
    lax = write_cfg(
        "clean", detectors={"enabled": ["builtin", "deepchecks"], "allow_missing": True}
    )
    assert main(["run", "--config", str(lax), "--out", str(tmp_path / "l")]) == 0
    rep = json.loads((tmp_path / "l" / "report.json").read_text())
    assert "detector_unavailable:deepchecks" in {f["finding_id"] for f in rep["findings"]}
