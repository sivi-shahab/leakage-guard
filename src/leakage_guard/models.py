"""Data models shared by detectors, aggregator, and report writers."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LeakageGuardError(Exception):
    """Base class for errors that map to exit code 2."""


class ConfigError(LeakageGuardError):
    """Invalid guard.yaml or waivers file."""


class PreflightError(LeakageGuardError):
    """Input data failed validation."""


class DetectorError(LeakageGuardError):
    """A detector could not run or crashed."""


class ReasonError(LeakageGuardError):
    """A finding has no complete reason block."""


class Severity(StrEnum):
    """Finding severity, ordered INFO < WARNING < CRITICAL via ``rank``."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}

Scope = Literal["row", "entity", "time", "feature", "dataset", "pipeline"]
ThresholdBasis = Literal["deepchecks_default", "design", "calibrated"]
Confidence = Literal["high", "medium", "low"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metric(_Model):
    name: str
    value: float | None = None
    threshold: float | None = None


class RawFinding(_Model):
    """Detector output, before aggregation. Evidence must hold aggregates only (no PII)."""

    check_id: str
    severity: Severity
    scope: Scope
    column: str | None = None
    metric: Metric | None = None
    threshold_basis: ThresholdBasis = "design"
    evidence: dict[str, Any] = Field(default_factory=dict)
    source: str
    message: str


class Waiver(_Model):
    finding_id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    expires: date


class Reason(_Model):
    summary: str
    why_leakage: str
    evidence: dict[str, Any]
    impact: str
    likely_root_causes: list[str]
    remediation: list[str]
    verification_question: str
    confidence: Confidence
    owner_assessment: (
        Literal["confirmed_leakage", "legitimate_feature", "needs_investigation"] | None
    ) = None


class Finding(_Model):
    finding_id: str
    check_id: str
    leakage_type: str | None
    severity: Severity
    scope: Scope
    column: str | None
    metric: Metric | None
    threshold_basis: ThresholdBasis
    message: str
    sources: list[str]
    reason: Reason
    waived: bool = False
    waiver: Waiver | None = None


class Report(_Model):
    model_id: str
    run_at: str
    config_hash: str
    data_fingerprint: dict[str, Any]
    tools: dict[str, str]
    summary: dict[str, int]
    gate: Literal["PASSED", "FAILED"]
    owner_assessment_pending: int
    findings: list[Finding]
