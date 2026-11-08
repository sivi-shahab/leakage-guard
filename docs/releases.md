# Releases

Version `0.1.0` (pre-release). History by milestone:

## Milestone 4: hardening

- Hash-pinned lockfiles per environment (`locks/`), Dockerfiles for the Deepchecks and Cleanlab environments (non-root, no network), GitHub Actions workflow, scheduled pin-compatibility test, benchmark script.
- `GateHook` extension point; warning when Deepchecks pins are not met.
- Benchmark: about 1.01 million input rows in 829 s (13.8 min) with all four detectors at `max_rows=100000`.
- Core coverage 95%. This documentation site.

## Milestone 3: prevention

- `prevention.splits` (time, group and purged splits with embargo and maturity window), `prevention.pipeline_integrity`, and the `ml-fit-before-split` semgrep rule.

## Milestone 2: external detectors

- Deepchecks, ppscore and Cleanlab detectors, run as subprocesses in isolated environments, with contract and end-to-end tests.

## Milestone 1: foundation

- Models, config, preflight, the built-in detector, aggregator, reason engine, waivers, gate, JSON and Markdown reports, CLI, and synthetic datasets with planted leakage.

Design decisions and deviations from the specification are recorded in {doc}`DECISIONS`.
