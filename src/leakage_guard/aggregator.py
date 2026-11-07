"""Aggregator: normalise, dedup, attach reasons, apply waivers (SPEC 4.6)."""

from __future__ import annotations

from datetime import date
from typing import Any

from leakage_guard.config import GuardConfig
from leakage_guard.models import Finding, RawFinding, Severity, Waiver
from leakage_guard.reasons.catalog import LEAKAGE_TYPE, THRESHOLD_BASIS
from leakage_guard.reasons.engine import build_reason
from leakage_guard.waivers import is_active


def finding_id(check_id: str, column: str | None, scope: str) -> str:
    return f"{check_id}:{column or scope}"


def _merge(group: list[RawFinding]) -> tuple[RawFinding, list[str], dict[str, Any]]:
    """Highest severity wins; evidence is merged without overwriting existing keys."""
    best = max(group, key=lambda r: r.severity.rank)
    sources = sorted({r.source for r in group})
    evidence: dict[str, Any] = {}
    for r in sorted(group, key=lambda r: (-r.severity.rank, r.source)):
        for k, v in r.evidence.items():
            evidence.setdefault(k, v)
    return best, sources, evidence


def aggregate(
    raws: list[RawFinding], cfg: GuardConfig, waivers: list[Waiver], today: date
) -> list[Finding]:
    """Return deduplicated findings with reason blocks, sorted by severity then id.

    Raises:
        ReasonError: a finding has no complete reason block (maps to exit code 2).
    """
    groups: dict[str, list[RawFinding]] = {}
    for r in raws:
        groups.setdefault(finding_id(r.check_id, r.column, r.scope), []).append(r)

    by_wid: dict[str, Waiver] = {w.finding_id: w for w in waivers}
    findings: list[Finding] = []
    for fid, group in groups.items():
        best, sources, evidence = _merge(group)
        basis = cfg.thresholds_basis.get(best.check_id, best.threshold_basis)
        reason = build_reason(
            best, sources, evidence, basis, cfg.data.target, cfg.prediction.prediction_date_col
        )
        w = by_wid.get(fid)
        findings.append(
            Finding(
                finding_id=fid,
                check_id=best.check_id,
                leakage_type=LEAKAGE_TYPE.get(best.check_id),
                severity=best.severity,
                scope=best.scope,
                column=best.column,
                metric=best.metric,
                threshold_basis=basis,
                message=best.message,
                sources=sources,
                reason=reason,
                waived=bool(w and is_active(w, today)),
                waiver=w,
            )
        )

    for w in waivers:
        if w.finding_id not in groups:
            findings.append(_orphan(w, cfg))

    findings.sort(key=lambda f: (-f.severity.rank, f.finding_id))
    return findings


def _orphan(w: Waiver, cfg: GuardConfig) -> Finding:
    raw = RawFinding(
        check_id="orphan_waiver",
        severity=Severity.INFO,
        scope="dataset",
        column=w.finding_id,
        threshold_basis=THRESHOLD_BASIS["orphan_waiver"],
        evidence={"waiver_finding_id": w.finding_id, "expires": w.expires.isoformat()},
        source="aggregator",
        message="Waiver tidak cocok dengan temuan apa pun.",
    )
    reason = build_reason(
        raw,
        ["aggregator"],
        raw.evidence,
        raw.threshold_basis,
        cfg.data.target,
        cfg.prediction.prediction_date_col,
    )
    return Finding(
        finding_id=finding_id(raw.check_id, raw.column, raw.scope),
        check_id=raw.check_id,
        leakage_type=None,
        severity=raw.severity,
        scope=raw.scope,
        column=raw.column,
        metric=None,
        threshold_basis=raw.threshold_basis,
        message=raw.message,
        sources=["aggregator"],
        reason=reason,
    )
