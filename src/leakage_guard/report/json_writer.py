"""Build and write ``report.json`` (SPEC 9.2). Output is deterministic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from leakage_guard.config import GuardConfig
from leakage_guard.models import Finding, Report, Severity


def build_report(
    findings: list[Finding],
    cfg: GuardConfig,
    fingerprint: dict[str, Any],
    run_at: str,
    tools: dict[str, str],
    exit_code: int,
) -> Report:
    open_ = [f for f in findings if not f.waived]
    summary = {
        "critical": sum(f.severity is Severity.CRITICAL for f in open_),
        "warning": sum(f.severity is Severity.WARNING for f in open_),
        "info": sum(f.severity is Severity.INFO for f in open_),
        "waived": len(findings) - len(open_),
    }
    pending = 0
    if cfg.report.require_owner_assessment:
        pending = sum(
            f.reason.owner_assessment is None and f.severity.rank >= Severity.WARNING.rank
            for f in open_
        )
    return Report(
        model_id=cfg.model_id,
        run_at=run_at,
        config_hash=cfg.config_hash(),
        data_fingerprint=fingerprint,
        tools=dict(sorted(tools.items())),
        summary=summary,
        gate="FAILED" if exit_code else "PASSED",
        owner_assessment_pending=pending,
        findings=findings,
    )


def write_json(report: Report, path: Path) -> None:
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
