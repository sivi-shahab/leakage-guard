# leakage-guard

Quality gate untuk mendeteksi dan menjelaskan data leakage di pipeline ML tabular (credit scoring, AML). Spesifikasi: `docs/SPEC.md` (v1.2); verifikasi sumber: `docs/spec-verification.md`; keputusan: `docs/DECISIONS.md`; arsitektur: `docs/ARCHITECTURE.md`; **dokumentasi pengguna (Inggris): `docs/index.md`** (dibangun dengan Sphinx, dipublikasikan ke GitHub Pages lewat `.github/workflows/docs.yml`).

**Status: Milestone 4** (detektor `builtin`, `deepchecks`, `ppscore`, `cleanlab`; utilitas pencegahan; semgrep L6; lockfile, Docker, CI).

## Pasang dan jalankan

Tiga environment terpisah karena pin Deepchecks bentrok dengan Cleanlab:

| Env | Isi | Lockfile | Python |
|---|---|---|---|
| core (`.venv`) | builtin, CLI, tes core | `locks/core.lock` | 3.11/3.12 |
| `.envs/dc` | deepchecks + ppscore | `locks/dc.lock` | 3.11 |
| `.envs/cl` | cleanlab[datalab] | `locks/cl.lock` | 3.12 |
| `.envs/sg` | semgrep (aturan L6) | `locks/sg.lock` | 3.11+ |

```
make_env() { uv venv --python $2 $1 && uv pip install --python $1/bin/python --require-hashes --no-deps -r locks/$3.lock && uv pip install --python $1/bin/python --no-deps -e .; }
make_env .venv 3.12 core; make_env .envs/dc 3.11 dc; make_env .envs/cl 3.12 cl
.venv/bin/python examples/make_synthetic.py                     # data sintetis -> examples/data
# sunting examples/guard_m2.yaml: environments.<detektor> = path python env masing-masing
.venv/bin/leakage-guard run --config examples/guard_m2.yaml --out out
```

Exit code: `0` lolos, `1` ada CRITICAL tanpa waiver, `2` error runtime (fail-closed, termasuk interpreter hilang kecuali `detectors.allow_missing: true`). Perintah lain: `validate-config`, `explain`, `version`; dokumentasi lengkap (Inggris, situs Sphinx): `docs/index.md`, build: `.envs/docs/bin/sphinx-build -b html docs docs/_build/html`.

Docker (build dari lockfile, user non-root; jalankan tanpa jaringan): `docker/env-dc.Dockerfile`, `docker/env-cl.Dockerfile`.
```
docker build -f docker/env-dc.Dockerfile -t leakage-guard-dc .
docker run --rm --network none -v $PWD/work:/work leakage-guard-dc run --config /work/guard.yaml --out /work/out
```
Memasang deepchecks dan cleanlab di satu environment tidak disarankan; bila dipaksa, perlu `pyarrow<=19.0.1` dan `numpy<2` (detektor memberi peringatan, bukan error, bila tidak terpenuhi).

## Pencegahan
- `leakage_guard.prevention.splits`: `time_split`, `group_split`, `purged_kfold` (satuan hari).
- `leakage_guard.prevention.pipeline_integrity`: `score_gap`, `pipeline_integrity_findings` untuk dipanggil dari tes model.
- `rules/semgrep/ml-fit-before-split.yml`: heuristik L6, WARNING. Jalankan dengan daftar berkas eksplisit (`semgrep scan --config rules/semgrep a.py b.py`); memindai direktori dalam monorepo bisa memakan menit.

## Tes
```
.venv/bin/pytest -q                      # core + e2e tiga interpreter (e2e dilewati bila .envs tidak ada)
.envs/dc/bin/pytest -q tests/detectors   # deepchecks, ppscore
.envs/cl/bin/pytest -q tests/detectors   # cleanlab
.venv/bin/pytest -q tests/compat -m compat   # terjadwal, butuh jaringan: pin tetap harus gagal di luar batas
.venv/bin/python benchmarks/run_benchmark.py --rows 1000000   # AC-7
```
CI: `.github/workflows/ci.yml` (job core, env-dc, env-cl, e2e, pin-compat terjadwal). Pindahkan ke root repositori bila dipakai dalam monorepo.

## Memperluas
Detektor baru: kelas dengan `name` dan `run(ctx) -> list[RawFinding]`, didaftarkan dengan `@register`, tambahkan di `runners/_common.py::_MODULES`, `check_id` baru di `reasons/catalog.py` (template, `LEAKAGE_TYPE`, `THRESHOLD_BASIS`). Hook hasil gate: implementasikan `gate.GateHook` dan berikan ke `run_guard(hooks=[...])`.

Item `TODO(owner)`: lisensi, ambang yang belum dikalibrasi, konfirmasi regulasi (PSAK 109/71, OJK), pertanyaan terbuka SPEC bagian 16.
