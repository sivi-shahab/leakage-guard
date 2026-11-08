# Laporan Milestone 2: Detektor Eksternal

## 1. Selesai
- `src/leakage_guard/detectors/{common,deepchecks_detector,ppscore_detector,cleanlab_detector}.py`; `builtin.py` memakai `common.py`.
- `src/leakage_guard/runners/` (runner subprocess per detektor); `orchestrator.py`, `config.py`, `reasons/catalog.py`, `detectors/base.py` (`attach_dir`) diperbarui.
- `tests/detectors/` (kontrak per detektor), `tests/integration/test_subprocess.py`, `tests/integration/test_e2e.py`; `examples/guard_m2.yaml`; kolom `region` bertipe campuran di data sintetis.
- `docs/DECISIONS.md`: D8 diperbarui, D9 ditambahkan.

## 2. Perintah dan hasil
- `.venv/bin/python -m pytest -q` (tanpa deepchecks/ppscore/cleanlab): 32 lulus, 3 dilewati (tes detektor, pustaka tidak terpasang). Tes e2e tiga interpreter ikut berjalan dan lulus.
- `.envs/dc/bin/python -m pytest -q tests/detectors`: 7 lulus, 1 dilewati (cleanlab).
- `.envs/cl/bin/python -m pytest -q tests/detectors`: 4 lulus, 2 dilewati (deepchecks, ppscore).
- Perbaikan: `tests/detectors/helpers.py` tidak mengimpor modul detektor sehingga tidak terdaftar (7 gagal di `dc`); kini diimpor.

## 3. Belum diuji / asumsi
- Skala (data besar) belum diukur; benchmark ada di Milestone 4.
- Ambang near-duplicate 0,13 default Cleanlab, belum dikalibrasi (D9).
- Belum diuji pada data kredit nyata; hanya data sintetis.
- Item bagian 5 SPEC: hanya data campuran yang diverifikasi lewat kolom `region`; sisanya belum dicek ulang satu per satu.

## 4. Penyimpangan dari SPEC
- Tidak ada penyimpangan baru; D8 dan D9 mencatat keputusan implementasi (isolasi subprocess, ambang default).

## 5. Berikutnya
- Milestone 3: `prevention/splits`, `prevention/pipeline_integrity`, aturan semgrep beserta tes dan ukuran false positive.
- Tidak ada pertanyaan yang memblokir.
