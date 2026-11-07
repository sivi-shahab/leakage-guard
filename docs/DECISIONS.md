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

## D8. Detektor eksternal belum ada di Milestone 1
- `detectors.enabled` yang memuat nama selain `builtin` menghasilkan exit 2, atau WARNING `detector_unavailable` bila `allow_missing: true`. Interpreter di `environments.<name>` memicu error "belum diimplementasikan" sampai Milestone 2.
