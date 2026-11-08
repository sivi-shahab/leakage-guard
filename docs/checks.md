# Checks and thresholds

Which leakage types leakage-guard detects, how severities and thresholds work, and where each threshold comes from.

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
