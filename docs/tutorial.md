# Tutorial: example cases

All outputs below are real runs of the builtin detector on the synthetic data from `examples/make_synthetic.py` (`examples/data/{clean,leaky,drift}_{train,test}.parquet`), using `examples/guard.yaml` with the data paths changed. Reports are in Indonesian; finding IDs and exit codes are as shown.

## Case 1: clean data passes

Time-based, entity-disjoint split with no planted leakage.

```
$ leakage-guard run --config clean.yaml --out out-clean
gate=PASSED critical=0 warning=0 info=0 waived=0 -> out-clean
$ echo $?
0
```

## Case 2: leaky data is blocked

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

The L5 planted leak (sequential `application_id`) is only reported by the ppscore detector (`identifier_label`), which is not enabled in this builtin-only run. Enable it ([Detector environments](detectors.md)) to see it.

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

How to act: remove `kolektibilitas_akhir` from the features (the blocklist says it is only known after the prediction date), re-split by customer and time (`group_split` / `time_split`, [Prevention utilities](prevention.md)), and de-duplicate rows. Re-run until exit 0.

## Case 3: drift between train and test (L7)

```
$ leakage-guard run --config drift.yaml --out out-drift
gate=FAILED critical=1 warning=0 info=0 waived=0 -> out-drift
$ echo $?
1
```

The single finding is `adversarial:channel_code`: a classifier can tell train from test using that one feature. Check whether the feature's definition or source changed over time before deciding to fix or waive.

## Case 4: waivers

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

## Case 5: errors are fail-closed (exit 2)

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

## Case 6: all four detectors

```bash
# guard_m2.yaml: enabled: [builtin, deepchecks, ppscore, cleanlab], environments.* set to your .envs python paths
.venv/bin/leakage-guard run --config examples/guard_m2.yaml --out out
```

On the 1.01-million-row benchmark this gave `gate=FAILED critical=8 warning=2 info=1` (exit 1) in about 13.8 minutes, compared with Case 2 it adds three CRITICAL findings (`identifier_label:application_id` from ppscore and Deepchecks, `pps_train:kolektibilitas_akhir` from ppscore and Deepchecks, `near_dup_cross_split:row` from Cleanlab) and an INFO `date_shared:application_date` (Deepchecks). Findings reported by several detectors, such as `group_overlap:customer_id` (builtin + Deepchecks), are merged into one ID with all sources listed, which raises confidence.

## Case 7: preventing leakage in your own model code

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
