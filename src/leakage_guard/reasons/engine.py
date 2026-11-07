"""Reason Engine: deterministic template rendering. No LLM, no network, no eval (SPEC 5.1)."""

from __future__ import annotations

import re
from typing import Any

from leakage_guard.models import (
    Confidence,
    RawFinding,
    Reason,
    ReasonError,
    Severity,
    ThresholdBasis,
)
from leakage_guard.reasons.catalog import BASE_KEYS, CATALOG, EXPLICIT_RULE_CHECKS

# Only plain names with an optional format spec: no attribute or index access.
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::([^{}]*))?\}")

_BASIS_TEXT: dict[ThresholdBasis, str] = {
    "design": "Ambang ini pilihan desain dan belum dikalibrasi pada data historis.",
    "deepchecks_default": (
        "Ambang kritis ini sama dengan nilai bawaan Deepchecks; "
        "ambang peringatan adalah pilihan desain."
    ),
    "calibrated": "Ambang ini sudah dikalibrasi pada model historis.",
}


def placeholders(text: str) -> set[str]:
    return {m.group(1) for m in _PLACEHOLDER.finditer(text)}


def validate_catalog() -> None:
    """Fail at startup if any template uses a placeholder with no guaranteed source."""
    for check_id, t in CATALOG.items():
        texts = [t.summary, t.why_leakage, t.impact, t.verification_question]
        texts += list(t.likely_root_causes) + list(t.remediation)
        used = set().union(*(placeholders(x) for x in texts))
        unknown = used - BASE_KEYS - t.evidence_keys
        if unknown:
            raise ReasonError(
                f"template '{check_id}' uses unguaranteed placeholders: {sorted(unknown)}"
            )


def _fmt(value: Any, spec: str | None) -> str:
    if value is None:
        return "n/a"
    try:
        return format(value, spec or "")
    except (ValueError, TypeError) as exc:
        raise ReasonError(f"cannot format {value!r} with spec '{spec}'") from exc


def render(text: str, values: dict[str, Any]) -> str:
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            raise ReasonError(f"missing evidence for placeholder '{key}'")
        return _fmt(values[key], m.group(2))

    return _PLACEHOLDER.sub(sub, text)


def confidence(check_id: str, severity: Severity, sources: list[str]) -> Confidence:
    if len(sources) >= 2 or check_id in EXPLICIT_RULE_CHECKS:
        return "high"
    return "medium" if severity is Severity.CRITICAL else "low"


def build_reason(
    f: RawFinding,
    sources: list[str],
    evidence: dict[str, Any],
    basis: ThresholdBasis,
    target: str,
    prediction_date: str | None,
) -> Reason:
    """Render the reason block for one aggregated finding; raises ReasonError if incomplete."""
    t = CATALOG.get(f.check_id)
    if t is None:
        raise ReasonError(f"no reason template registered for check_id '{f.check_id}'")
    missing = t.evidence_keys - evidence.keys()
    if missing:
        raise ReasonError(f"finding '{f.check_id}' lacks guaranteed evidence: {sorted(missing)}")
    values: dict[str, Any] = {
        **evidence,
        "column": f.column or "(seluruh dataset)",
        "target": target,
        "value": f.metric.value if f.metric else None,
        "threshold": f.metric.threshold if f.metric else None,
        "metric_name": f.metric.name if f.metric else "",
        "prediction_date": prediction_date or "titik prediksi",
    }
    why = render(t.why_leakage, values)
    if f.metric is not None:
        why += " " + _BASIS_TEXT[basis]
    out_evidence = dict(sorted(evidence.items()))
    out_evidence["detectors_agreeing"] = sorted(sources)
    reason = Reason(
        summary=render(t.summary, values),
        why_leakage=why,
        evidence=out_evidence,
        impact=render(t.impact, values),
        likely_root_causes=[render(x, values) for x in t.likely_root_causes],
        remediation=[render(x, values) for x in t.remediation],
        verification_question=render(t.verification_question, values),
        confidence=confidence(f.check_id, f.severity, sources),
    )
    _require_complete(reason, f.check_id)
    return reason


def _require_complete(r: Reason, check_id: str) -> None:
    empty = [
        name
        for name in ("summary", "why_leakage", "impact", "verification_question")
        if not getattr(r, name).strip()
    ]
    if not r.likely_root_causes:
        empty.append("likely_root_causes")
    if not r.remediation:
        empty.append("remediation")
    if not r.evidence:
        empty.append("evidence")
    if empty:
        raise ReasonError(f"reason for '{check_id}' is incomplete: {empty}")
