# Command-line reference

```
leakage-guard <command> [options]
```

## `run`

Runs preflight, detectors, aggregation, gate and report writing.

| Option | Default | Description |
|---|---|---|
| `--config PATH` | required | Path to `guard.yaml`. Relative data/waiver paths resolve against this file's directory. |
| `--out DIR` | `leakage-guard-out` | Output directory (created if missing). |
| `--fail-on LIST` | from config | Comma-separated severities that block, e.g. `CRITICAL,WARNING`. Overrides `gate.fail_on`. |
| `--no-html` | off | Do not produce HTML attachments (Deepchecks reports). Faster. |

## `validate-config`

`leakage-guard validate-config --config guard.yaml` checks the config (unknown keys are rejected) and the waivers file. Prints `config ok`.

## `explain`

`leakage-guard explain --report out/report.json --finding-id group_overlap:customer_id` prints the full reason block of one finding as JSON.

## `version`

Prints the package version.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Gate passed: no unwaived finding at a blocking severity. |
| `1` | Gate failed: at least one unwaived finding with severity in `gate.fail_on`. |
| `2` | Runtime error, **fail-closed**: invalid config, preflight failure, missing or crashed or timed-out detector, finding without a reason. |

Exit `2` is deliberate: an incomplete check must never look like a pass. The one exception is `detectors.allow_missing: true`, which turns a missing detector interpreter into a `WARNING` finding (`detector_unavailable`) instead of an error.
