<h1 align="center">leakage-guard</h1>
<p align="center"><b>Detect, explain and block data leakage in tabular ML pipelines.</b></p>
<p align="center">
  <a href="https://sivi-shahab.github.io/leakage-guard/"><img alt="Docs" src="https://img.shields.io/badge/docs-GitHub%20Pages-2b5fd9"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%20%7C%203.12-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-milestone%204-green">
</p>

leakage-guard runs several detectors on a train/test pair, merges their findings into one schema, explains *why* each finding is leakage, applies time-limited waivers, and returns an exit code your CI/CD can act on. Built for credit-scoring and AML models at Indonesian banks; nothing in it is bank-specific.

**Documentation:** https://sivi-shahab.github.io/leakage-guard/ (also readable offline in [`docs/`](docs/index.md)).

## Features

- **Eight leakage types (L1 to L8):** duplicates, shared entities, temporal overlap, post-outcome features, identifiers, preprocessing leakage, train/test drift, near-duplicates and label errors.
- **Four detectors:** built-in, Deepchecks, ppscore and Cleanlab, each in its own isolated environment (their pins conflict).
- **Explains, does not just flag:** every finding carries evidence, impact, root causes, remediation and the basis of its threshold.
- **Fail-closed gate:** exit `0` pass, `1` blocked (CRITICAL without waiver), `2` error. A missing detector never looks like a pass.
- **Waivers with expiry**, **PII dropped before detection**, **deterministic reports**, **hash-pinned lockfiles and Docker images**.
- **Prevention tooling:** `time_split`, `group_split`, `purged_kfold`, a pipeline integrity test and a semgrep rule.

## Quick start

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python --require-hashes --no-deps -r locks/core.lock
uv pip install --python .venv/bin/python --no-deps -e .

.venv/bin/python examples/make_synthetic.py            # synthetic data with planted leakage
.venv/bin/leakage-guard run --config examples/guard.yaml --out out
# gate=FAILED critical=8 warning=2 info=1 waived=0 -> out
```

Minimal config:

```yaml
version: 1
model_id: my-scoring-model-v1
data:
  train: data/train.parquet
  test: data/test.parquet
  target: default_flag
  entity_col: customer_id
  time_col: application_date
```

Other commands: `validate-config`, `explain`, `version`. Using all four detectors, Docker, CI and waivers are covered in the [docs](docs/index.md).

## Project layout

| Path | Contents |
|---|---|
| `src/leakage_guard/` | package: detectors, gate, reasons, prevention |
| `rules/semgrep/` | L6 rule (fit before split) |
| `locks/`, `docker/` | hash-pinned environments and images |
| `examples/`, `benchmarks/`, `tests/` | demo data and configs, AC-7 benchmark, test suite |
| `docs/` | Sphinx site, spec, decisions, architecture |

## Build the docs

```bash
uv venv --python 3.12 .envs/docs
uv pip install --python .envs/docs/bin/python -r locks/docs.in -e .
.envs/docs/bin/sphinx-build -b html docs docs/_build/html
```

Pushes to `main` publish to GitHub Pages via `.github/workflows/docs.yml` (Settings → Pages → Source: GitHub Actions).

## Status and limits

Thresholds are design defaults, not yet calibrated on real portfolios. Reports are Indonesian only. License is not chosen yet (`TODO(owner)`). See [troubleshooting](docs/troubleshooting.md).
