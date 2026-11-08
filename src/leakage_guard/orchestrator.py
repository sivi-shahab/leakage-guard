"""Run detectors and the full gate pipeline."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, date, datetime
from importlib import metadata
from pathlib import Path

import leakage_guard.detectors.builtin  # noqa: F401  (registers the detectors; heavy libs import lazily)
import leakage_guard.detectors.cleanlab_detector  # noqa: F401
import leakage_guard.detectors.deepchecks_detector  # noqa: F401
import leakage_guard.detectors.ppscore_detector  # noqa: F401
from leakage_guard import __version__
from leakage_guard.aggregator import aggregate
from leakage_guard.config import GuardConfig
from leakage_guard.detectors.base import DetectorContext, get_detector
from leakage_guard.gate import exit_code
from leakage_guard.models import DetectorError, Metric, RawFinding, Report, Severity, Waiver
from leakage_guard.preflight import PreflightResult, run_preflight, write_clean_copies
from leakage_guard.reasons.catalog import THRESHOLD_BASIS
from leakage_guard.reasons.engine import validate_catalog
from leakage_guard.report.json_writer import build_report, write_json
from leakage_guard.report.markdown_writer import write_markdown

log = logging.getLogger(__name__)


def _run_subprocess(
    name: str,
    interpreter: str,
    cfg: GuardConfig,
    pre: PreflightResult,
    workdir: Path,
    attach_dir: Path,
) -> list[RawFinding]:
    """Run ``python -m leakage_guard.runners.<name>`` with the configured interpreter."""
    if not Path(interpreter).is_file():
        raise DetectorError(
            f"interpreter for '{name}' not found: {interpreter} "
            f"(expected the Python of its dedicated environment, set at environments.{name})"
        )
    tr, te = write_clean_copies(pre, workdir)
    run_json, out_json = workdir / f"run_{name}.json", workdir / f"findings_{name}.json"
    run_json.write_text(
        json.dumps(
            {
                "train": str(tr),
                "test": str(te),
                "roles": asdict(pre.roles),
                "config": cfg.model_dump(mode="json"),
                "attach_dir": str(attach_dir),
            }
        ),
        encoding="utf-8",
    )
    cmd = [
        interpreter,
        "-m",
        f"leakage_guard.runners.{name}",
        "--input",
        str(run_json),
        "--output",
        str(out_json),
    ]
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, interpreter from trusted config
            cmd, capture_output=True, text=True, timeout=cfg.detectors.timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise DetectorError(
            f"detector '{name}' timed out after {cfg.detectors.timeout_s}s"
        ) from exc
    try:
        payload = json.loads(out_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {"error": f"no output (exit {proc.returncode}): {proc.stderr[-300:].strip()}"}
    if proc.returncode != 0 or "error" in payload:
        raise DetectorError(f"detector '{name}' failed: {payload.get('error', proc.stderr[-300:])}")
    return [RawFinding.model_validate(f) for f in payload["findings"]]


def _run_one(name: str, cfg: GuardConfig, pre: PreflightResult, workdir: Path) -> list[RawFinding]:
    sub = workdir / name
    attach = sub / "attachments"
    interpreter = getattr(cfg.environments, name, None)
    if interpreter is not None:
        sub.mkdir(parents=True, exist_ok=True)
        return _run_subprocess(name, interpreter, cfg, pre, sub, attach)
    return get_detector(name).run(
        DetectorContext(pre.train, pre.test, pre.roles, cfg, attach_dir=attach)
    )


def run_detectors(cfg: GuardConfig, pre: PreflightResult, workdir: Path) -> list[RawFinding]:
    """Run enabled detectors in parallel; failures follow ``detectors.allow_missing``."""
    names = cfg.detectors.enabled
    out: list[RawFinding] = list(pre.findings)
    with ThreadPoolExecutor(max_workers=max(1, len(names))) as pool:
        futures = {n: pool.submit(_run_one, n, cfg, pre, workdir) for n in names}
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
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="leakage-guard-") as tmp:
        raws = run_detectors(cfg, pre, Path(tmp))
        if cfg.report.attach_html:
            for html in sorted(Path(tmp).glob("*/attachments/*.html")):
                shutil.copy(html, out_dir / html.name)
    findings = aggregate(raws, cfg, waivers, today)
    code = exit_code(findings, cfg.gate.fail_on)
    report = build_report(
        findings, cfg, pre.fingerprint, run_at.strftime("%Y-%m-%dT%H:%M:%SZ"), _tools(), code
    )
    write_json(report, out_dir / "report.json")
    write_markdown(report, out_dir / "report.md")
    return report, code
