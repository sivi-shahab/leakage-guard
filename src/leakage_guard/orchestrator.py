"""Run detectors and the full gate pipeline."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from importlib import metadata
from pathlib import Path

import leakage_guard.detectors.builtin  # noqa: F401  (registers the builtin detector)
from leakage_guard import __version__
from leakage_guard.aggregator import aggregate
from leakage_guard.config import GuardConfig
from leakage_guard.detectors.base import DetectorContext, get_detector
from leakage_guard.gate import exit_code
from leakage_guard.models import DetectorError, Metric, RawFinding, Report, Severity, Waiver
from leakage_guard.preflight import PreflightResult, run_preflight
from leakage_guard.reasons.catalog import THRESHOLD_BASIS
from leakage_guard.reasons.engine import validate_catalog
from leakage_guard.report.json_writer import build_report, write_json
from leakage_guard.report.markdown_writer import write_markdown

log = logging.getLogger(__name__)


def _run_one(name: str, cfg: GuardConfig, pre: PreflightResult) -> list[RawFinding]:
    interpreter = getattr(cfg.environments, name, None)
    if interpreter is not None:
        # TODO(Milestone 2): subprocess runners with a per-detector interpreter.
        raise DetectorError(
            f"subprocess execution for '{name}' ({interpreter}) is not implemented yet"
        )
    det = get_detector(name)
    ctx = DetectorContext(pre.train, pre.test, pre.roles, cfg)
    return det.run(ctx)


def run_detectors(cfg: GuardConfig, pre: PreflightResult) -> list[RawFinding]:
    """Run enabled detectors in parallel; failures follow ``detectors.allow_missing``."""
    names = cfg.detectors.enabled
    out: list[RawFinding] = list(pre.findings)
    with ThreadPoolExecutor(max_workers=max(1, len(names))) as pool:
        futures = {n: pool.submit(_run_one, n, cfg, pre) for n in names}
    for name, fut in futures.items():
        try:
            out += fut.result()
        except DetectorError as exc:
            if not cfg.detectors.allow_missing:
                raise
            log.warning("detector %s unavailable: %s", name, exc)
            out.append(
                RawFinding(
                    check_id="detector_unavailable",
                    severity=Severity.WARNING,
                    scope="dataset",
                    column=name,
                    metric=Metric(name="available", value=0.0, threshold=1.0),
                    threshold_basis=THRESHOLD_BASIS["detector_unavailable"],
                    evidence={"detector": name, "error": str(exc)},
                    source="orchestrator",
                    message=f"Detektor {name} tidak tersedia.",
                )
            )
        except Exception as exc:  # noqa: BLE001 - any detector crash must fail closed
            raise DetectorError(f"detector '{name}' crashed: {type(exc).__name__}: {exc}") from exc
    return out


def _tools() -> dict[str, str]:
    tools = {"leakage-guard": __version__}
    for pkg in ("scikit-learn", "pandas", "numpy"):
        tools[pkg] = metadata.version(pkg)
    return tools


def run_guard(
    cfg: GuardConfig,
    base_dir: Path,
    out_dir: Path,
    waivers: list[Waiver],
    *,
    run_at: datetime | None = None,
    today: date | None = None,
) -> tuple[Report, int]:
    """Preflight, detect, aggregate, gate, and write reports.

    Raises LeakageGuardError on failure.
    """
    validate_catalog()
    run_at = run_at or datetime.now(UTC)
    today = today or run_at.date()
    pre = run_preflight(cfg, base_dir)
    findings = aggregate(run_detectors(cfg, pre), cfg, waivers, today)
    code = exit_code(findings, cfg.gate.fail_on)
    report = build_report(
        findings, cfg, pre.fingerprint, run_at.strftime("%Y-%m-%dT%H:%M:%SZ"), _tools(), code
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, out_dir / "report.json")
    write_markdown(report, out_dir / "report.md")
    return report, code
