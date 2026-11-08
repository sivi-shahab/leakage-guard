# leakage-guard

```{div} lg-tagline
A quality gate that detects, explains and blocks data leakage in tabular ML pipelines.
```

leakage-guard runs several detectors on a train/test pair, merges their findings into one schema, explains *why* each finding counts as leakage, applies time-limited waivers, and returns an exit code your CI/CD can act on. It was built for credit-scoring and AML models at Indonesian banks, but nothing in it is bank-specific.

::::{grid} 1 2 2 4
:gutter: 3

:::{grid-item-card} Install
:link: install
:link-type: doc
Environments, lockfiles and Docker.
:::
:::{grid-item-card} Quickstart
:link: quickstart
:link-type: doc
Run the gate on synthetic data in minutes.
:::
:::{grid-item-card} Tutorial
:link: tutorial
:link-type: doc
Worked examples with planted leakage.
:::
:::{grid-item-card} API reference
:link: api-reference
:link-type: doc
`run_guard`, hooks and prevention utilities.
:::
::::

```{image} architecture-diagram.png
:alt: leakage-guard architecture
:class: only-light
```

```{image} architecture-diagram-dark.png
:alt: leakage-guard architecture
:class: only-dark
```

## Features

- **Eight leakage types (L1 to L8):** duplicate rows, shared entities, temporal overlap, post-outcome features, identifier leakage, preprocessing leakage, train/test drift, near-duplicates and label errors.
- **Four detectors:** a built-in detector plus Deepchecks, ppscore and Cleanlab, each running in its own isolated environment.
- **Explains, does not just flag:** every finding carries a reason block: why it is leakage, evidence, impact, likely root causes, remediation, a verification question, and the basis of its threshold.
- **Fail-closed gate:** exit `0` pass, `1` blocked, `2` error. A missing or crashed detector never looks like a pass.
- **Waivers with expiry:** accepted findings stay visible in the report and block again when the waiver lapses.
- **Privacy by design:** PII is dropped before detectors run, and reports contain aggregates only.
- **Prevention tooling:** leakage-safe time/group splits, a pipeline integrity test, and a semgrep rule for preprocessing leakage.
- **Reproducible:** deterministic output, hash-pinned lockfiles, Docker images, scheduled pin-compatibility tests.

## Quick example

```bash
leakage-guard run --config guard.yaml --out out
```

```text
gate=FAILED critical=5 warning=2 info=0 waived=0 -> out
```

```yaml
# guard.yaml (minimal)
version: 1
model_id: my-scoring-model-v1
data:
  train: data/train.parquet
  test: data/test.parquet
  target: default_flag
  entity_col: customer_id
  time_col: application_date
```

Continue with {doc}`install` and {doc}`quickstart`, or jump to the {doc}`tutorial` for worked examples.

```{admonition} Project status
:class: note
All four implementation milestones are complete. Thresholds are design defaults and not yet calibrated on real portfolios, CI has not yet run on GitHub, and report text is Indonesian only. See {doc}`troubleshooting` for the full list of known limits.
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Getting started

install
quickstart
tutorial
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: User guide

cli
configuration
checks
detectors
waivers
outputs
privacy
prevention
ci-docker
troubleshooting
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Reference

api-reference
development
releases
```

```{toctree}
:maxdepth: 1
:hidden:
:caption: Project documents

ARCHITECTURE
DECISIONS
SPEC
```
