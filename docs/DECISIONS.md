# Decisions

Format: konteks, pilihan, alasan. Penyimpangan dari `SPEC.md` ditandai **[SPEC]**.

## D1. Berkas legacy tidak tersedia
- Konteks: `legacy/leakage_check.py` dan `legacy/deepchecks_leakage.py` tidak ada di mesin ini.
- Pilihan: detektor `builtin` ditulis dari SPEC 4.2; runner Deepchecks akan ditulis dari SPEC 4.3 (Milestone 2).
- Alasan: tidak ada sumber untuk di-port. Perilaku "dipertahankan dari legacy" tidak diklaim; ambang adalah default SPEC.

## D2. CLI memakai `argparse`
- Empat perintah kecil, tanpa dependensi tambahan.

## D3. Kuasi-identifier: k-anonimitas
- Pilihan: `privacy.min_group_size` default 5, dapat dikonfigurasi; temuan `quasi_identifier_risk` (WARNING).
- Alasan: SPEC 11 meminta kuasi-identifier dikelola, tanpa angka. Angka 5 adalah usulan, belum dikalibrasi. TODO(owner): konfirmasi bersama kepatuhan.

## D4. Kolom peran yang juga PII di-pseudonim, bukan di-drop
- Pilihan: jika `entity_col`/`time_col`/`index_col`/`target` ada di `pii_columns`, nilainya di-hash (SHA-256 terpotong) agar cek overlap tetap bekerja; kolom PII lain di-drop.
- Alasan: men-drop kolom entitas mematikan L2. Hash bukan anonimisasi (UU 27/2022 Pasal 4(3)(f)), jadi nilainya tetap tidak ditulis ke laporan.

## D5. Cek `adversarial` mengecualikan kolom peran
- Pilihan: `adversarial` hanya menilai fitur (bukan `time_col`, `entity_col`, `index_col`).
- Alasan: pada split out-of-time yang sah, `time_col` otomatis AUC 1,0 dan menimbulkan CRITICAL palsu (melanggar AC-2).

## D6. Severity `temporal_embargo` selalu WARNING dan hanya aktif bila `embargo_days > 0`.

## D7. Basis ambang dibawa sampai laporan
- `RawFinding.threshold_basis` dan teks alasan menyebut apakah ambang default Deepchecks, desain, atau terkalibrasi. Dapat di-override lewat `thresholds_basis` di config.

## D8. Detektor eksternal berjalan sebagai subprocess (Milestone 2)
- Pilihan: `deepchecks`, `ppscore`, `cleanlab` dijalankan oleh `leakage_guard.runners.<nama>` di interpreter `environments.<nama>` (`.envs/dc` untuk deepchecks+ppscore, `.envs/cl` untuk cleanlab). Hasil dikembalikan sebagai JSON; crash/timeout runner menghasilkan exit 2. Interpreter tidak ditemukan: exit 2, atau WARNING `detector_unavailable` bila `allow_missing: true`.
- Alasan: pin Deepchecks (pandas<2.3, dll.) bentrok dengan Cleanlab; isolasi proses memperbolehkan keduanya.

## D9. Ambang near-duplicate Cleanlab 0,13 adalah default, belum dikalibrasi
- Pilihan: `thresholds.near_dup_threshold` = 0,13 (default Cleanlab `near_duplicate`), `near_dup_cross_split` warn >0% / crit >=1% pasangan lintas split.
- Alasan: tidak ada data nyata untuk kalibrasi. Basis ambang dibawa ke laporan sebagai "default pustaka" (D7). TODO(owner): kalibrasi pada data kredit nyata.

## D10. Semgrep L6: rule diperketat, severity WARNING, environment terpisah
- Pilihan: `rules/semgrep/ml-fit-before-split.yml` hanya menandai `fit_transform`/`fit` pada data yang kemudian masuk `train_test_split` atau `cross_val_*` (klausa `train_test_split` kini diimplementasikan). `severity: WARNING`. Semgrep dipasang di `.envs/sg` (di luar core).
- Penyimpangan dari SPEC 6.2 **[SPEC]**: rule contoh SPEC (`pattern-not-inside: Pipeline(...)`) menandai pemakaian benar; diganti pola berurutan di atas.
- Batas: heuristik intra-fungsi/berkas; tidak melacak data lewat fungsi lain atau atribut. Tuning pada kode nyata belum dilakukan.

## D11. Pipeline integrity: gap skor CV, ambang desain
- `thresholds.pipeline_gap` warn 0,02 / crit 0,05 (desain, belum dikalibrasi). Varian bocor = langkah preprocessing di-fit pada seluruh data, lalu CV estimator akhir. Artifact yang bukan `Pipeline` (>=2 langkah) atau tidak bisa di-clone memunculkan `TypeError` (bukan temuan).
- Belum terhubung ke CLI/orkestrator: ini utilitas uji untuk dipanggil dari tes proyek model.

## D12. Satuan split dalam hari
- `prevention/splits` memakai hari; `purged_kfold` internal (bukan skfolio). Konversi ke observasi untuk pustaka lain = hari × baris/hari.
