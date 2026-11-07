# ML Leakage Guard: Spesifikasi

| | |
|---|---|
| **Versi** | 1.2 (draft untuk review): koreksi hasil verifikasi sumber primer (lihat Catatan Perubahan) |
| **Tanggal** | 7 November 2026 |
| **Cakupan** | Deteksi dan pencegahan data leakage di pipeline ML (train/test bocor, fitur "mengintip" target) |
| **Konteks utama** | Model tabular untuk credit scoring dan AML di lingkungan perbankan Indonesia |

---

## 1. Latar Belakang dan Tujuan

Data leakage membuat metrik evaluasi (AUC, KS, Gini) terlihat bagus di tahap pengembangan, tetapi performa jatuh di produksi. Di konteks perbankan, dampaknya lebih serius dari sekadar akurasi: model yang bocor bisa lolos validasi model risk, menghasilkan cadangan kerugian (PSAK 109 Instrumen Keuangan; penomoran lama PSAK 71, hubungan keduanya perlu dikonfirmasi dari dokumen resmi IAI/OJK) yang salah, dan sulit dipertanggungjawabkan saat audit OJK.

Sistem ini, **ML Leakage Guard**, adalah *quality gate* yang berjalan otomatis di pipeline training dan retraining untuk:

1. **Mendeteksi** leakage antar split dan leakage fitur terhadap target.
2. **Mencegah** leakage dari preprocessing lewat standar implementasi dan pengujian.
3. **Menghasilkan bukti** (laporan terstruktur) yang bisa dilampirkan ke dokumentasi validasi model.
4. **Memblokir** promosi model ke tahap berikutnya jika ada temuan kritis yang belum diwaiver.
5. **Menjelaskan alasan** setiap temuan: kenapa data atau fitur tersebut dianggap leakage, bukti angkanya, dampaknya, kemungkinan akar masalah, dan langkah perbaikan (bagian 5.1).

### Bukan tujuan (non-goals)

- Mendeteksi kebocoran data sensitif (PII/secret). Itu lingkup terpisah (Presidio, gitleaks, dll).
- Menggantikan validasi model independen oleh tim model risk.
- Mendeteksi leakage pada data tidak terstruktur (teks, gambar, audio) di versi 1.0.
- Memperbaiki leakage secara otomatis. Sistem hanya mendeteksi, melaporkan, dan memblokir.

---

## 2. Taksonomi Leakage yang Ditangani

| Kode | Jenis | Contoh di credit scoring | Dideteksi oleh |
|---|---|---|---|
| L1 | **Duplikasi baris** train/test | Aplikasi yang sama tercatat dua kali dan jatuh di split berbeda | Deepchecks `TrainTestSamplesMix`, `leakage_check.py`, Cleanlab (near-duplicate) |
| L2 | **Overlap entitas** | Satu nasabah punya banyak baris (banyak produk atau snapshot bulanan), tersebar di train dan test | `leakage_check.py` (group overlap) sebagai sumber utama; Deepchecks `IndexTrainTestLeakage` dengan `index_name` = kolom entitas (`entity_col`) sebagai pendukung (lihat 4.3) |
| L3 | **Leakage temporal** | Data test lebih lama dari data train terakhir, sehingga model "melihat masa depan" | Deepchecks `DateTrainTestLeakageOverlap`, `leakage_check.py` (temporal). `DateTrainTestLeakageDuplicates` mengukur tanggal bersama, bukan urutan waktu (lihat 4.3) |
| L4 | **Target leakage (fitur)** | Fitur kolektibilitas, DPD, atau status restrukturisasi yang baru diketahui setelah titik prediksi | ppscore, Deepchecks `FeatureLabelCorrelation`, `leakage_check.py` (single-feature), blocklist nama kolom |
| L5 | **Identifier leakage** | ID/nomor aplikasi berurutan yang berkorelasi dengan target | Deepchecks `IdentifierLabelCorrelation` (hanya memeriksa kolom `index` dan `datetime`) |
| L6 | **Preprocessing leakage** | Scaler, imputer, atau target encoder di-fit sebelum split | `Pipeline` wajib, semgrep rule, *pipeline integrity test* |
| L7 | **Split tidak i.i.d. / drift** | Test diambil dari periode atau segmen berbeda secara tidak sengaja | Adversarial validation (`leakage_check.py`), Deepchecks drift checks |
| L8 | **Label error / near-duplicate lintas split** | Label yang sama-sama salah, atau sampel hampir identik di train dan test | Cleanlab Datalab |

> L6 tidak bisa dideteksi dari data. Ia hanya bisa dicegah lewat disiplin implementasi dan diuji lewat kode, sehingga ditangani terpisah di bagian 6.

---

## 3. Arsitektur

### 3.1 Prinsip

- **Banyak detektor, satu laporan.** Tiap alat punya blind spot. Hasilnya dinormalisasi ke satu format temuan.
- **Environment terisolasi per alat.** Terbukti ada konflik dependensi (bagian 3.3), sehingga detektor dijalankan sebagai langkah terpisah yang bertukar data lewat berkas, bukan di satu proses Python.
- **Fail-closed untuk temuan kritis.** Exit code non-nol menghentikan pipeline.
- **Tidak ada PII di laporan.** Kolom identitas mentah di-drop sebelum dianalisis.

### 3.2 Alur

```
 train.parquet ──┐
 test.parquet  ──┤
 guard.yaml    ──┘
        │
        ▼
 ┌──────────────────────┐
 │ 0. Preflight         │  validasi skema, drop kolom PII, tentukan peran kolom
 └──────────┬───────────┘
            ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ Detektor (job terpisah, environment terisolasi, paralel)     │
 │  A. custom   : leakage_check.py       → findings_custom.json │
 │  B. deepchecks: deepchecks_leakage.py → findings_dc.json     │
 │  C. ppscore  : ppscore_check.py       → findings_pps.json    │
 │  D. cleanlab : datalab_check.py       → findings_cl.json     │
 └──────────┬───────────────────────────────────────────────────┘
            ▼
 ┌──────────────────────┐
 │ 1. Aggregator        │  normalisasi + dedup + waiver + reason → report.json / report.md
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │ 2. Gate              │  exit 0 (lolos) / 1 (blok) → CI/CD, MLflow tag, tiket
 └──────────────────────┘
```

