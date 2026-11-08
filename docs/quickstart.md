# Quick start

```bash
# 1. Generate synthetic data with deliberately planted leakage (and a clean variant)
.venv/bin/python examples/make_synthetic.py          # writes examples/data/*.parquet

# 2. Validate the config
.venv/bin/leakage-guard validate-config --config examples/guard.yaml

# 3. Run the gate (builtin only, uses examples/guard.yaml)
.venv/bin/leakage-guard run --config examples/guard.yaml --out out
echo "exit code: $?"          # 1 = blocked on the leaky data

# 4. Read the result
less out/report.md
```

For all four detectors, edit `examples/guard_m2.yaml` so `environments.deepchecks`, `environments.ppscore` and `environments.cleanlab` point to the Python interpreters of your `.envs/*`, then run it the same way.

Console summary printed by `run`:

```
gate=FAILED critical=8 warning=2 info=1 waived=0 -> out
```
