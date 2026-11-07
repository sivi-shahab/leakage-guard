"""Waiver loading and expiry (SPEC 8)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from leakage_guard.models import ConfigError, Waiver


class _File(BaseModel):
    model_config = ConfigDict(extra="forbid")
    waivers: list[Waiver] = []


def load_waivers(path: Path | None) -> list[Waiver]:
    """Load ``waivers.yaml``. ``None`` means no waivers; a missing file is an error."""
    if path is None:
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read waivers {path}: {exc}") from exc
    try:
        return _File.model_validate(raw).waivers
    except ValidationError as exc:
        msgs = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise ConfigError(f"invalid waivers {path}: " + "; ".join(msgs)) from exc


def is_active(w: Waiver, today: date) -> bool:
    """A waiver is valid through its ``expires`` date inclusive."""
    return w.expires >= today