### 3.3 Environment dan dependensi

Hasil pengujian pada 7 November 2026 menunjukkan konflik yang harus dihormati desainnya:

| Environment | Isi | Pin yang wajib |
|---|---|---|
| `env-dc` (Deepchecks, ppscore, custom) | `deepchecks==0.19.1`, `ppscore`, `scikit-learn`, `pandas` | `scikit-learn<1.6`, `numpy<2`, `pandas<2.3`, `setuptools<81`, `pyarrow<=19.0.1` |
| `env-cl` (Cleanlab Datalab) | `cleanlab[datalab]` | tanpa pin `numpy<2` |

Versi Python yang diuji: 3.11 dan 3.12 (disarankan). Python 3.13 belum diuji.

Temuan yang mendasari tabel di atas:

- Pin di tabel bersifat **konservatif**. Pada uji, yang gagal adalah `scikit-learn>=1.8`, `pandas>=3`, `setuptools>=82`, dan `numpy>=2`; `scikit-learn` 1.6.1 dan 1.7.2, `pandas` 2.3.3, dan `setuptools` 81 masih lolos pada satu skenario klasifikasi kecil. Pelonggaran harus diuji ulang pada data nyata (termasuk jalur regresi) sebelum dipakai.
- Alasan `scikit-learn<1.6`: scorer `max_error` deprecated sejak 1.6 dan dihapus di 1.8, sehingga Deepchecks 0.19.1 gagal di-import. Deepchecks juga memerlukan `pkg_resources` dari setuptools.
- `pyarrow` versi terbaru butuh NumPy 2 sehingga tidak bisa dipasang bersama `numpy<2`. Versi 17.0.0, 18.1.0, dan 19.0.1 diuji berfungsi untuk baca/tulis Parquet dengan `numpy<2`.
- `cleanlab[datalab]` (cleanlab 2.9.0) **dapat dipasang bersama** Deepchecks di `env-dc` bila `pyarrow<=19.0.1` dan `numpy<2` dipin (diuji 7 November 2026), dan `Datalab.find_issues` berjalan. `env-cl` tetap dipisahkan agar rilis `datasets`/`pyarrow` baru tidak memaksa `numpy>=2` ke `env-dc`.

Konsekuensi: **tiap environment dibangun sebagai container image atau virtualenv terpisah** dengan lockfile (`uv.lock` atau `requirements.lock`). Pertukaran data hanya lewat Parquet (input) dan JSON (output).

---

## 4. Komponen

### 4.1 Preflight

**Tanggung jawab:** menyiapkan input yang aman dan konsisten sebelum detektor berjalan.

- Validasi skema (nama kolom, tipe, target ada, split tidak kosong). Great Expectations atau Pandera boleh dipakai di sini.
- Drop kolom pada `pii_columns` (misalnya `nik`, `npwp`, `nama`, `no_rekening`) sebelum disalin ke area kerja detektor.
- Menentukan **peran kolom** dari konfigurasi: `target`, `entity`, `time`, `index`, `blocklist`, `features`.
- Menolak jalan jika `train` dan `test` punya kolom yang berbeda, atau target hanya punya satu kelas.

### 4.2 Detektor A: custom (`leakage_check.py`, sudah ada)

Dependensi minimal (pandas, numpy, scikit-learn). Memeriksa: row overlap, group overlap, temporal overlap, nama kolom mencurigakan, single-feature leakage (pohon kedalaman 3 dengan CV, mirip PPS secara konsep; PPS memakai pohon tanpa batas kedalaman, CV 4-fold, dan F1 ternormalisasi untuk klasifikasi), dan adversarial validation. Berperan sebagai *baseline* tanpa dependensi berat dan sebagai cadangan jika alat lain gagal dipasang.

### 4.3 Detektor B: Deepchecks (`deepchecks_leakage.py`, sudah ada)

Menjalankan suite `train_test_validation` ditambah `FeatureLabelCorrelation` (ambang PPS 0,8 = default Deepchecks) dan `IdentifierLabelCorrelation` (ambang 0,2 = pilihan desain; default Deepchecks 0). Menghasilkan laporan HTML untuk lampiran audit dan ringkasan JSON. Diuji pada data sintetis dengan kebocoran yang disengaja, dan semua kebocoran tertangkap.

Catatan teknis dari uji coba:

- `Suite.run()` pada versi 0.19.1 tidak punya parameter `n_samples`. Sampling dilakukan di skrip.
- Cek leakage tanggal dan indeks hanya aktif bila `time` dan `index` didefinisikan di `Dataset`.
- Ambang bawaan sangat ketat (leakage tanggal harus 0%). Pada split acak hampir pasti gagal, dan itu perilaku yang diinginkan.
- **Peran `index` dan L2.** `IndexTrainTestLeakage` membandingkan nilai kolom `index_name`. Uji: `index_name=application_id` menghasilkan overlap 0, `index_name=customer_id` menghasilkan 0,577. Sementara `IdentifierLabelCorrelation` (L5) hanya memeriksa kolom `index` dan `datetime`, dan butuh `index_name` = ID berurutan (`index_col`). Satu `Dataset` hanya punya satu `index_name`, sehingga skrip harus menjalankan dua pemanggilan dengan dua `Dataset`: (1) `index_name = entity_col` untuk L2; (2) `index_name = index_col` untuk L5 (dan duplikasi aplikasi, mendekati L1). `group_overlap` dari `leakage_check.py` tetap menjadi sumber utama L2.
- **L3.** `DateTrainTestLeakageOverlap` sepadan dengan `temporal` di bagian 5. `DateTrainTestLeakageDuplicates` mengukur tanggal bersama (bukan urutan waktu) dan akan menyala pada hampir semua split acak, sehingga bukan padanan `temporal`.

