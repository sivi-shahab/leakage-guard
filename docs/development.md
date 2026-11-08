# Development

## Extending leakage-guard

Adding a detector:

1. Write a class with a `name` and `run(self, ctx: DetectorContext) -> list[RawFinding]`, decorate with `@register` (see `detectors/builtin.py`; helpers `classify` and `make_raw` live in `detectors/common.py`).
2. For an external detector, add its module to `_MODULES` in `runners/_common.py`, add a key to `environments` in `config.py`, and import it where the orchestrator expects detectors.
3. Every new `check_id` needs an entry in `reasons/catalog.py`: `THRESHOLD_BASIS`, `LEAKAGE_TYPE`, and a `ReasonTemplate`. The template's placeholders must be satisfiable from `BASE_KEYS` plus the `evidence_keys` your detector guarantees; `validate_catalog()` enforces this at startup.
4. Evidence must contain **aggregates only**.
5. Add a contract test (`tests/detectors/`, see `helpers.assert_contract`) and mark it `deepchecks`, `ppscore` or `cleanlab` if it needs those libraries.

Adding a threshold: add a field to `ThresholdsCfg`, document the basis, and consume it through `classify`.

## Testing, coverage and benchmark

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
