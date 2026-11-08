# Laporan Milestone 4: Pengerasan

## 1. Selesai
- `locks/{core,dc,cl,sg}.lock` (+ `sg.in`), `docker/env-{dc,cl}.Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`.
- `tests/compat/test_pins.py`, `benchmarks/run_benchmark.py`, `README.md`, `docs/ARCHITECTURE.md`.
- `gate.GateHook` + parameter `hooks` di `run_guard`; peringatan pin di detektor deepchecks.
- `docs/DECISIONS.md`: D13 dan status akhir item bagian 5.

## 2. Perintah dan hasil
- `.venv/bin/pytest -q --cov`: 42 lulus, 3 dilewati (tes detektor, pustaka tidak ada di .venv), 3 compat dikecualikan; cakupan core 95% (target 85%).
- `ruff check`, `ruff format --check`, `mypy` (strict): bersih.
- `pytest -m compat`: 3 lulus (sklearn 1.8, setuptools 82, pandas 3 masih gagal terhadap deepchecks 0.19.1).
- `docker build` env-dc dan env-cl dari lockfile: berhasil; `docker run --network none`: import deepchecks+ppscore (py3.11) dan cleanlab (py3.12) berhasil; user uid 10001.
- Benchmark: 1.013.427 baris, 829,1 detik (13,8 menit), exit 1 (varian bocor, 8 CRITICAL).

## 3. Belum diuji / asumsi
- CI belum pernah berjalan di GitHub; pembangunan ulang dari lockfile (AC-6) hanya diuji lewat Docker, bukan di Actions.
- Pembangunan lockfile untuk Python 3.12 pada env dc, dan 3.11 pada env cl, tidak diuji; matriks 3.11/3.12 di CI hanya untuk job core.
- Satu kali ukur benchmark, dengan beban CPU lain; belum ada pengukuran ulang bersih.
- Jalur regresi; Python 3.13; pelatuk peringatan pin (kasus numpy>=2); semgrep belum dituning pada kode nyata.
- Image Docker belum menjalankan `leakage-guard run` end to end (hanya import).

## 4. Penyimpangan dari SPEC
- Tidak ada penyimpangan baru; lihat D10 untuk rule semgrep (Milestone 3).

## 5. Berikutnya
- Semua milestone selesai. Sisa: jalankan CI di GitHub, kalibrasi ambang pada data nyata, tuning semgrep, jawab `TODO(owner)`. Tidak ada pertanyaan yang memblokir.