### 4.4 Detektor C: ppscore (`ppscore_check.py`, perlu dibuat)

Menghitung Predictive Power Score tiap fitur terhadap target dengan `pps.predictors(df, y=target)`. Diuji berfungsi di `env-dc`: pada data sintetis, fitur bocor mendapat skor 1,0 dan fitur lain 0,0.

Spesifikasi:

- Input: Parquet train, daftar `features`, `target`.
- Hitung hanya pada **train**, lalu hitung ulang pada **test** untuk membandingkan konsistensi.
- Sampling maksimum 100.000 baris: `sample=` (default ppscore 5.000) harus diteruskan eksplisit ke `pps.predictors`. Seed memakai parameter `random_seed`.
- Output temuan `L4` per fitur dengan skor PPS.
- Blind spot: kolom kategorikal dengan nilai unik memperoleh skor 0, sehingga PPS tidak mendeteksi ID bertipe string. Deteksi L5 lewat ppscore hanya bekerja untuk ID numerik.
- Catatan: Deepchecks memakai modul PPS internalnya sendiri (`deepchecks/ppscore.py`), bukan paket PyPI `ppscore`. Paket `ppscore` hanya dibutuhkan oleh detektor C ini.
- Peringatan: ppscore dirilis jarang (1.3.0 Oktober 2022, 1.3.1 Maret 2026). Karena itu pin versi dipelihara dan `leakage_check.py` menyediakan padanan tanpa dependensi; ppscore diposisikan sebagai pembanding, bukan satu-satunya sumber.

### 4.5 Detektor D: Cleanlab Datalab (`datalab_check.py`, perlu dibuat)

Berjalan di `env-cl`. **Status: rancangan, belum diuji** karena dependensinya tidak terpasang di lingkungan uji.

Rancangan:

1. Gabungkan train dan test dalam satu frame, tambahkan kolom `__split__` (`train`/`test`).
2. Bentuk matriks fitur numerik (encoding kategori dilakukan di Preflight).
3. Jalankan `Datalab(data=df, label_name=target)` lalu `find_issues(features=X, issue_types={"near_duplicate": {}, "label": {}, "outlier": {}})`.
4. Dari hasil `near_duplicate`, ambil himpunan near-duplicate yang **anggotanya mencakup train dan test sekaligus**. Itulah temuan `L8`.
5. Temuan `label` (label error) pada train dilaporkan sebagai INFO atau WARNING, bukan blocker.

Yang harus diverifikasi saat implementasi: nama kolom hasil (`near_duplicate_sets`), perilaku pada data tabular campuran, dan waktu eksekusi pada data berukuran jutaan baris (gunakan sampling bila perlu).

### 4.6 Aggregator

Menggabungkan keluaran semua detektor ke satu skema (bagian 9), menghapus duplikasi temuan yang sama dari alat berbeda (kunci: `check_id` + `column`/`scope`), menerapkan waiver yang masih berlaku, **menambahkan blok `reason` pada tiap temuan lewat Reason Engine (bagian 5.1)**, lalu menulis `report.json` dan `report.md`.

### 4.7 Gate

Mengembalikan exit code berdasarkan temuan yang belum diwaiver (bagian 8). Diintegrasikan ke CI/CD dan, jika dipakai, ke tag MLflow pada run model (`leakage_guard=passed|failed`).

---

## 5. Katalog Pemeriksaan dan Ambang

Semua ambang dapat dikonfigurasi di `guard.yaml`. Nilai di bawah adalah default yang diusulkan, bukan hasil kalibrasi pada data produksi. Kolom "Basis ambang": **default Deepchecks** (nilai sama dengan default alat), **desain** (pilihan desain tanpa dasar sumber), atau **kalibrasi** (setelah dikalibrasi pada model historis, fase 4).

| ID | Pemeriksaan | WARNING jika | CRITICAL jika | Basis ambang |
|---|---|---|---|---|
| `row_overlap` | Persentase baris test yang identik dengan baris train | > 0% | ≥ 1% | desain (kondisi default Deepchecks `TrainTestSamplesMix`: 5%) |
| `group_overlap` | Entitas yang muncul di train dan test | n/a | > 0 entitas (jika `entity` didefinisikan) | desain (konsisten dengan default `IndexTrainTestLeakage`: 0) |
| `temporal` | Persentase baris test bertanggal sebelum maksimum train | > 0% | ≥ 5% | desain (default Deepchecks Date*: 0) |
| `temporal_embargo` | Jarak antara akhir train dan awal test kurang dari `embargo_days` | selalu | n/a | desain |
| `single_feature` | ROC-AUC (atau R²) fitur tunggal terhadap target | ≥ 0,85 | ≥ 0,95 | desain (detektor custom) |
| `pps_train` | PPS fitur terhadap target | ≥ 0,5 | ≥ 0,8 | CRITICAL = default Deepchecks `FeatureLabelCorrelation`; WARNING = desain |
| `identifier_label` | PPS kolom ID terhadap target | ≥ 0,1 | ≥ 0,2 | desain (default Deepchecks: 0) |
| `suspicious_names` | Kolom cocok pola blocklist | selalu | n/a | desain |
| `blocklist_hit` | Kolom pada `forbidden_columns` ada di fitur | n/a | selalu | desain |
| `adversarial` | AUC fitur tunggal membedakan train dari test | ≥ 0,70 | ≥ 0,95 | desain (lihat catatan di bawah) |
| `near_dup_cross_split` | Himpunan near-duplicate lintas split | > 0 | ≥ 1% dari test | desain (`threshold=0.13` Cleanlab mengatur kedekatan, bukan batas jumlah) |
| `pipeline_integrity` | Uji integritas preprocessing (bagian 6) | n/a | gagal | desain |

Catatan `adversarial`: AUC fitur tunggal berbeda dari `MultivariateDrift` Deepchecks, yang melatih klasifier domain atas semua fitur dan melaporkan `2*AUC-1` (default 0,25, setara AUC 0,625). Keduanya bukan padanan. Issue type `non_iid` Cleanlab Datalab dapat dipertimbangkan sebagai pendukung L7.

