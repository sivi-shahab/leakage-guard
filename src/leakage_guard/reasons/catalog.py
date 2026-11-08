"""Reason templates per ``check_id`` (SPEC 5.1) and threshold bases (SPEC 5).

Placeholders use ``{name}`` or ``{name:format_spec}`` and are resolved from the base keys
(``BASE_KEYS``) plus the evidence keys the detector is guaranteed to provide
(``evidence_keys``). Language: Indonesian.
"""

from __future__ import annotations

from dataclasses import dataclass

from leakage_guard.models import ThresholdBasis

# Keys the engine always provides.
BASE_KEYS = frozenset({"column", "target", "value", "threshold", "metric_name", "prediction_date"})

THRESHOLD_BASIS: dict[str, ThresholdBasis] = {
    "row_overlap": "design",
    "group_overlap": "design",
    "temporal": "design",
    "temporal_embargo": "design",
    "single_feature": "design",
    "pps_train": "deepchecks_default",  # CRITICAL=0.8 equals Deepchecks default; WARNING is design
    "identifier_label": "design",
    "suspicious_names": "design",
    "blocklist_hit": "design",
    "adversarial": "design",
    "near_dup_cross_split": "design",
    "label_errors": "design",
    "date_shared": "design",
    "pps_blind_spot": "design",
    "pipeline_integrity": "design",
    "detector_unavailable": "design",
    "orphan_waiver": "design",
    "quasi_identifier_risk": "design",
}

LEAKAGE_TYPE: dict[str, str | None] = {
    "row_overlap": "L1",
    "group_overlap": "L2",
    "temporal": "L3",
    "temporal_embargo": "L3",
    "single_feature": "L4",
    "pps_train": "L4",
    "suspicious_names": "L4",
    "blocklist_hit": "L4",
    "identifier_label": "L5",
    "pipeline_integrity": "L6",
    "adversarial": "L7",
    "near_dup_cross_split": "L8",
    "label_errors": "L8",
    "date_shared": "L3",
    "pps_blind_spot": None,
    "detector_unavailable": None,
    "orphan_waiver": None,
    "quasi_identifier_risk": None,
}

# Checks whose evidence is an explicit rule / exact match -> confidence "high" on their own.
EXPLICIT_RULE_CHECKS = frozenset({"blocklist_hit", "row_overlap"})


@dataclass(frozen=True)
class ReasonTemplate:
    summary: str
    why_leakage: str
    impact: str
    likely_root_causes: tuple[str, ...]
    remediation: tuple[str, ...]
    verification_question: str
    evidence_keys: frozenset[str] = frozenset()


_IMPACT = (
    "Metrik evaluasi (AUC, KS, Gini) terlalu optimis; performa produksi diperkirakan lebih rendah."
)

