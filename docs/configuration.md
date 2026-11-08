# Configuration (`guard.yaml`)

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
  pii_columns: [nik, npwp, nama] # dropped before detectors; see [Privacy](privacy.md)

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
thresholds_basis: {}             # override the "basis" label per check_id (see [Checks and thresholds](checks.md))

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