**Prinsip interpretasi:** WARNING tidak memblokir, tetapi wajib dikomentari oleh pemilik model di laporan. Fitur yang sangat prediktif belum tentu bocor. Pertanyaan penentunya: *apakah nilai fitur ini sudah tersedia pada saat prediksi dibuat?*

### 5.1 Katalog Alasan: Kenapa Data Ini Dianggap Leakage

Setiap temuan wajib membawa penjelasan **kenapa** data atau fitur itu dianggap leakage, bukan hanya angka dan status. Penjelasan ini dibuat oleh **Reason Engine** di dalam Aggregator.

**Prinsip Reason Engine**

1. **Deterministik dan dapat diaudit.** Teks dihasilkan dari template per `check_id` yang diisi nilai bukti (metrik, ambang, nama kolom). Tidak ada LLM di jalur gate, sehingga hasil yang sama selalu menghasilkan teks yang sama.
2. **Gejala bukan vonis.** Detektor hanya melihat gejala (korelasi, overlap, drift). Akar masalah ditulis sebagai *kemungkinan penyebab* yang perlu dikonfirmasi pemilik model, bukan sebagai fakta.
3. **Ada tingkat keyakinan (`confidence`).**
   - `high`: aturan eksplisit (kolom ada di `forbidden_columns`, duplikat persis), atau minimal dua detektor independen sepakat.
   - `medium`: satu detektor melaporkan CRITICAL.
   - `low`: temuan WARNING atau berbasis heuristik (mis. nama kolom).
4. **Pertanyaan verifikasi untuk manusia.** Tiap alasan menyertakan `verification_question`, karena keputusan akhir "bocor atau fitur sah yang kuat" selalu ada pada pemilik model.
5. **Tanpa PII.** Bukti hanya memuat agregat, nama kolom, dan identifier yang di-hash. Contoh nilai mentah tidak pernah dimasukkan.
6. **Bahasa** keluaran mengikuti `report.language` di `guard.yaml` (default `id`). Nama field JSON tetap Inggris.

**Katalog alasan per pemeriksaan**

| `check_id` | Kenapa ini leakage | Bukti yang dilampirkan | Kemungkinan akar masalah | Perbaikan yang disarankan |
|---|---|---|---|---|
| `row_overlap` | Baris yang sama persis ada di train dan test. Model dinilai pada contoh yang sudah pernah dilihatnya, sehingga metrik test terlalu optimis. | Jumlah dan persentase baris test yang duplikat; jumlah kolom yang dibandingkan; hash baris (tanpa nilai) | Duplikasi di sumber; join yang menggandakan baris; oversampling/augmentasi dilakukan sebelum split | Dedup sebelum split; oversampling hanya pada data training setelah split |
| `group_overlap` | Nasabah yang sama muncul di kedua split. Perilaku dan profil nasabah itu ikut terbawa, sehingga model bisa mengenali nasabahnya, bukan mempelajari pola risiko. Sampel test tidak independen. | Jumlah entitas yang bocor; persentase dari entitas test; ID ter-hash | Satu nasabah punya banyak produk atau snapshot bulanan; split acak per baris | Split berbasis entitas (`GroupKFold`); pastikan tiap entitas hanya berada di satu split |
| `temporal` | Sebagian data test lebih lama dari data train terakhir. Model dilatih dengan kondisi yang di dunia nyata belum terjadi saat keputusan diambil (kondisi ekonomi, kebijakan, perilaku periode berikutnya). | `train_max`, `test_min`; persentase test sebelum `train_max` | Random split pada data berurutan waktu | Split out-of-time; tambahkan embargo |
| `temporal_embargo` | Jarak antara akhir train dan awal test lebih kecil dari `embargo_days`. Fitur berjendela (rata-rata 3 bulan, jumlah transaksi 6 bulan) dan label yang baru matang di akhir train bertumpang tindih dengan awal test. | Jarak hari aktual vs `embargo_days`; daftar fitur berjendela (jika terdaftar di metadata) | Split dipotong tepat di batas tanggal tanpa jeda | Sisipkan jeda sebesar jendela fitur terpanjang atau maturity window |
| `single_feature` | Satu fitur saja memprediksi target hampir sempurna. Pada kasus risiko kredit yang nyata, itu hampir tidak pernah terjadi kecuali fitur diturunkan dari target atau baru tercatat setelah outcome diketahui. | Skor CV fitur (ROC-AUC/R²); perbandingan dengan 5 fitur teratas lain; ambang | Fitur pasca-outcome (mis. kolektibilitas, DPD sesudah origination); fitur turunan dari target; proxy label | Telusuri lineage fitur dan `available_at`; ganti dengan nilai snapshot pada `prediction_date` atau hapus |
| `pps_train` | Predictive Power Score menangkap hubungan non-linier fitur terhadap target. Skor mendekati 1 berarti fitur itu hampir menentukan target. Bila `single_feature` juga menyala, dua metode independen sepakat. | PPS di train dan di test; apakah `single_feature` ikut menandai kolom yang sama | Sama seperti `single_feature` | Sama seperti `single_feature` |
| `identifier_label` | Kolom identitas (ID aplikasi, nomor urut) berkorelasi dengan target. ID berurutan menyandi waktu, kanal, atau produk, sehingga model belajar "kapan/lewat mana", bukan risiko nasabah. | PPS kolom ID terhadap target; ambang | ID dipakai sebagai fitur; penomoran berbeda per periode atau produk | Keluarkan ID dari matriks fitur |
| `suspicious_names` | Nama kolom mengisyaratkan informasi pasca-outcome (mis. `kolek`, `dpd`, `npl`). Ini hanya petunjuk dari penamaan, bukan bukti. | Nama kolom dan pola yang cocok | Penamaan kolom turunan dari status kredit | Konfirmasi kapan nilai kolom tersedia; jika pasca-outcome, masukkan ke `forbidden_columns` |
| `blocklist_hit` | Kolom ini sudah ditetapkan terlarang oleh tim model risk karena pasti diketahui setelah titik prediksi. | Nama kolom dan entri blocklist yang cocok | Fitur ikut terbawa dari tabel sumber yang berisi kolom outcome | Hapus kolom dari fitur; perbaiki query/feature store sumber |
| `adversarial` | Sebuah model dapat membedakan data train dari test lewat fitur tertentu. Artinya distribusi keduanya berbeda secara sistematis, sehingga skor test tidak mewakili populasi training. Bisa berupa drift periode, split tidak acak, atau fitur yang menyandi waktu/ID. | AUC pembeda per fitur teratas; ambang | Split non-acak; drift antar periode; fitur menyandi tanggal atau ID | Periksa fitur penanda; gunakan split yang disengaja (out-of-time) dan dokumentasikan drift yang diharapkan |
| `near_dup_cross_split` | Sampel yang hampir identik (aplikasi diulang dengan perubahan kecil, snapshot bulan berurutan) ada di kedua split. Efeknya sama dengan duplikat persis, tetapi lolos dari pemeriksaan hash. | Jumlah himpunan near-duplicate lintas split; persentase dari test | Snapshot berulang per nasabah; entri ganda dengan variasi kecil | Split berbasis entitas atau waktu; dedup near-duplicate sebelum split |
| `pipeline_integrity` | Langkah preprocessing yang belajar dari seluruh data (scaler, imputer, target encoder) membawa statistik test ke dalam training, sehingga skor evaluasi terlalu baik. | Selisih skor CV antara pipeline benar dan varian yang di-fit pada data penuh | Transformer di-fit sebelum split; target encoding tanpa out-of-fold | Pindahkan semua transformer ke dalam `Pipeline`; hitung encoding out-of-fold |

