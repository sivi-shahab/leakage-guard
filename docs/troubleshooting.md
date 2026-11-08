# Troubleshooting and limits

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Exit 2: `train and test columns differ` | Train and test must share exactly the same columns. |
| Exit 2: `column 'x' not found in data` | A role/PII/quasi-identifier column in the config is not in the data. |
| Exit 2: `target has fewer than two classes in train` | Check the target column and the train sample. |
| Exit 2: interpreter not found | Fix `environments.<name>` or build the env; or `detectors.allow_missing: true` (WARNING instead). |
| Exit 2: detector timeout | Increase `detectors.timeout_s` or lower `runtime.max_rows`. |
| Config error mentioning an extra field | Unknown keys are rejected; check spelling against [Configuration](configuration.md). |
| L2 never detected | Set `data.entity_col` (customer identifier). `index_col` alone cannot detect entity overlap. |
| `detector 'deepchecks' is not registered` in tests | The detector module was not imported; run detector tests in the right environment (`.envs/dc`). |
| Deepchecks pin warning | numpy>=2 or pyarrow>19.0.1 in that environment; use the dedicated `.envs/dc`. |
| Semgrep is extremely slow | Scan explicit files, not directories. |
| Report text is Indonesian | Expected; English reason text is not implemented. |

## Known limits and open items

- Reason text is Indonesian only.
- Thresholds are design defaults, not calibrated on real portfolios; the 0.13 near-duplicate threshold is the Cleanlab default.
- Regression targets with Deepchecks/ppscore are untested (classification only); Python 3.13 untested.
- Large inputs are handled by sampling to `runtime.max_rows`, not by exhaustive scan.
- The semgrep rule is heuristic and untuned on real code.
- CI has not yet run on GitHub; Docker images are import-tested only.
- Open for the owner (`TODO(owner)`): license, calibration, regulatory confirmation (PSAK 109/71, OJK rules), embargo/maturity defaults, approver roles for waivers, HTML retention, and the other open questions in SPEC section 16.