CATALOG: dict[str, ReasonTemplate] = {
    "row_overlap": ReasonTemplate(
        summary="{pct_test_rows:.2f}% baris test identik dengan baris di train.",
        why_leakage=(
            "Sebanyak {n_duplicate_rows} baris test ({pct_test_rows:.2f}% dari test) identik dengan "
            "baris train pada {n_columns_compared} kolom yang dibandingkan. Model dinilai pada contoh "
            "yang sudah pernah dilihatnya, sehingga metrik test terlalu optimis."
        ),
        impact=_IMPACT,
        likely_root_causes=(
            "Duplikasi di sumber data",
            "Join yang menggandakan baris",
            "Oversampling atau augmentasi dilakukan sebelum split",
        ),
        remediation=(
            "Dedup sebelum split",
            "Lakukan oversampling hanya pada data training setelah split",
        ),
        verification_question="Apakah baris-baris ini memang aplikasi yang sama yang tercatat dua kali?",
        evidence_keys=frozenset({"n_duplicate_rows", "pct_test_rows", "n_columns_compared"}),
    ),
    "group_overlap": ReasonTemplate(
        summary="{pct_test_entities:.2f}% data test memakai entitas yang juga ada di train.",
        why_leakage=(
            "Sebesar {pct_test_entities:.2f}% data test memakai entitas yang juga muncul di train. "
            "Perilaku dan profil entitas itu ikut terbawa, sehingga model bisa mengenali "
            "entitasnya, bukan mempelajari pola risiko. Sampel test tidak independen."
        ),
        impact=_IMPACT,
        likely_root_causes=(
            "Satu nasabah punya banyak produk atau snapshot bulanan",
            "Split acak per baris",
        ),
        remediation=(
            "Split berbasis entitas (GroupKFold)",
            "Pastikan tiap entitas hanya berada di satu split",
        ),
        verification_question="Apakah satu entitas boleh muncul di train dan test menurut desain validasi?",
        evidence_keys=frozenset({"pct_test_entities"}),
    ),
    "temporal": ReasonTemplate(
        summary="{pct_test_before_train_max:.2f}% baris test lebih lama dari data train terakhir.",
        why_leakage=(
            "Sebagian data test ({pct_test_before_train_max:.2f}%) bertanggal sebelum tanggal train "
            "terakhir ({train_max}; test paling awal {test_min}). Model dilatih dengan kondisi yang di "
            "dunia nyata belum terjadi saat keputusan diambil."
        ),
        impact=_IMPACT,
        likely_root_causes=("Random split pada data berurutan waktu",),
        remediation=("Split out-of-time", "Tambahkan embargo"),
        verification_question="Apakah split memang dimaksudkan out-of-time?",
        evidence_keys=frozenset({"train_max", "test_min", "pct_test_before_train_max"}),
    ),
    "temporal_embargo": ReasonTemplate(
        summary="Jarak train-test {gap_days} hari, kurang dari embargo {embargo_days} hari.",
        why_leakage=(
            "Jarak antara akhir train dan awal test adalah {gap_days} hari, lebih kecil dari embargo "
            "{embargo_days} hari. Fitur berjendela dan label yang baru matang di akhir train "
            "bertumpang tindih dengan awal test."
        ),
        impact=_IMPACT,
        likely_root_causes=("Split dipotong tepat di batas tanggal tanpa jeda",),
        remediation=("Sisipkan jeda sebesar jendela fitur terpanjang atau maturity window",),
        verification_question="Berapa jendela fitur terpanjang dan maturity window model ini?",
        evidence_keys=frozenset({"gap_days", "embargo_days"}),
    ),
    "single_feature": ReasonTemplate(
        summary="{column} hampir menentukan {target}; kemungkinan informasi pasca-outcome.",
        why_leakage=(
            "Fitur `{column}` memprediksi target `{target}` dengan {metric_name} {value:.3f} "
            "(ambang {threshold}), padahal fitur teratas lain hanya mencapai {next_best_score:.3f}. "
            "Pada data risiko kredit yang nyata, satu fitur hampir tidak pernah cukup memprediksi gagal "
            "bayar kecuali nilainya diturunkan dari target atau baru tercatat setelah outcome diketahui."
        ),
        impact=_IMPACT,
        likely_root_causes=(
            "Fitur dicatat setelah outcome diketahui (pasca-outcome)",
            "Fitur diturunkan dari target atau dari status kredit akhir",
        ),
        remediation=(
            "Telusuri lineage dan available_at kolom ini",
            "Gunakan nilai snapshot pada prediction_date atau hapus kolom dari fitur",
        ),
        verification_question="Apakah nilai {column} sudah tersedia pada {prediction_date}?",
        evidence_keys=frozenset({"score", "next_best_score"}),
    ),
    "pps_train": ReasonTemplate(
        summary="PPS {column} terhadap {target} = {pps_train:.2f}.",
        why_leakage=(
            "Predictive Power Score fitur `{column}` terhadap `{target}` adalah {pps_train:.2f}. "
            "Skor mendekati 1 berarti fitur itu hampir menentukan target."
        ),
        impact=_IMPACT,
        likely_root_causes=("Sama seperti single_feature",),
        remediation=("Telusuri lineage dan available_at kolom ini",),
        verification_question="Apakah nilai {column} sudah tersedia pada {prediction_date}?",
        evidence_keys=frozenset({"pps_train"}),
    ),
    "identifier_label": ReasonTemplate(
        summary="Kolom ID {column} berkorelasi dengan {target} (PPS {pps_value:.2f}).",
        why_leakage=(
            "Kolom identitas `{column}` memiliki PPS {pps_value:.2f} terhadap target. ID berurutan "
            "menyandi waktu, kanal, atau produk, sehingga model belajar kapan atau lewat mana, bukan "
            "risiko nasabah."
        ),
        impact=_IMPACT,
        likely_root_causes=(
            "ID dipakai sebagai fitur",
            "Penomoran berbeda per periode atau produk",
        ),
        remediation=("Keluarkan ID dari matriks fitur",),
        verification_question="Apakah {column} dipakai sebagai fitur model?",
        evidence_keys=frozenset({"pps_value"}),
    ),
    "suspicious_names": ReasonTemplate(
        summary="Nama kolom {column} cocok pola '{matched_pattern}'.",
        why_leakage=(
            "Nama kolom `{column}` cocok dengan pola `{matched_pattern}` yang mengisyaratkan informasi "
            "pasca-outcome. Ini hanya petunjuk dari penamaan, bukan bukti."
        ),
        impact="Jika kolom memang pasca-outcome, metrik evaluasi terlalu optimis.",
        likely_root_causes=("Penamaan kolom turunan dari status kredit",),
        remediation=(
            "Konfirmasi kapan nilai kolom tersedia",
            "Jika pasca-outcome, masukkan ke forbidden_columns",
        ),
        verification_question="Apakah nilai {column} sudah tersedia pada {prediction_date}?",
        evidence_keys=frozenset({"matched_pattern"}),
    ),
    "blocklist_hit": ReasonTemplate(
        summary="Kolom terlarang {column} dipakai sebagai fitur.",
        why_leakage=(
            "Kolom `{column}` terdaftar di forbidden_columns karena pasti diketahui setelah titik "
            "prediksi, tetapi ada di fitur."
        ),
        impact=_IMPACT,
        likely_root_causes=("Fitur ikut terbawa dari tabel sumber yang berisi kolom outcome",),
        remediation=("Hapus kolom dari fitur", "Perbaiki query atau feature store sumber"),
        verification_question="Mengapa {column} masih ada di fitur padahal terdaftar terlarang?",
        evidence_keys=frozenset({"blocklist_entry"}),
    ),
    "adversarial": ReasonTemplate(
        summary="Fitur {column} membedakan train dari test (AUC {auc:.3f}).",
        why_leakage=(
            "Fitur `{column}` saja dapat membedakan data train dari test dengan AUC {auc:.3f} "
            "(ambang {threshold}). Distribusi keduanya berbeda secara sistematis, sehingga skor test "
            "tidak mewakili populasi training."
        ),
        impact="Skor test tidak mewakili populasi training.",
        likely_root_causes=(
            "Split non-acak",
            "Drift antar periode",
            "Fitur menyandi tanggal atau ID",
        ),
        remediation=(
            "Periksa fitur penanda",
            "Gunakan split yang disengaja (out-of-time) dan dokumentasikan drift yang diharapkan",
        ),
        verification_question="Apakah perbedaan distribusi {column} antara train dan test disengaja?",
        evidence_keys=frozenset({"auc"}),
    ),
    "near_dup_cross_split": ReasonTemplate(
        summary="{n_sets_cross_split} himpunan near-duplicate lintas split.",
        why_leakage=(
            "Ada {n_sets_cross_split} himpunan sampel hampir identik yang anggotanya ada di train dan "
            "test ({pct_test_rows:.2f}% baris test). Efeknya sama dengan duplikat persis, tetapi lolos "
            "dari pemeriksaan hash."
        ),
        impact=_IMPACT,
        likely_root_causes=("Snapshot berulang per nasabah", "Entri ganda dengan variasi kecil"),
        remediation=("Split berbasis entitas atau waktu", "Dedup near-duplicate sebelum split"),
        verification_question="Apakah sampel-sampel ini merepresentasikan entitas yang sama?",
        evidence_keys=frozenset({"n_sets_cross_split", "pct_test_rows"}),
    ),
    "label_errors": ReasonTemplate(
        summary="{n_label_issues} baris train diduga salah label.",
        why_leakage=(
            "Cleanlab menandai {n_label_issues} baris train ({pct_train_rows:.2f}%) sebagai kemungkinan "
            "salah label. Ini masalah kualitas label, bukan kebocoran antar split; dilaporkan sebagai "
            "informasi dan tidak memblokir."
        ),
        impact="Label yang salah menurunkan kualitas model dan membuat evaluasi tidak andal.",
        likely_root_causes=("Kesalahan pelabelan", "Definisi target tidak konsisten antar periode"),
        remediation=("Tinjau sampel yang ditandai bersama pemilik data",),
        verification_question="Apakah definisi target konsisten untuk seluruh periode data?",
        evidence_keys=frozenset({"n_label_issues", "pct_train_rows"}),
    ),
    "date_shared": ReasonTemplate(
        summary="{pct_test_dates_shared:.1f}% tanggal test juga ada di train.",
        why_leakage=(
            "Sebesar {pct_test_dates_shared:.1f}% tanggal di test juga muncul di train. Metrik ini "
            "mengukur tanggal bersama, bukan urutan waktu, dan menyala pada hampir semua split acak. "
            "Gunakan `temporal` untuk memeriksa apakah test lebih lama dari train."
        ),
        impact="Indikasi pendukung bahwa split tidak memisahkan periode.",
        likely_root_causes=("Random split pada data berurutan waktu",),
        remediation=("Gunakan split out-of-time", "Tambahkan embargo"),
        verification_question="Apakah split dimaksudkan memisahkan periode waktu?",
        evidence_keys=frozenset({"pct_test_dates_shared"}),
    ),
    "pps_blind_spot": ReasonTemplate(
        summary="PPS tidak dapat menilai kolom ID {column}.",
        why_leakage=(
            "Kolom `{column}` bertipe kategorikal/string dengan nilai unik, sehingga PPS selalu "
            "bernilai 0 dan tidak dapat mendeteksi korelasi ID dengan target. Ini batasan alat, bukan "
            "temuan kebocoran."
        ),
        impact="Kebocoran lewat ID string tidak terdeteksi oleh PPS.",
        likely_root_causes=("ID bertipe string",),
        remediation=("Gunakan detektor lain atau ubah ID menjadi numerik berurutan untuk diuji",),
        verification_question="Apakah ID ini berurutan dan menyandi waktu atau kanal?",
        evidence_keys=frozenset({"id_dtype"}),
    ),
    "pipeline_integrity": ReasonTemplate(
        summary="Selisih skor CV pipeline benar vs varian bocor = {score_gap:.3f}.",
        why_leakage=(
            "Skor CV varian yang di-fit pada data penuh berbeda {score_gap:.3f} dari pipeline yang "
            "benar. Langkah preprocessing yang belajar dari seluruh data membawa statistik test ke "
            "training."
        ),
        impact=_IMPACT,
        likely_root_causes=(
            "Transformer di-fit sebelum split",
            "Target encoding tanpa out-of-fold",
        ),
        remediation=(
            "Pindahkan semua transformer ke dalam Pipeline",
            "Hitung encoding out-of-fold",
        ),
        verification_question="Apakah ada transformer yang di-fit sebelum split?",
        evidence_keys=frozenset({"score_gap"}),
    ),
    "detector_unavailable": ReasonTemplate(
        summary="Detektor {detector} tidak tersedia.",
        why_leakage=(
            "Detektor `{detector}` tidak dapat dijalankan ({error}). Cakupan pemeriksaan berkurang: "
            "kebocoran yang hanya dideteksi alat ini tidak terperiksa. Ini bukan temuan kebocoran."
        ),
        impact="Cakupan pemeriksaan kebocoran lebih sempit dari yang dikonfigurasi.",
        likely_root_causes=(
            "Environment detektor belum dipasang",
            "Interpreter salah dikonfigurasi",
        ),
        remediation=("Pasang environment detektor", "Periksa environments di guard.yaml"),
        verification_question="Apakah menjalankan gate tanpa detektor ini dapat diterima?",
        evidence_keys=frozenset({"detector", "error"}),
    ),
    "orphan_waiver": ReasonTemplate(
        summary="Waiver untuk {waiver_finding_id} tidak cocok dengan temuan apa pun.",
        why_leakage=(
            "Waiver `{waiver_finding_id}` tidak cocok dengan temuan pada run ini. Ini bukan temuan "
            "kebocoran; waiver yatim sebaiknya dibersihkan agar tidak menutupi temuan di masa depan."
        ),
        impact="Waiver yatim dapat tanpa sengaja membungkam temuan yang muncul kemudian.",
        likely_root_causes=("Kebocoran sudah diperbaiki", "Kolom atau check_id berganti nama"),
        remediation=("Hapus waiver dari waivers.yaml",),
        verification_question="Apakah waiver ini masih diperlukan?",
        evidence_keys=frozenset({"waiver_finding_id"}),
    ),
    "quasi_identifier_risk": ReasonTemplate(
        summary="Kombinasi kuasi-identifier menghasilkan kelompok kecil (minimum {min_group_size}).",
        why_leakage=(
            "Kombinasi kolom kuasi-identifier menghasilkan {n_small_groups} kelompok dengan ukuran di "
            "bawah {k_threshold} (terkecil {min_group_size}). Menurut UU 27/2022 Pasal 4 ayat (3) huruf "
            "f, kombinasi atribut yang dapat mengidentifikasi seseorang adalah data pribadi. Ini bukan "
            "temuan kebocoran model."
        ),
        impact="Risiko re-identifikasi bila artefak laporan atau data kerja bocor.",
        likely_root_causes=("Atribut demografis atau geografis terlalu rinci",),
        remediation=(
            "Generalisasi atau gabungkan kategori kuasi-identifier",
            "Batasi akses artefak",
        ),
        verification_question="Apakah kolom-kolom ini perlu dikelola sebagai data pribadi?",
        evidence_keys=frozenset({"min_group_size", "k_threshold", "n_small_groups"}),
    ),
}
