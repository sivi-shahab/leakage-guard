"""Shared runner logic. A runner only reads ``run.json`` and writes ``findings.json``."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from leakage_guard.config import GuardConfig
from leakage_guard.detectors.base import DetectorContext, get_detector
from leakage_guard.io import read_table
from leakage_guard.preflight import Roles

_MODULES = {
    "builtin": "builtin",
    "deepchecks": "deepchecks_detector",
    "ppscore": "ppscore_detector",
    "cleanlab": "cleanlab_detector",
}


def main(name: str, argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog=f"leakage_guard.runners.{name}")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    out = Path(args.output)
    try:
        spec = json.loads(Path(args.input).read_text(encoding="utf-8"))
        importlib.import_module(f"leakage_guard.detectors.{_MODULES[name]}")
        ctx = DetectorContext(
            train=read_table(spec["train"]),
            test=read_table(spec["test"]),
            roles=Roles(**spec["roles"]),
            config=GuardConfig.model_validate(spec["config"]),
            attach_dir=Path(spec["attach_dir"]) if spec.get("attach_dir") else None,
        )
        findings = get_detector(name).run(ctx)
        out.write_text(json.dumps({"findings": [f.model_dump(mode="json") for f in findings]}))
        return 0
    except Exception as exc:  # noqa: BLE001 - report any crash to the parent as structured error
        out.write_text(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        print(f"runner {name} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
