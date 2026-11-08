# CI/CD and Docker

## CI/CD integration

The gate is a plain command with an exit code.

```yaml
# GitHub Actions step (example)
- name: Leakage gate
  run: |
    .venv/bin/leakage-guard run --config guard.yaml --out leakage-guard-out
- uses: actions/upload-artifact@v4
  if: always()
  with: { name: leakage-report, path: leakage-guard-out }
```

- `0` passes the job, `1` blocks the model promotion, `2` signals an infrastructure/config problem (also blocks).
- Use `--fail-on CRITICAL,WARNING` for a stricter pipeline stage.
- Always upload `report.md`/`report.json` as artifacts, including on failure.

### This repository's own CI (`.github/workflows/ci.yml`)

Jobs: `core` (ruff, mypy strict, tests with coverage >= 85%, Python 3.11 and 3.12), `env-dc`, `env-cl`, `e2e` (full CLI across three interpreters), and a weekly scheduled `pin-compat`. All environments are rebuilt from the lockfiles with `--require-hashes`. GitHub only reads workflows from the repository root: if `leakage-guard` lives in a monorepo subfolder, move the file to `<root>/.github/workflows/`.

### Gate hooks

To publish results elsewhere (for example MLflow), implement the protocol and pass it in; the core has no MLflow dependency:

```python
from leakage_guard.gate import GateHook
from leakage_guard.orchestrator import run_guard

class LogToTracker:
    def on_gate(self, report, code):      # called after reports are written
        print(report.gate, code, report.summary)

report, code = run_guard(cfg, base_dir, out_dir, waivers, hooks=[LogToTracker()])
```

## Docker

Images are built from the lockfiles, run as non-root (uid 10001), and are intended to run **without network**.

```bash
docker build -f docker/env-dc.Dockerfile -t leakage-guard-dc .   # deepchecks + ppscore + builtin (Python 3.11)
docker build -f docker/env-cl.Dockerfile -t leakage-guard-cl .   # cleanlab (Python 3.12)

docker run --rm --network none -v "$PWD/work:/work" leakage-guard-dc \
  run --config /work/guard.yaml --out /work/out
```

Each image holds one environment. To run all detectors in containers you must point `environments.*` at interpreters that exist where the CLI runs, or use `detectors.allow_missing`. Verified so far: both images build and import their libraries with `--network none`; a full `run` inside a container is not yet verified.