**Contoh teks yang dihasilkan** (template `single_feature`, bahasa Indonesia):

> Fitur `{column}` memprediksi target `{target}` dengan ROC-AUC {value:.3f} (ambang kritis {threshold}), padahal fitur teratas lain hanya mencapai {next_best:.3f}. Pada data risiko kredit yang nyata, satu fitur hampir tidak pernah cukup memprediksi gagal bayar kecuali nilainya diturunkan dari target atau baru tercatat setelah outcome diketahui. Keyakinan: {confidence}. Pertanyaan verifikasi: apakah nilai `{column}` sudah tersedia pada `{prediction_date}`?

**Aturan operasional**

- Temuan tanpa blok `reason` dianggap cacat. Aggregator menolak menulis laporan dan mengembalikan exit code 2.
- `check_id` baru wajib menyertakan template alasan sebelum dapat didaftarkan.
- Pemilik model wajib mengisi `owner_assessment` (`confirmed_leakage` / `legitimate_feature` / `needs_investigation`) untuk setiap temuan CRITICAL dan WARNING sebelum laporan dilampirkan ke dokumen validasi. `legitimate_feature` tanpa waiver tidak menghapus blokir CRITICAL.

---

## 6. Pencegahan Preprocessing Leakage (L6)

Tidak ada detektor data yang andal untuk L6, sehingga pencegahannya berupa standar kode dan pengujian.

### 6.1 Standar wajib

- Semua transformasi yang belajar dari data (scaler, imputer, encoder, selector, target encoder, PCA) **harus** berada di dalam `sklearn.pipeline.Pipeline` atau `ColumnTransformer`, dan di-fit hanya pada data training atau fold training.
- Tidak boleh ada `fit` atau `fit_transform` pada data penuh sebelum pembagian split.
- Target encoding dan fitur agregat per nasabah dihitung dengan skema out-of-fold, dengan batas waktu: hanya data **sebelum** tanggal observasi baris tersebut.
- Resampling (SMOTE, undersampling) hanya pada fold training, bukan sebelum split.
- Seleksi fitur berbasis target dilakukan di dalam fold.

### 6.2 Pemeriksaan otomatis

1. **Static rule (semgrep)**: tandai pola `fit_transform(` pada variabel yang bukan hasil split, serta `train_test_split(` yang dipanggil setelah transformasi.

   ```yaml
   rules:
     - id: ml-fit-before-split
       languages: [python]
       severity: ERROR
       message: "Transformer di-fit sebelum split. Pindahkan ke dalam sklearn Pipeline."
       patterns:
         - pattern: $T.fit_transform($DF)
         - pattern-not-inside: |
             Pipeline(...)
   ```

   (Aturan ini heuristik. Sintaksnya valid, tetapi juga menandai pemakaian yang benar (mis. `fit_transform` pada data training setelah split) dan belum mengimplementasikan klausa `train_test_split`. Gunakan sebagai WARNING, bukan blocker, sampai dituning pada kode nyata.)

2. **Pipeline integrity test (unit test)**: model artifact harus berupa objek `Pipeline`, dan seluruh langkahnya harus dapat di-clone dan di-fit ulang dari data training saja. Tes membandingkan skor CV pipeline utuh dengan varian "bocor" yang sengaja di-fit pada seluruh data. Selisih skor yang besar menandakan fitur atau langkah sensitif terhadap leakage.

---

## 7. Strategi Split (Pencegahan L2, L3, L7)

| Situasi data | Strategi wajib |
|---|---|
| Satu nasabah punya banyak baris | `GroupKFold` / split berbasis `entity` |
| Data berurutan waktu (aplikasi kredit, transaksi) | Split berbasis waktu (out-of-time), `TimeSeriesSplit`, atau purged CV dengan embargo |
| Label baru matang setelah periode observasi (mis. default dalam 12 bulan) | Batas cut-off: baris yang belum melewati *maturity window* dikeluarkan dari train dan test |
| Kombinasi grup dan waktu | Split waktu lebih dulu, lalu pastikan tidak ada entitas bocor lintas split (atau terima dan dokumentasikan dengan waiver) |

Catatan implementasi:

