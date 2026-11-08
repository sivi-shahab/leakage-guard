# leakage-guard: Usage Guide

`leakage-guard` is a quality gate that detects and explains **data leakage** in tabular ML pipelines (built for credit scoring and AML at Indonesian banks). It runs several detectors on a train/test pair, merges their findings into one schema, explains *why* each finding is considered leakage, applies approved waivers, and returns an exit code your CI/CD can act on.

Related documents: `SPEC.md` (specification v1.2), `ARCHITECTURE.md`, `DECISIONS.md` (design decisions and deviations), `spec-verification.md` (source verification).

> **Language note.** Command output, config keys and JSON field names are in English. The generated *reason text* (summaries, remediation, verification questions in `report.json` / `report.md`) is currently **Indonesian only** (`report.language: id`); English reason text is not implemented (SPEC section 16, item 6).

---

## Contents

1. [What it checks](#1-what-it-checks)
2. [Installation](#2-installation)
3. [Quick start](#3-quick-start)
4. [CLI reference](#4-cli-reference)
5. [Configuration reference (`guard.yaml`)](#5-configuration-reference-guardyaml)
6. [Checks and thresholds](#6-checks-and-thresholds)
7. [Waivers](#7-waivers)
8. [Outputs](#8-outputs)
9. [Detector environments](#9-detector-environments)
10. [Privacy guarantees](#10-privacy-guarantees)
11. [Prevention utilities](#11-prevention-utilities)
12. [CI/CD integration](#12-cicd-integration)
13. [Docker](#13-docker)
14. [Extending leakage-guard](#14-extending-leakage-guard)
15. [Testing, coverage and benchmark](#15-testing-coverage-and-benchmark)
16. [Example cases](#16-example-cases)
17. [Troubleshooting](#17-troubleshooting)
18. [Known limits and open items](#18-known-limits-and-open-items)

---

## 1. What it checks

Leakage is classified L1 to L8:

| Type | Meaning | Examples of check IDs |
|---|---|---|
| L1 | Duplicate rows across train/test | `row_overlap` |
| L2 | Same entity (e.g. customer) on both sides | `group_overlap` |
| L3 | Temporal leakage (test dates inside the training period, embargo violations) | `temporal`, `temporal_embargo`, `date_shared` |
| L4 | Post-outcome features / target proxies | `blocklist_hit`, `suspicious_names`, `single_feature`, `pps_train` |
| L5 | Identifier correlated with the target | `identifier_label` |
| L6 | Preprocessing fitted before the split | `pipeline_integrity` (test utility) and the semgrep rule |
| L7 | Train/test distribution drift | `adversarial` |
| L8 | Near-duplicates across splits, label errors | `near_dup_cross_split`, `label_errors` |

Housekeeping findings (no leakage type): `pps_blind_spot`, `detector_unavailable`, `orphan_waiver`, `quasi_identifier_risk`.

Four detectors produce findings:

| Detector | Runs in | Produces |
|---|---|---|
| `builtin` | core process | overlap, temporal, blocklist, name patterns, single-feature, adversarial |
| `deepchecks` | subprocess, `.envs/dc` | Deepchecks train/test checks (run on two `Dataset`s, see D-notes in `DECISIONS.md`) |
| `ppscore` | subprocess, `.envs/dc` | `pps_train`, `identifier_label`, `pps_blind_spot` |
| `cleanlab` | subprocess, `.envs/cl` | `near_dup_cross_split`, `label_errors` |

---

## 2. Installation

Requirements: Python 3.11 or 3.12 (3.13 is **not** supported/tested), [`uv`](https://docs.astral.sh/uv/).

Deepchecks and Cleanlab have conflicting pins, so there are separate environments, each rebuilt from a hash-pinned lockfile in `locks/`:

| Environment | Contents | Lockfile | Python |
|---|---|---|---|
| core (`.venv`) | `builtin` detector, CLI, core tests | `locks/core.lock` | 3.11 / 3.12 |
| `.envs/dc` | deepchecks 0.19.1 + ppscore | `locks/dc.lock` | 3.11 |
| `.envs/cl` | cleanlab[datalab] | `locks/cl.lock` | 3.12 |
| `.envs/sg` | semgrep (rule L6 tests only) | `locks/sg.lock` | 3.11+ |

```bash
make_env() {  # usage: make_env <dir> <python> <lock-name>
  uv venv --python "$2" "$1" \
  && uv pip install --python "$1/bin/python" --require-hashes --no-deps -r "locks/$3.lock" \
  && uv pip install --python "$1/bin/python" --no-deps -e .
}
make_env .venv    3.12 core
make_env .envs/dc 3.11 dc      # only if you use deepchecks / ppscore
make_env .envs/cl 3.12 cl      # only if you use cleanlab
```

You only need the environments for the detectors you enable. With just `builtin`, the core environment is enough.

**Do not install deepchecks and cleanlab into one environment.** If you must, you need `pyarrow<=19.0.1` and `numpy<2`; the deepchecks detector logs a warning (not an error) when these pins are not met.

Pins are deliberate (`scikit-learn<1.6`, `numpy<2`, `pandas<2.3`, `setuptools<81`, `pyarrow<=19.0.1`). Do not relax them without re-testing; the scheduled `tests/compat` job checks that versions beyond the pins still fail.

---

## 3. Quick start

```bash
# 1. Generate synthetic data with deliberately planted leakage (and a clean variant)
.venv/bin/python examples/make_synthetic.py          # writes examples/data/*.parquet

# 2. Validate the config
.venv/bin/leakage-guard validate-config --config examples/guard.yaml

# 3. Run the gate (builtin only, uses examples/guard.yaml)
.venv/bin/leakage-guard run --config examples/guard.yaml --out out
echo "exit code: $?"          # 1 = blocked on the leaky data

# 4. Read the result
less out/report.md
```

For all four detectors, edit `examples/guard_m2.yaml` so `environments.deepchecks`, `environments.ppscore` and `environments.cleanlab` point to the Python interpreters of your `.envs/*`, then run it the same way.

Console summary printed by `run`:

```
gate=FAILED critical=8 warning=2 info=1 waived=0 -> out
```

---

## 4. CLI reference

```
leakage-guard <command> [options]
```

### `run`

Runs preflight, detectors, aggregation, gate and report writing.

| Option | Default | Description |
|---|---|---|
| `--config PATH` | required | Path to `guard.yaml`. Relative data/waiver paths resolve against this file's directory. |
| `--out DIR` | `leakage-guard-out` | Output directory (created if missing). |
| `--fail-on LIST` | from config | Comma-separated severities that block, e.g. `CRITICAL,WARNING`. Overrides `gate.fail_on`. |
| `--no-html` | off | Do not produce HTML attachments (Deepchecks reports). Faster. |

### `validate-config`

`leakage-guard validate-config --config guard.yaml` checks the config (unknown keys are rejected) and the waivers file. Prints `config ok`.

### `explain`

`leakage-guard explain --report out/report.json --finding-id group_overlap:customer_id` prints the full reason block of one finding as JSON.

### `version`

Prints the package version.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Gate passed: no unwaived finding at a blocking severity. |
| `1` | Gate failed: at least one unwaived finding with severity in `gate.fail_on`. |
| `2` | Runtime error, **fail-closed**: invalid config, preflight failure, missing or crashed or timed-out detector, finding without a reason. |

Exit `2` is deliberate: an incomplete check must never look like a pass. The one exception is `detectors.allow_missing: true`, which turns a missing detector interpreter into a `WARNING` finding (`detector_unavailable`) instead of an error.

---

## 5. Configuration reference (`guard.yaml`)

Unknown keys are rejected. Minimal config:

```yaml
version: 1
model_id: my-scoring-model-v1
data:
  train: data/train.parquet
  test: data/test.parquet
  target: default_flag
```

Full reference with defaults:

```yaml
version: 1                       # config schema version
model_id: abc-scoring-pd-v3      # required; shown in the report

data:
  train: data/train.parquet      # required; Parquet, CSV or Feather (local path)
  test: data/test.parquet        # required
  target: default_flag           # required; needs >= 2 classes in train
  entity_col: customer_id        # optional: enables L2 (entity overlap)
  time_col: application_date    # optional: enables temporal checks (L3)
  index_col: application_id      # optional: row identifier, enables L5
  pii_columns: [nik, npwp, nama] # dropped before detectors; see section 10

prediction:                      # temporal controls
  prediction_date_col: null      # column holding the prediction/observation date
  embargo_days: 0                # > 0 activates temporal_embargo (always WARNING)
  maturity_window_days: 0        # days an outcome needs to be observable

blocklist:
  forbidden_columns: []          # columns known only AFTER prediction time -> CRITICAL if present as features
  suspicious_name_patterns: []   # substrings; matching column names -> suspicious_names finding

thresholds:                      # all configurable; defaults below
  row_overlap:      { warn_pct: 0.0, crit_pct: 1.0 }
  temporal:         { warn_pct: 0.0, crit_pct: 5.0 }
  single_feature:   { warn: 0.85, crit: 0.95 }
  pps:              { warn: 0.5,  crit: 0.8 }
  identifier_label: { warn: 0.1,  crit: 0.2 }
  adversarial:      { warn: 0.70, crit: 0.95 }
  pipeline_gap:     { warn: 0.02, crit: 0.05 }
  near_dup_cross_split: { warn_pct: 0.0, crit_pct: 1.0 }
  near_dup_threshold: 0.13       # Cleanlab near-duplicate distance threshold
thresholds_basis: {}             # override the "basis" label per check_id (see section 6)

runtime:
  max_rows: 100000               # detectors sample down to this many rows
  seed: 42                       # all randomness is seeded

gate:
  fail_on: [CRITICAL]            # severities that block (exit 1)
  waivers_file: null             # path to waivers.yaml

report:
  language: id                   # only "id" is implemented
  require_owner_assessment: true # report counts findings awaiting owner assessment
  attach_html: true              # copy Deepchecks HTML reports to --out

environments:                    # interpreter per detector; null = current process
  builtin: null
  deepchecks: /path/to/.envs/dc/bin/python
  ppscore:    /path/to/.envs/dc/bin/python
  cleanlab:   /path/to/.envs/cl/bin/python

detectors:
  enabled: [builtin]             # any of: builtin, deepchecks, ppscore, cleanlab
  allow_missing: false           # true: missing interpreter -> WARNING instead of exit 2
  timeout_s: 1800                # per external detector

privacy:
  quasi_identifier_columns: []   # e.g. age, region, postal code; values never reach reports
  min_group_size: 5              # k-anonymity threshold (proposal, uncalibrated)
```

Notes:

- `entity_col` and `index_col` are **different roles**. L2 (same customer on both sides) is only detected through `entity_col`. A unique-per-row `application_id` used as the only identifier gives overlap 0 and will *not* reveal L2.
- Valid thresholds require `warn <= crit`.
- Every column referenced in `data.*` and `privacy.quasi_identifier_columns` must exist, otherwise preflight fails (exit 2).
- Train and test must have identical columns and be non-empty.

---

## 6. Checks and thresholds

Severities: `INFO` < `WARNING` < `CRITICAL`. Duplicate findings from several detectors collapse into one `finding_id` (`<check_id>:<column or scope>`), taking the highest severity and merging sources and evidence.

**Threshold basis.** Every finding states where its threshold comes from, and the report text repeats it:

| Basis | Meaning |
|---|---|
| `deepchecks_default` | Same value as a Deepchecks default |
| `design` | A design choice in SPEC; **not calibrated** on your data |
| `calibrated` | Calibrated on real data (set via `thresholds_basis` once you have done so) |

Almost all defaults are `design`. Treat them as starting points and calibrate on your own portfolio (`TODO(owner)`); then record it:

```yaml
thresholds_basis:
  pps_train: calibrated
```

**Confidence** in each reason: `high` when at least two independent detectors agree or a rule is explicit (blocklist, exact duplicate); `medium` for a single CRITICAL detector; `low` for WARNING or heuristics.

**Important caveats** (documented, not bugs):

- `single_feature` (builtin) and `adversarial` (builtin, single-feature AUC) are *not* equivalent to ppscore's PPS or Deepchecks' `MultivariateDrift`.
- `adversarial` ignores role columns (`time_col`, `entity_col`, `index_col`) so a legitimate out-of-time split does not trigger a false CRITICAL.
- Deepchecks `DateTrainTestLeakageDuplicates` measures shared dates and fires on almost any random split, so it is reported as the separate low-severity `date_shared`, not as `temporal`.
- `ppscore` cannot score string IDs; that blind spot is reported as `pps_blind_spot` instead of being silently skipped.

---

## 7. Waivers

A waiver accepts a known finding for a limited time. Put them in a YAML file and reference it from `gate.waivers_file` (path relative to `guard.yaml`).

```yaml
waivers:
  - finding_id: group_overlap:customer_id     # check_id:column (or scope)
    owner: model.owner@example.com
    approved_by: model.risk@example.com
    reason: "One customer holds several products; impact measured and immaterial"
    expires: 2027-02-28                       # valid through this date, inclusive
```

Rules:

- All five fields are required.
- A waiver applies only while `expires >= run date`. After that the finding **blocks again** automatically.
- A waiver whose `finding_id` matches nothing produces an `orphan_waiver` finding (INFO) so stale waivers get cleaned up.
- Waived findings stay in the report (`waived: true`, with the waiver attached); they are counted separately and do not affect the exit code.

---

## 8. Outputs

Written to `--out`:

| File | Content |
|---|---|
| `report.json` | Machine-readable report (schema below) |
| `report.md` | Human-readable report: summary table plus one block per finding |
| `*.html` | Deepchecks HTML reports, if `report.attach_html` and not `--no-html` |

### `report.json`

```json
{
  "model_id": "abc-scoring-pd-v3",
  "run_at": "2026-11-08T02:09:03Z",
  "config_hash": "sha256:...",
  "data_fingerprint": {"...": "row counts and schema hash, never data values"},
  "tools": {"deepchecks": "0.19.1", "...": "..."},
  "summary": {"critical": 8, "warning": 2, "info": 1, "waived": 0},
  "gate": "FAILED",
  "owner_assessment_pending": 10,
  "findings": [ { "finding_id": "blocklist_hit:kolektibilitas_akhir",
                  "check_id": "blocklist_hit", "leakage_type": "L4",
                  "severity": "CRITICAL", "scope": "feature", "column": "kolektibilitas_akhir",
                  "metric": {"name": "...", "value": 0.0, "threshold": 0.0},
                  "threshold_basis": "design", "message": "...",
                  "sources": ["builtin"], "waived": false, "waiver": null,
                  "reason": { "summary": "...", "why_leakage": "...", "evidence": {},
                              "impact": "...", "likely_root_causes": [], "remediation": [],
                              "verification_question": "...", "confidence": "high",
                              "owner_assessment": null } } ]
}
```

Output is **deterministic**: with the same inputs, config and seed, two runs produce identical bytes (apart from `run_at`).

### Owner assessment

Each reason has `owner_assessment`: one of `confirmed_leakage`, `legitimate_feature`, `needs_investigation`, or empty. The reports explain *symptoms*, not verdicts; the model owner decides. With `report.require_owner_assessment: true`, the report counts how many findings still await an assessment.

### Typical workflow when blocked

1. Open `report.md`, start with `[CRITICAL]` blocks.
2. Read "Why this is leakage", the evidence table, and the verification question.
3. Either fix the pipeline (remove the column, split by entity/time, rebuild features) and re-run, or, if the feature is legitimate, request a time-limited waiver (section 7).
4. `leakage-guard explain --report out/report.json --finding-id <id>` to share one finding.

---

## 9. Detector environments

External detectors run as subprocesses (`python -m leakage_guard.runners.<name>`) using the interpreter given in `environments.<name>`:

1. The orchestrator writes a spec JSON and cleaned Parquet copies (PII removed) to a temp directory.
2. The runner reads them, runs the detector, writes a result JSON (or `{"error": ...}`).
3. Findings are validated against the `RawFinding` schema.

Failure handling (fail-closed):

| Situation | Behavior |
|---|---|
| Interpreter path missing/not executable | Exit 2, message names the path; with `allow_missing: true` becomes WARNING `detector_unavailable` |
| Runner crash | Exit 2 |
| Timeout (`detectors.timeout_s`) | Exit 2 |
| Detector listed in `enabled` but unknown | Exit 2 |

No network access is needed at runtime. Subprocesses are launched without `shell=True`.

`runtime.max_rows` bounds the work: detectors sample down to this many rows (default 100,000) with the configured seed. A measured full run on ~1.01 million input rows with all four detectors, `max_rows=100000`, took about **829 seconds (13.8 min)** (single measurement, WSL2, under other CPU load).

---

## 10. Privacy guarantees

- Columns in `data.pii_columns` are dropped before any detector sees the data. Exception: if a role column (`entity_col`, `time_col`, `index_col`, `target`) is also listed as PII, it is replaced by a truncated SHA-256 pseudonym so overlap checks still work. (A hash is **not** anonymisation under the Indonesian PDP law, Art. 4(3)(f), so the values are still never written to any output.)
- Reports, logs and evidence contain **aggregates only**, never row values. Quasi-identifier columns may be used by detectors but their values never appear in outputs.
- The data fingerprint contains row counts and a schema hash, not value hashes.
- Preflight warns (`quasi_identifier_risk`, WARNING) when a combination of quasi-identifier columns yields groups smaller than `privacy.min_group_size`.
- Automated tests plant unique marker values in PII and quasi-identifier columns and assert they appear in none of `report.json`, `report.md` or the HTML files (AC-5).

Regulatory statements in the project are limited to what `SPEC.md` claims; compliance confirmation is a `TODO(owner)`.

---

## 11. Prevention utilities

Leakage L6 (preprocessing fitted before the split) has no reliable data-side detector, so prevention is code standards and tests. These utilities are **not** run by `leakage-guard run`; call them from your model project.

### 11.1 Splits (`leakage_guard.prevention.splits`)

All durations are in **days**. (If you wrap a library whose purge/embargo is in observations, such as skfolio's `purged_size`, convert: observations = days x rows per day.)

```python
from leakage_guard.prevention.splits import time_split, group_split, purged_kfold, drop_immature

# Train: time <= cutoff - embargo.  Test: time > cutoff.
# Rows whose outcome is not yet observable (time + maturity > as_of) are dropped.
train, test = time_split(
    df, "application_date", cutoff="2025-06-30",
    embargo_days=30, maturity_window_days=365,   # as_of defaults to the latest date in df
)

# Random split where no customer appears on both sides
train, test = group_split(df, "customer_id", test_size=0.2, seed=0)

# Time-ordered K-fold with purging: training rows within embargo_days of the test block are removed
for train_idx, test_idx in purged_kfold(df, "application_date", n_splits=5, embargo_days=30):
    ...   # positional indices (use df.iloc)
```

### 11.2 Pipeline integrity (`leakage_guard.prevention.pipeline_integrity`)

Verifies that the model is a clone-able `sklearn.pipeline.Pipeline` (at least two steps) and compares the CV score of the correct pipeline against a deliberately leaky variant whose preprocessing is fitted on all data. A large gap means a step is sensitive to leakage.

```python
from leakage_guard.config import load_config
from leakage_guard.prevention.pipeline_integrity import score_gap, pipeline_integrity_findings

gap = score_gap(pipeline, X, y, cv=5, scoring="roc_auc")     # leaky_score - correct_score

cfg = load_config(Path("guard.yaml"))
findings = pipeline_integrity_findings(pipeline, X, y, cfg)  # [] if gap < warn
assert not findings, findings
```

- Gap thresholds: `thresholds.pipeline_gap` (warn 0.02, crit 0.05, uncalibrated design values).
- A non-`Pipeline` model (or one with a single step, or one that cannot be cloned) raises `TypeError`; it is not returned as a finding.
- Typical use is a unit test in your model repository that fails CI when preprocessing leaks.

### 11.3 Semgrep rule (`rules/semgrep/ml-fit-before-split.yml`)

A heuristic rule (severity WARNING) that flags `fit_transform` / `fit` on data that is later passed to `train_test_split` or `cross_val_score` / `cross_val_predict` / `cross_validate`. It does not flag fitting on the training side after the split, nor `Pipeline` usage.

```bash
.envs/sg/bin/semgrep scan --metrics=off --config rules/semgrep path/to/a.py path/to/b.py
```

Pass **explicit files**: scanning a directory inside a large git repository can take minutes because semgrep walks the enclosing repo. Limits: it follows data only within one function or file, and has not been tuned on real code, so treat hits as review prompts.

### 11.4 Team standards (SPEC 6.1)

Learned transformers (scaler, imputer, encoder, selector, target encoder, PCA) belong inside a `Pipeline`/`ColumnTransformer` and are fitted on training data only; target encodings and per-customer aggregates must be out-of-fold and use only data **before** the row's observation date; resampling (SMOTE, undersampling) only on training folds; target-based feature selection inside the fold.

---

## 12. CI/CD integration

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

---

## 13. Docker

Images are built from the lockfiles, run as non-root (uid 10001), and are intended to run **without network**.

```bash
docker build -f docker/env-dc.Dockerfile -t leakage-guard-dc .   # deepchecks + ppscore + builtin (Python 3.11)
docker build -f docker/env-cl.Dockerfile -t leakage-guard-cl .   # cleanlab (Python 3.12)

docker run --rm --network none -v "$PWD/work:/work" leakage-guard-dc \
  run --config /work/guard.yaml --out /work/out
```

Each image holds one environment. To run all detectors in containers you must point `environments.*` at interpreters that exist where the CLI runs, or use `detectors.allow_missing`. Verified so far: both images build and import their libraries with `--network none`; a full `run` inside a container is not yet verified.

---

## 14. Extending leakage-guard

Adding a detector:

1. Write a class with a `name` and `run(self, ctx: DetectorContext) -> list[RawFinding]`, decorate with `@register` (see `detectors/builtin.py`; helpers `classify` and `make_raw` live in `detectors/common.py`).
2. For an external detector, add its module to `_MODULES` in `runners/_common.py`, add a key to `environments` in `config.py`, and import it where the orchestrator expects detectors.
3. Every new `check_id` needs an entry in `reasons/catalog.py`: `THRESHOLD_BASIS`, `LEAKAGE_TYPE`, and a `ReasonTemplate`. The template's placeholders must be satisfiable from `BASE_KEYS` plus the `evidence_keys` your detector guarantees; `validate_catalog()` enforces this at startup.
4. Evidence must contain **aggregates only**.
5. Add a contract test (`tests/detectors/`, see `helpers.assert_contract`) and mark it `deepchecks`, `ppscore` or `cleanlab` if it needs those libraries.

Adding a threshold: add a field to `ThresholdsCfg`, document the basis, and consume it through `classify`.

---

## 15. Testing, coverage and benchmark

```bash
.venv/bin/pytest -q --cov                    # core + integration; detector tests skip without their libs
.envs/dc/bin/pytest -q tests/detectors       # deepchecks, ppscore
.envs/cl/bin/pytest -q tests/detectors       # cleanlab
.venv/bin/pytest -q tests/compat -m compat   # scheduled; needs network; pins beyond limits must still fail
.venv/bin/ruff check src tests && .venv/bin/mypy
.venv/bin/python benchmarks/run_benchmark.py --rows 1000000 --work lg-bench   # AC-7
```

The acceptance tests (AC-1 to AC-10 in `SPEC.md`) cover detection of planted leakage, no false CRITICALs on the clean variant, unique finding IDs, waiver expiry, no PII in any artifact, reproducible environments, a reason for every finding, determinism, and correct metric/column in each reason.

Latest local results: 42 passed, 3 skipped (detector tests outside their environments), core coverage 95%, `ruff` and `mypy --strict` clean.

---

## 16. Example cases

All outputs below are real runs of the builtin detector on the synthetic data from `examples/make_synthetic.py` (`examples/data/{clean,leaky,drift}_{train,test}.parquet`), using `examples/guard.yaml` with the data paths changed. Reports are in Indonesian; finding IDs and exit codes are as shown.

### Case 1: clean data passes

Time-based, entity-disjoint split with no planted leakage.

```
$ leakage-guard run --config clean.yaml --out out-clean
gate=PASSED critical=0 warning=0 info=0 waived=0 -> out-clean
$ echo $?
0
```

### Case 2: leaky data is blocked

Planted: duplicated rows (L1), shared customers (L2), shared dates (L3), a post-outcome column `kolektibilitas_akhir` (L4), an ID ordered by outcome (L5).

```
$ leakage-guard run --config leaky.yaml --out out-leaky
gate=FAILED critical=5 warning=2 info=0 waived=0 -> out-leaky
$ echo $?
1
```

Findings (sorted by severity, then ID):

| Severity | `finding_id` | Type |
|---|---|---|
| CRITICAL | `blocklist_hit:kolektibilitas_akhir` | L4 |
| CRITICAL | `group_overlap:customer_id` | L2 |
| CRITICAL | `row_overlap:row` | L1 |
| CRITICAL | `single_feature:kolektibilitas_akhir` | L4 |
| CRITICAL | `temporal:application_date` | L3 |
| WARNING | `suspicious_names:kolektibilitas_akhir` | L4 |
| WARNING | `temporal_embargo:application_date` | L3 |

The L5 planted leak (sequential `application_id`) is only reported by the ppscore detector (`identifier_label`), which is not enabled in this builtin-only run. Enable it (section 9) to see it.

Inspect one finding:

```
$ leakage-guard explain --report out-leaky/report.json --finding-id group_overlap:customer_id
{
  "summary": "78.92% data test memakai entitas yang juga ada di train.",
  "evidence": { "n_entities_overlap": 771, "pct_test_entities": 78.9, "detectors_agreeing": ["builtin"] },
  "impact": "Metrik evaluasi (AUC, KS, Gini) terlalu optimis; ...",
  ...
}
```

How to act: remove `kolektibilitas_akhir` from the features (the blocklist says it is only known after the prediction date), re-split by customer and time (`group_split` / `time_split`, section 11), and de-duplicate rows. Re-run until exit 0.

### Case 3: drift between train and test (L7)

```
$ leakage-guard run --config drift.yaml --out out-drift
gate=FAILED critical=1 warning=0 info=0 waived=0 -> out-drift
$ echo $?
1
```

The single finding is `adversarial:channel_code`: a classifier can tell train from test using that one feature. Check whether the feature's definition or source changed over time before deciding to fix or waive.

### Case 4: waivers

Waivers file (`waived.yaml` points to it via `gate.waivers_file`), covering the five CRITICAL findings of Case 2 plus one ID that matches nothing:

```yaml
waivers:
  - {finding_id: group_overlap:customer_id, owner: owner@example.com, approved_by: risk@example.com,
     reason: "accepted for demo", expires: 2099-01-01}
  # ...same shape for the other four CRITICAL IDs...
  - {finding_id: "pps_train:nonexistent", owner: owner@example.com, approved_by: risk@example.com,
     reason: "accepted for demo", expires: 2099-01-01}
```

```
$ leakage-guard run --config waived.yaml --out out-waived
gate=PASSED critical=0 warning=2 info=1 waived=5 -> out-waived     # exit 0
```

- The 5 waived findings stay in the report with `waived: true`.
- The INFO finding is `orphan_waiver:pps_train:nonexistent` (a waiver that matches nothing, to be cleaned up).
- WARNINGs do not block because `gate.fail_on` is `[CRITICAL]`.

**Expired waiver.** Same file, but the waiver for `blocklist_hit:kolektibilitas_akhir` has `expires: 2020-01-01`:

```
$ leakage-guard run --config expired.yaml --out out-expired
gate=FAILED critical=1 warning=2 info=0 waived=4 -> out-expired    # exit 1
```

The expired waiver no longer protects its finding, so it blocks again. A stricter stage can add `--fail-on CRITICAL,WARNING`.

### Case 5: errors are fail-closed (exit 2)

Bad column in config:

```
$ leakage-guard run --config bad.yaml --out out-bad
ERROR leakage_guard: data.target: column 'nope' not found in data
$ echo $?
2
```

Detector interpreter missing:

```
$ leakage-guard run --config missing.yaml --out out-missing      # enabled: [builtin, cleanlab]
ERROR leakage_guard: interpreter for 'cleanlab' not found: /nonexistent/python (expected the Python of its dedicated environment, set at environments.cleanlab)
$ echo $?
2
```

With `detectors.allow_missing: true` the same run continues, adds a `WARNING detector_unavailable:cleanlab`, and the gate is decided by the remaining detectors (here still `FAILED`, exit 1, because Case 2's CRITICALs remain). Use it only in development; in CI keep the default so a missing detector cannot look like a pass.

### Case 6: all four detectors

```bash
# guard_m2.yaml: enabled: [builtin, deepchecks, ppscore, cleanlab], environments.* set to your .envs python paths
.venv/bin/leakage-guard run --config examples/guard_m2.yaml --out out
```

On the 1.01-million-row benchmark this gave `gate=FAILED critical=8 warning=2 info=1` (exit 1) in about 13.8 minutes, compared with Case 2 it adds three CRITICAL findings (`identifier_label:application_id` from ppscore and Deepchecks, `pps_train:kolektibilitas_akhir` from ppscore and Deepchecks, `near_dup_cross_split:row` from Cleanlab) and an INFO `date_shared:application_date` (Deepchecks). Findings reported by several detectors, such as `group_overlap:customer_id` (builtin + Deepchecks), are merged into one ID with all sources listed, which raises confidence.

### Case 7: preventing leakage in your own model code

Time split with embargo, on 100 daily rows starting 2024-01-01:

```python
train, test = time_split(df, "t", "2024-02-15", embargo_days=5)
# len(train)=41, train ends 2024-02-10  (cutoff minus 5 days)
# len(test)=54,  test starts 2024-02-16
```

Pipeline integrity: feature selection fitted on all data is a classic L6 leak. On 120 rows of pure noise (400 features, random labels), selecting the best 10 features outside the CV loop inflates the score:

```python
pipe = Pipeline([("sel", SelectKBest(f_classif, k=10)), ("m", LogisticRegression())])
score_gap(pipe, X, y)        # 0.15  -> above pipeline_gap.crit (0.05): CRITICAL pipeline_integrity
```

A proper pipeline (scaler plus model, with all fitting inside CV folds) gives a gap near zero and no finding. Put this in a unit test so CI fails when someone moves a transformer outside the pipeline:

```python
def test_no_preprocessing_leak():
    assert pipeline_integrity_findings(pipeline, X, y, cfg) == []
```

Semgrep catches the same mistake statically:

```python
scaler = StandardScaler()
Xs = scaler.fit_transform(X)                 # <- flagged: ml-fit-before-split
X_tr, X_te, y_tr, y_te = train_test_split(Xs, y)
```

Correct: split first, then `scaler.fit_transform(X_tr)` and `scaler.transform(X_te)`, or use a `Pipeline`.

---

## 17. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Exit 2: `train and test columns differ` | Train and test must share exactly the same columns. |
| Exit 2: `column 'x' not found in data` | A role/PII/quasi-identifier column in the config is not in the data. |
| Exit 2: `target has fewer than two classes in train` | Check the target column and the train sample. |
| Exit 2: interpreter not found | Fix `environments.<name>` or build the env; or `detectors.allow_missing: true` (WARNING instead). |
| Exit 2: detector timeout | Increase `detectors.timeout_s` or lower `runtime.max_rows`. |
| Config error mentioning an extra field | Unknown keys are rejected; check spelling against section 5. |
| L2 never detected | Set `data.entity_col` (customer identifier). `index_col` alone cannot detect entity overlap. |
| `detector 'deepchecks' is not registered` in tests | The detector module was not imported; run detector tests in the right environment (`.envs/dc`). |
| Deepchecks pin warning | numpy>=2 or pyarrow>19.0.1 in that environment; use the dedicated `.envs/dc`. |
| Semgrep is extremely slow | Scan explicit files, not directories. |
| Report text is Indonesian | Expected; English reason text is not implemented. |

---

## 18. Known limits and open items

- Reason text is Indonesian only.
- Thresholds are design defaults, not calibrated on real portfolios; the 0.13 near-duplicate threshold is the Cleanlab default.
- Regression targets with Deepchecks/ppscore are untested (classification only); Python 3.13 untested.
- Large inputs are handled by sampling to `runtime.max_rows`, not by exhaustive scan.
- The semgrep rule is heuristic and untuned on real code.
- CI has not yet run on GitHub; Docker images are import-tested only.
- Open for the owner (`TODO(owner)`): license, calibration, regulatory confirmation (PSAK 109/71, OJK rules), embargo/maturity defaults, approver roles for waivers, HTML retention, and the other open questions in SPEC section 16.
