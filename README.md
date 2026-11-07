# leakage-guard

Quality gate untuk mendeteksi dan menjelaskan data leakage di pipeline ML tabular. Spesifikasi: `docs/SPEC.md` (v1.2); verifikasi sumber: `docs/spec-verification.md`; keputusan: `docs/DECISIONS.md`.

**Status: Milestone 1** (detektor `builtin` saja). Deepchecks, ppscore, Cleanlab, pencegahan, Docker, dan CI menyusul (lihat `docs/DECISIONS.md` D8).

```
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python examples/make_synthetic.py            # data sintetis di examples/data
.venv/bin/leakage-guard run --config examples/guard.yaml --out out
```

Exit code: `0` lolos, `1` ada CRITICAL tanpa waiver, `2` error runtime (fail-closed).