- Untuk purged/embargo CV pada data keuangan, `skfolio.model_selection.CombinatorialPurgedCV` adalah salah satu opsi. Parameter `purged_size` dan `embargo_size` berada dalam jumlah observasi, bukan hari, sehingga `embargo_days` harus dikonversi sesuai frekuensi data. Kelayakannya untuk data kredit nasabah (bukan deret harga) perlu dievaluasi, dan implementasi `PurgedKFold` internal tetap menjadi alternatif.
- `embargo_days` dan `maturity_window_days` ditetapkan per model di `guard.yaml`, disetujui pemilik bisnis dan model risk.

### 7.1 Kontrol khusus domain credit scoring

- **Titik prediksi (`prediction_date`)** didefinisikan eksplisit per model. Semua fitur wajib bertanda `available_at <= prediction_date`.
- **`forbidden_columns`** berisi atribut yang pasti pasca-outcome, misalnya kolektibilitas masa depan, DPD pasca-origination, status write-off, dan status restrukturisasi.
- **Definisi target** (misalnya 90+ DPD dalam 12 bulan) tidak boleh ikut menjadi fitur dalam bentuk turunan apa pun.

---

## 8. Konfigurasi (`guard.yaml`)

```yaml
version: 1
model_id: abc-scoring-pd-v3

data:
  train: s3://bucket/model/train.parquet
  test: s3://bucket/model/test.parquet
  target: default_flag
  entity_col: customer_id       # dipakai sebagai index_name pada IndexTrainTestLeakage (L2)
  time_col: application_date
  index_col: application_id     # dipakai sebagai index_name pada IdentifierLabelCorrelation (L5)
  pii_columns: [nik, npwp, nama, no_rekening]

prediction:
  prediction_date_col: application_date
  embargo_days: 30
  maturity_window_days: 365

blocklist:
  forbidden_columns: [kolektibilitas_akhir, dpd_max_post, status_writeoff]
  suspicious_name_patterns: [default, kolek, dpd, npl, write_off, restruct, recovery]

thresholds:
  row_overlap:      { warn_pct: 0.0, crit_pct: 1.0 }
  temporal:         { warn_pct: 0.0, crit_pct: 5.0 }
  single_feature:   { warn: 0.85, crit: 0.95 }
  pps:              { warn: 0.5,  crit: 0.8 }
  identifier_label: { warn: 0.1,  crit: 0.2 }
  adversarial:      { warn: 0.70, crit: 0.95 }

runtime:
  max_rows: 100000
  seed: 42

gate:
  fail_on: [CRITICAL]
  waivers_file: waivers.yaml

report:
  language: id            # bahasa teks alasan; nama field JSON tetap Inggris
  require_owner_assessment: true
```

### Waiver

Waiver memungkinkan temuan CRITICAL yang sudah dikaji tetap lolos, dengan jejak audit.

```yaml
waivers:
  - finding_id: group_overlap:customer_id
    owner: nama.pemilik@bank.example
    approved_by: nama.model.risk@bank.example
    reason: "Satu nasabah dengan beberapa produk; dampak diukur dan dinilai tidak material"
    expires: 2027-02-28
```

Aturan waiver: wajib punya `owner`, `approved_by`, `reason`, dan `expires`. Waiver kedaluwarsa otomatis tidak berlaku dan gate kembali memblokir.

---

## 9. Skema Keluaran

### 9.1 Temuan (dinormalisasi)

```json
{
  "finding_id": "single_feature:kolektibilitas_akhir",
  "check_id": "single_feature",
  "leakage_type": "L4",
  "severity": "CRITICAL",
  "scope": "feature",
  "column": "kolektibilitas_akhir",
  "metric": { "name": "cv_roc_auc", "value": 1.0, "threshold": 0.95 },
  "message": "Fitur tunggal memprediksi target hampir sempurna.",
  "sources": ["custom", "deepchecks", "ppscore"],
  "reason": {
    "summary": "kolektibilitas_akhir hampir menentukan default_flag; kemungkinan informasi pasca-outcome.",
    "why_leakage": "Fitur memprediksi target dengan ROC-AUC 1.000 (ambang kritis 0.95), padahal fitur teratas lain hanya 0.512. Pada data risiko kredit yang nyata, satu fitur hampir tidak pernah cukup memprediksi gagal bayar kecuali nilainya diturunkan dari target atau baru tercatat setelah outcome diketahui.",
    "evidence": {
      "cv_roc_auc": 1.0,
      "next_best_feature_auc": 0.512,
      "pps_train": 1.0,
      "pps_test": 1.0,
      "detectors_agreeing": ["custom", "deepchecks", "ppscore"]
    },
    "impact": "Metrik evaluasi (AUC, KS, Gini) terlalu optimis; performa produksi diperkirakan jauh lebih rendah.",
    "likely_root_causes": [
      "Fitur dicatat setelah outcome diketahui (pasca-outcome)",
      "Fitur diturunkan dari target atau dari status kredit akhir"
    ],
    "remediation": [
      "Telusuri lineage dan available_at kolom ini",
      "Gunakan nilai snapshot pada prediction_date atau hapus kolom dari fitur"
    ],
    "verification_question": "Apakah nilai kolektibilitas_akhir sudah tersedia pada application_date?",
    "confidence": "high",
    "owner_assessment": null
  },
  "waived": false
}
```

### 9.2 Ringkasan laporan

```json
{
  "model_id": "abc-scoring-pd-v3",
  "run_at": "2026-11-07T10:00:00Z",
  "config_hash": "sha256:...",
  "data_fingerprint": { "train_rows": 2800000, "test_rows": 700000 },
  "tools": { "deepchecks": "0.19.1", "ppscore": "1.3.1", "cleanlab": "x.y.z" },
  "summary": { "critical": 2, "warning": 5, "info": 11, "waived": 0 },
  "gate": "FAILED",
  "findings": []
}
```

`report.md` berisi ringkasan untuk manusia dan dilampirkan ke dokumen validasi model. HTML Deepchecks disimpan sebagai lampiran tambahan.

