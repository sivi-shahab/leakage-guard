# Prevention utilities

Leakage L6 (preprocessing fitted before the split) has no reliable data-side detector, so prevention is code standards and tests. These utilities are **not** run by `leakage-guard run`; call them from your model project.

## Splits (`leakage_guard.prevention.splits`)

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

## Pipeline integrity (`leakage_guard.prevention.pipeline_integrity`)

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

## Semgrep rule (`rules/semgrep/ml-fit-before-split.yml`)

A heuristic rule (severity WARNING) that flags `fit_transform` / `fit` on data that is later passed to `train_test_split` or `cross_val_score` / `cross_val_predict` / `cross_validate`. It does not flag fitting on the training side after the split, nor `Pipeline` usage.

```bash
.envs/sg/bin/semgrep scan --metrics=off --config rules/semgrep path/to/a.py path/to/b.py
```

Pass **explicit files**: scanning a directory inside a large git repository can take minutes because semgrep walks the enclosing repo. Limits: it follows data only within one function or file, and has not been tuned on real code, so treat hits as review prompts.

## Team standards (SPEC 6.1)

Learned transformers (scaler, imputer, encoder, selector, target encoder, PCA) belong inside a `Pipeline`/`ColumnTransformer` and are fitted on training data only; target encodings and per-customer aggregates must be out-of-fold and use only data **before** the row's observation date; resampling (SMOTE, undersampling) only on training folds; target-based feature selection inside the fold.
