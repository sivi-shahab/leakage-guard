"""guard.yaml parsing and validation (docs/SPEC.md section 8)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from leakage_guard.models import ConfigError, Severity, ThresholdBasis


class _Cfg(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Band(_Cfg):
    warn: float
    crit: float

    @model_validator(mode="after")
    def _ordered(self) -> Band:
        if self.warn > self.crit:
            raise ValueError("warn must be <= crit")
        return self


class PctBand(_Cfg):
    warn_pct: float
    crit_pct: float

    @model_validator(mode="after")
    def _ordered(self) -> PctBand:
        if self.warn_pct > self.crit_pct:
            raise ValueError("warn_pct must be <= crit_pct")
        return self


class DataCfg(_Cfg):
    train: str
    test: str
    target: str
    entity_col: str | None = None
    time_col: str | None = None
    index_col: str | None = None
    pii_columns: list[str] = Field(default_factory=list)


class PredictionCfg(_Cfg):
    prediction_date_col: str | None = None
    embargo_days: int = Field(default=0, ge=0)
    maturity_window_days: int = Field(default=0, ge=0)


class BlocklistCfg(_Cfg):
    forbidden_columns: list[str] = Field(default_factory=list)
    suspicious_name_patterns: list[str] = Field(default_factory=list)


class ThresholdsCfg(_Cfg):
    row_overlap: PctBand = PctBand(warn_pct=0.0, crit_pct=1.0)
    temporal: PctBand = PctBand(warn_pct=0.0, crit_pct=5.0)
    single_feature: Band = Band(warn=0.85, crit=0.95)
    pps: Band = Band(warn=0.5, crit=0.8)
    identifier_label: Band = Band(warn=0.1, crit=0.2)
    adversarial: Band = Band(warn=0.70, crit=0.95)
    # Design default, not calibrated: CV score gap, leaky-variant minus correct pipeline.
    pipeline_gap: Band = Band(warn=0.02, crit=0.05)
    near_dup_cross_split: PctBand = PctBand(warn_pct=0.0, crit_pct=1.0)
    # Cleanlab near-duplicate threshold (Cleanlab default, not calibrated; DECISIONS D9).
    near_dup_threshold: float = Field(default=0.13, gt=0)


class RuntimeCfg(_Cfg):
    max_rows: int = Field(default=100_000, gt=0)
    seed: int = 42


class GateCfg(_Cfg):
    fail_on: list[Severity] = Field(default_factory=lambda: [Severity.CRITICAL])
    waivers_file: str | None = None


class ReportCfg(_Cfg):
    # TODO(owner): bahasa Inggris untuk audit eksternal (SPEC 16 no. 6) belum diimplementasikan.
    language: Literal["id"] = "id"
    require_owner_assessment: bool = True
    attach_html: bool = True


class EnvironmentsCfg(_Cfg):
    builtin: str | None = None
    deepchecks: str | None = None
    ppscore: str | None = None
    cleanlab: str | None = None


class DetectorsCfg(_Cfg):
    enabled: list[str] = Field(default_factory=lambda: ["builtin"])
    allow_missing: bool = False
    timeout_s: int = Field(default=1800, gt=0)


class PrivacyCfg(_Cfg):
    quasi_identifier_columns: list[str] = Field(default_factory=list)
    # Ambang k-anonimitas (usulan; belum dikalibrasi). TODO(owner): konfirmasi bersama kepatuhan.
    min_group_size: int = Field(default=5, ge=1)


class GuardConfig(_Cfg):
    version: int = 1
    model_id: str
    data: DataCfg
    prediction: PredictionCfg = Field(default_factory=PredictionCfg)
    blocklist: BlocklistCfg = Field(default_factory=BlocklistCfg)
    thresholds: ThresholdsCfg = Field(default_factory=ThresholdsCfg)
    thresholds_basis: dict[str, ThresholdBasis] = Field(default_factory=dict)
    runtime: RuntimeCfg = Field(default_factory=RuntimeCfg)
    gate: GateCfg = Field(default_factory=GateCfg)
    report: ReportCfg = Field(default_factory=ReportCfg)
    environments: EnvironmentsCfg = Field(default_factory=EnvironmentsCfg)
    detectors: DetectorsCfg = Field(default_factory=DetectorsCfg)
    privacy: PrivacyCfg = Field(default_factory=PrivacyCfg)

    def config_hash(self) -> str:
        """Stable hash of the full config (including defaults)."""
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def load_config(path: Path) -> GuardConfig:
    """Load and validate ``guard.yaml``; errors name the offending field path."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    try:
        return GuardConfig.model_validate(raw)
    except ValidationError as exc:
        msgs = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise ConfigError(f"invalid config {path}: " + "; ".join(msgs)) from exc