### 9.3 Struktur `report.md`

Setiap temuan ditulis dengan blok alasan yang sama agar reviewer model risk tidak perlu membuka JSON.

```markdown
## [CRITICAL] single_feature: kolektibilitas_akhir

**Kenapa ini leakage:** Fitur memprediksi target dengan ROC-AUC 1.000 (ambang 0.95), padahal fitur teratas lain hanya 0.512. ...

| Bukti | Nilai |
|---|---|
| CV ROC-AUC | 1.000 |
| PPS train / test | 1.0 / 1.0 |
| Detektor yang sepakat | custom, deepchecks, ppscore |

**Dampak:** Metrik evaluasi terlalu optimis.
**Kemungkinan akar masalah:** fitur pasca-outcome; turunan dari target.
**Perbaikan:** telusuri lineage dan `available_at`; gunakan snapshot pada `prediction_date`.
**Keyakinan:** high
**Pertanyaan verifikasi:** Apakah nilai `kolektibilitas_akhir` sudah tersedia pada `application_date`?
**Penilaian pemilik model:** (diisi)
```

---

## 10. Integrasi CI/CD

- **Titik pasang:** (1) setelah pembuatan dataset split, sebelum training; (2) sebelum promosi model ke staging; (3) pada setiap retraining terjadwal.
- **Perilaku gate:** exit 0 = lanjut; exit 1 = ada temuan CRITICAL tanpa waiver; exit 2 = error runtime detektor (diperlakukan sebagai gagal, bukan lolos).
- **Artefak:** `report.json`, `report.md`, `deepchecks_report.html`, dan hash konfigurasi diunggah ke penyimpanan artefak dan dikaitkan ke run model.
- **Retensi:** laporan disimpan selama masa hidup model ditambah periode retensi audit internal.

---

## 11. Keamanan dan Kepatuhan

- **UU PDP (UU No. 27 Tahun 2022):** laporan tidak boleh memuat nilai PII. Kolom pada `pii_columns` di-drop di Preflight, dan contoh nilai pada temuan (mis. `examples` entitas yang bocor) dimasking atau di-hash. Menurut Pasal 4 ayat (3) huruf f, data yang dikombinasikan untuk mengidentifikasi seseorang adalah data pribadi, sehingga hash tidak menghapus status data pribadi dan kuasi-identifier (usia, wilayah, tanggal aplikasi) juga harus dikelola, bukan hanya `pii_columns`. Pasal 34 mewajibkan penilaian dampak untuk pengambilan keputusan otomatis dan penskoran sistematis, dan Pasal 10 mengatur hak keberatan atas keputusan otomatis; keduanya relevan bagi model credit scoring yang dilindungi gate ini.
- **Kerahasiaan bank:** rahasia bank menurut UU No. 10 Tahun 1998 (Pasal 1 angka 28), sebagaimana diubah UU No. 4 Tahun 2023, mencakup nasabah penyimpan dan simpanannya. Data debitur untuk credit scoring tidak dicakup definisi ini; ketentuan ini berlaku bila data memuat nasabah penyimpan. Ketentuan turunan (POJK) belum diperiksa.
- **Akses:** laporan HTML Deepchecks bisa memuat potongan data. Simpan di bucket dengan kontrol akses setara data training.
- **Jejak audit:** konfigurasi, versi alat, hash data, dan waiver terekam sehingga hasil dapat direproduksi.
- **Selaras dengan tata kelola model risk:** laporan menjadi bukti kontrol "tidak ada kebocoran data" pada dokumentasi pengembangan dan validasi model. Pemetaan ke ketentuan OJK/BI yang spesifik harus dikonfirmasi bersama tim kepatuhan dan model risk, bukan diasumsikan dari dokumen ini.

---

## 12. Kriteria Penerimaan

1. Pada dataset uji sintetis dengan kebocoran yang disengaja (duplikat, overlap entitas, overlap tanggal, fitur bocor), seluruh jenis L1 sampai L5 terdeteksi dan gate mengembalikan exit 1.
2. Pada dataset bersih dengan split berbasis waktu dan grup, gate mengembalikan exit 0 dengan false positive CRITICAL = 0.
3. Aggregator menghasilkan satu temuan per `finding_id` meski dilaporkan oleh beberapa alat.
4. Waiver yang kedaluwarsa memblokir pipeline kembali.
5. Tidak ada nilai PII pada `report.json`, `report.md`, maupun laporan HTML.
6. Seluruh detektor dapat dibangun ulang dari lockfile dan dijalankan di CI tanpa akses internet selain registry paket.
7. Waktu eksekusi total kurang dari 15 menit untuk 1 juta baris dengan `max_rows=100000` (target awal, perlu diukur).
8. Setiap temuan pada `report.json` dan `report.md` memiliki blok `reason` lengkap (`why_leakage`, `evidence`, `impact`, `likely_root_causes`, `remediation`, `verification_question`, `confidence`). Aggregator gagal dengan exit 2 bila ada yang kosong.
9. Teks alasan bersifat deterministik: dua kali eksekusi pada data dan konfigurasi yang sama menghasilkan teks identik.
10. Pada dataset sintetis berkebocoran, alasan yang dihasilkan menyebut kolom dan metrik yang benar, dan tidak memuat nilai PII.

---

## 13. Status Verifikasi

