# Detector environments

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
