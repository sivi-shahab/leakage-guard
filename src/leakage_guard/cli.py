"""Command line interface. Exit codes: 0 pass, 1 blocked, 2 runtime error.

argparse is used (stdlib, four small commands, no extra dependency).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from leakage_guard import __version__
from leakage_guard.config import GuardConfig, load_config
from leakage_guard.models import LeakageGuardError, Report, Severity
from leakage_guard.orchestrator import run_guard
from leakage_guard.waivers import load_waivers

log = logging.getLogger("leakage_guard")


def _load(path: Path) -> GuardConfig:
    return load_config(path)


def _waivers_path(cfg: GuardConfig, base: Path) -> Path | None:
    w = cfg.gate.waivers_file
    return None if w is None else (Path(w) if Path(w).is_absolute() else base / w)


def cmd_run(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config)
    cfg = _load(cfg_path)
    if args.fail_on:
        cfg.gate.fail_on = [Severity(s) for s in args.fail_on.split(",")]
    if args.no_html:
        cfg.report.attach_html = False
    base = cfg_path.parent
    waivers = load_waivers(_waivers_path(cfg, base))
    report, code = run_guard(cfg, base, Path(args.out), waivers)
    s = report.summary
    print(
        f"gate={report.gate} critical={s['critical']} warning={s['warning']} "
        f"info={s['info']} waived={s['waived']} -> {args.out}"
    )
    return code


def cmd_validate(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config)
    cfg = _load(cfg_path)
    load_waivers(_waivers_path(cfg, cfg_path.parent))
    print("config ok")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    try:
        report = Report.model_validate(json.loads(Path(args.report).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise LeakageGuardError(f"cannot read report {args.report}: {exc}") from exc
    for f in report.findings:
        if f.finding_id == args.finding_id:
            print(f.reason.model_dump_json(indent=2))
            return 0
    raise LeakageGuardError(f"finding '{args.finding_id}' not found in {args.report}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="leakage-guard", description="ML leakage quality gate")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the gate")
    r.add_argument("--config", required=True)
    r.add_argument("--out", default="leakage-guard-out")
    r.add_argument("--fail-on", default=None, help="comma separated, e.g. CRITICAL,WARNING")
    r.add_argument("--no-html", action="store_true")
    r.set_defaults(func=cmd_run)
    v = sub.add_parser("validate-config", help="validate guard.yaml")
    v.add_argument("--config", required=True)
    v.set_defaults(func=cmd_validate)
    e = sub.add_parser("explain", help="print the reason block of one finding")
    e.add_argument("--report", required=True)
    e.add_argument("--finding-id", required=True)
    e.set_defaults(func=cmd_explain)
    ver = sub.add_parser("version", help="print version")
    ver.set_defaults(func=lambda _a: print(__version__) or 0)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr
    )
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except LeakageGuardError as exc:
        log.error("%s", exc)
        return 2
    except Exception:  # noqa: BLE001 - fail closed: an unexpected crash is never a pass
        log.exception("unexpected error")
        return 2


if __name__ == "__main__":
    sys.exit(main())