| Komponen | Status | Catatan |
|---|---|---|
| `leakage_check.py` | Dibuat (tidak ada di repo ini; lokasi perlu dicantumkan) | Belum dijalankan end-to-end pada data produksi |
| `deepchecks_leakage.py` | **Diuji** pada data sintetis (skrip tidak ada di repo ini; lokasi perlu dicantumkan) | Semua kebocoran yang disengaja terdeteksi; exit code 1 terverifikasi. Catatan: L2 baru terdeteksi bila `index_name` = kolom entitas (lihat 4.3) |
| ppscore | **Diuji** | Fitur bocor mendapat PPS 1,0; berjalan di `env-dc`. Default `sample=5000`; ID kategorikal unik bernilai 0 |
| Cleanlab Datalab | **Diuji sebagian** (cleanlab 2.9.0, data sintetis kecil) | `near_duplicate_sets`, kolom hasil, dan deteksi lintas-split terverifikasi; dapat dipasang bersama Deepchecks dengan `pyarrow<=19.0.1` dan `numpy<2`. Belum diuji: data campuran dan skala jutaan baris |
| `ppscore_check.py`, `datalab_check.py`, Aggregator, Gate | Belum dibuat | Lingkup fase 1 dan 2 |
| Semgrep rule L6 | Belum diuji | Heuristik, perlu tuning |
| Ambang default | Belum dikalibrasi | Kalibrasi pada data historis model yang sudah divalidasi |
| Target performa (15 menit) | Belum diukur | |
| Reason Engine dan template alasan (bagian 5.1) | Belum dibuat | Hanya spesifikasi; teks contoh belum divalidasi oleh tim model risk |

---

## 14. Rencana Implementasi

| Fase | Isi | Keluaran |
|---|---|---|
| **1. Fondasi** | Preflight, `guard.yaml`, container `env-dc` dengan lockfile, jalankan A dan B, Aggregator minimal | Gate lokal dan di CI untuk satu model percontohan |
| **2. Pelengkap** | `ppscore_check.py`, `env-cl` + `datalab_check.py`, dedup lintas alat, waiver | Laporan terpadu `report.md` |
| **3. Pencegahan** | Standar `Pipeline`, semgrep rule, *pipeline integrity test*, template split berbasis waktu dan grup | Panduan engineering dan template proyek |
| **4. Governance** | Integrasi MLflow, retensi laporan, kalibrasi ambang dari model historis, review bersama model risk | Dokumen kontrol siap audit |

---

## 15. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Konflik dependensi antar alat (mis. rilis `datasets`/`pyarrow` baru memaksa `numpy>=2`) | Gate tidak bisa dijalankan | Environment terisolasi dengan lockfile; pertukaran lewat berkas |
| Ambang terlalu ketat atau longgar | Banyak false positive, atau kebocoran lolos | Kalibrasi pada model historis; WARNING tidak memblokir; mekanisme waiver |
| Fitur kuat yang sah ditandai bocor | Tim mengabaikan gate | Wajib dokumentasi alasan; metrik `available_at` per fitur |
| ppscore jarang dirilis (1.3.0 Okt 2022, 1.3.1 Mar 2026) | Bit-rot | Padanan internal di `leakage_check.py`; pin versi |
| Deepchecks butuh pin lama (sklearn, numpy) | Terkunci pada versi lama | Container terpisah; pantau rilis Deepchecks berikutnya |
| Laporan memuat data sensitif | Pelanggaran kerahasiaan | Drop PII di Preflight; masking contoh nilai; kontrol akses artefak |
| Alasan terbaca seperti vonis padahal baru gejala | Fitur sah dibuang, atau kebocoran dianggap sudah dipastikan | Bahasa "kemungkinan penyebab"; wajib `confidence` dan `verification_question`; keputusan akhir pada pemilik model |

---

## 16. Pertanyaan Terbuka

1. Berapa `embargo_days` dan `maturity_window_days` yang disetujui untuk tiap model scoring?
2. Apakah semua fitur sudah memiliki metadata `available_at`, atau perlu dibuat dulu sebagai prasyarat?
3. Apakah hasil gate perlu terhubung ke tiket model risk (misalnya Jira) selain MLflow?
4. Siapa yang berwenang menyetujui waiver CRITICAL (pemilik model, model risk, atau keduanya)?
5. Apakah laporan HTML Deepchecks boleh disimpan di luar zona data training?
6. Apakah teks alasan perlu tersedia dalam dua bahasa (Indonesia dan Inggris) untuk kebutuhan audit eksternal?
7. Siapa yang mengisi `owner_assessment` bila pemilik model tidak lagi menangani model tersebut?

---

## Catatan Perubahan

### 1.2 (7 November 2026)

Koreksi berdasarkan verifikasi terhadap sumber primer (`research/spec-verification.md`).

- **L2 / `index_col` (4.3, 8, 2):** `IndexTrainTestLeakage` hanya mendeteksi overlap entitas bila `index_name` = kolom entitas; dua pemanggilan dengan dua `Dataset` (L2 dan L5). `leakage_check.py` menjadi sumber utama L2.
- **Dependensi (3.3, 13, 15):** `cleanlab[datalab]` dapat dipasang bersama Deepchecks dengan `pyarrow<=19.0.1` dan `numpy<2`; alasan `env-cl` terpisah diubah. Ditambahkan versi Python yang diuji dan catatan bahwa pin bersifat konservatif.
- **ppscore (4.2, 4.4, 15):** `sample=` default 5.000, nama parameter `random_seed`, ID kategorikal unik bernilai 0, Deepchecks memakai modul PPS internal, klaim "tidak dipelihara" dilunakkan.
- **Ambang (4.3, 5):** kolom "Basis ambang" (default Deepchecks / desain / kalibrasi); catatan perbedaan `adversarial` dengan `MultivariateDrift`.
- **L3 (2, 4.3):** `DateTrainTestLeakageDuplicates` mengukur tanggal bersama, bukan urutan waktu.
- **Regulasi (1, 11):** "PSAK 71" diganti PSAK 109 (hubungan penomoran perlu dikonfirmasi); UU PDP (UU 27/2022) dipisah dari kerahasiaan bank, yang hanya mencakup nasabah penyimpan.
- **Semgrep L6 (6.2), skfolio (7):** catatan false positive; satuan `purged_size`/`embargo_size` adalah observasi.
- **Status verifikasi (13):** status Cleanlab diperbarui; skrip `leakage_check.py` dan `deepchecks_leakage.py` ditandai tidak ada di repo.

### 1.1

Penjelasan alasan leakage per temuan (Reason Engine, bagian 5.1).
