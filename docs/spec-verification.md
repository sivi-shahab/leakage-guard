# Verifikasi Klaim Teknis dan Regulasi: spec.md (ML Leakage Guard v1.1)

Tanggal verifikasi: 7 November 2026. Objek: `/root/data-leakage/spec.md` (518 baris, dibaca penuh). Spec tidak diubah; semua koreksi hanya usulan.

Status yang dipakai: **TERVERIFIKASI**, **TIDAK SESUAI** (termasuk "sebagian sesuai / perlu dikoreksi"), **TIDAK BISA DIVERIFIKASI**, dan **KEPUTUSAN DESAIN** (bukan klaim fakta; tidak punya sumber primer dan memang tidak perlu).

## 1. Ringkasan

Metode: (a) metadata PyPI dan GitHub API resmi, (b) membaca source terpasang (`deepchecks` 0.19.1, `ppscore` 1.3.1, `cleanlab` 2.9.0), (c) eksperimen pemasangan dan eksekusi di virtualenv terisolasi (Python 3.11, uv; Python 3.12 diuji sekali), (d) teks UU di peraturan.bpk.go.id dan daftar standar di situs IAI.

Temuan terpenting:

1. **Konfigurasi `L2` salah arah.** `IndexTrainTestLeakage` membandingkan nilai kolom `index_name` antara train dan test. Spec memetakan L2 (overlap entitas) ke check ini, tetapi `guard.yaml` mengisi `index_col: application_id`. Hasil uji: dengan `application_id` hasilnya 0; dengan `customer_id` hasilnya 0,577. Jadi entitas bocor hanya terdeteksi bila `index_name=customer_id` (§4.1).
2. **`IdentifierLabelCorrelation` tidak memeriksa kolom ID sembarang.** Check ini hanya menguji kolom `index` dan `datetime` yang didefinisikan di `Dataset`, dan melempar `DatasetValidationError` bila keduanya tidak ada. Default kondisinya `max_pps=0`, bukan 0,2 (§4.2).
3. **Klaim "cleanlab[datalab] tak bisa hidup di `env-dc`" tidak terbukti.** Dengan pin yang sama (`numpy<2`, `pyarrow<=19.0.1`, `pandas<2.3`, `scikit-learn<1.6`, `setuptools<81`), resolver memasang `datasets 4.0.0` + `cleanlab 2.9.0` + `deepchecks 0.19.1` berdampingan, dan `Datalab.find_issues` berjalan. Konflik hanya terjadi bila `pyarrow` tidak di-pin. Isolasi environment tetap pilihan yang wajar, tetapi alasannya harus dikoreksi (§3.1).
4. **Pin terlalu ketat atau salah alasan.** `scikit-learn<1.6`: yang gagal adalah 1.8.0 dan 1.9.1; 1.6.1 dan 1.7.2 lolos pada uji klasifikasi. `setuptools<81`: 81.0.0 masih lolos, 82.0.0 gagal. `pandas<2.3`: 2.3.3 lolos; yang gagal 3.x (hanya pada jalur display). Semua pin bersifat aman-tapi-konservatif, bukan batas sebenarnya (§3.1).
5. **Deepchecks memakai ppscore internal (`deepchecks/ppscore.py`), bukan paket PyPI `ppscore`.** Status pemeliharaan ppscore karenanya tidak memengaruhi Deepchecks. Selain itu, rilis ppscore 1.3.1 terbit 11 Maret 2026, sehingga klaim "tidak aktif dikembangkan, rilis terakhir 1.3.x" perlu dilunakkan (§3.2).
6. **Daya deteksi ppscore punya blind spot:** fitur kategorikal dengan nilai unik semua baris (mis. ID bertipe string) otomatis diberi skor 0 ("feature_is_id"). Default `sample=5000` juga berlaku; "sampling maksimum 100.000" di spec tidak berlaku sendiri bila `sample=` tidak diteruskan (§4.4).
7. **Regulasi §1 dan §11:** nomor "PSAK 71" tidak muncul di daftar SAK umum IAI saat ini; yang tercantum "PSAK 109 Instrumen Keuangan". "Kerahasiaan bank" menurut definisi UU hanya mencakup nasabah penyimpan dan simpanannya, bukan data debitur; dasar yang tepat untuk data debitur adalah UU PDP (§11).
8. Aturan semgrep di §6.2 valid secara sintaks, tetapi menandai pemakaian benar (`fit_transform` pada data train pasca-split) sebagai pelanggaran, dan tidak mengimplementasikan klausa "`train_test_split(` setelah transformasi".

Jumlah klaim yang diperiksa: 47 (ringkas di tabel §2). Tidak bisa diverifikasi: 6 (#27, #37, #42, #43, #44, #46; semua berupa hal organisasi/kebijakan atau di luar sumber primer yang bisa diakses).

## 2. Tabel klaim → status → sumber

Sumber singkat: **PyPI** = `https://pypi.org/pypi/<paket>/json`; **DC-src** = source `deepchecks==0.19.1` terpasang (`site-packages/deepchecks/...`) yang sama dengan `https://github.com/deepchecks/deepchecks/tree/0.19.1`; **PPS-src** = `https://github.com/8080labs/ppscore`; **CL-src** = `https://github.com/cleanlab/cleanlab` rilis 2.9.0; **Uji** = eksperimen saya (§12).

| # | Bagian | Klaim spec | Status | Sumber / bukti |
|---|---|---|---|---|
| 1 | 3.3 | Deepchecks 0.19.1 gagal import dengan scikit-learn terbaru (`max_error` tak dikenali) | TERVERIFIKASI (dengan nuansa batas versi, lihat #2) | Uji: sklearn 1.8.0 dan 1.9.1 → `ValueError: 'max_error' is not a valid scoring value`. `deepchecks/tabular/metric_utils/scorers.py:116` memanggil `get_scorer('max_error')`. Release notes sklearn 1.6: `scoring="max_error"` deprecated, ganti `neg_max_error` (`doc/whats_new/v1.6.rst`). Kegagalan terjadi saat dipakai, bukan saat `import` murni. |
| 2 | 3.3 | Pin `scikit-learn<1.6` wajib | TIDAK SESUAI (terlalu ketat) | Uji: 1.6.1 dan 1.7.2 lolos suite `train_test_validation` + `FeatureLabelCorrelation` (klasifikasi); 1.8.0 gagal. Batas empiris `<1.8`. Jalur regresi (yang memakai `max_error`) tidak diuji di 1.6/1.7 dan akan menampilkan deprecation. |
| 3 | 3.3 | Pin `numpy<2` wajib | TERVERIFIKASI | Uji: dengan `numpy>=2` (2.4.6) → `AttributeError: np.Inf was removed in the NumPy 2.0 release` di source Deepchecks. |
| 4 | 3.3 | Pin `pandas<2.3` wajib | TIDAK SESUAI (terlalu ketat) | Uji: pandas 2.3.3 lolos (check + suite + display). Pandas 3.0.6 gagal: `'DataFrame' object has no attribute 'applymap'` pada jalur display; suite dengan `with_display=False` lolos. Batas empiris `<3`. |
| 5 | 3.3 | Pin `setuptools<81` wajib; Deepchecks butuh `pkg_resources` | TERVERIFIKASI untuk kebutuhan, TIDAK SESUAI untuk batas | `deepchecks/core/serialization/dataframe/html.py:16: from pkg_resources import parse_version`. Uji: setuptools 81.0.0 lolos (dengan UserWarning), 82.0.0 dan 84.2.1 gagal `No module named 'pkg_resources'`. Peringatan resmi dalam kode: "Refrain from using this package or pin to Setuptools<81". Batas empiris `<82`; `<81` adalah rekomendasi peringatan, aman. |
| 6 | 3.3 | `pyarrow` terbaru butuh NumPy 2 sehingga tak bisa dipasang dengan `numpy<2` | TERVERIFIKASI | Uji: pyarrow 26.0.1 + numpy 1.26.4 → `ImportError: pyarrow requires NumPy 2.0 or newer, found 1.26.4`. |
| 7 | 3.3 | pyarrow 17.0.0, 18.1.0, 19.0.1 diuji berfungsi dengan `numpy<2` | TERVERIFIKASI sebagian | Uji: 19.0.1 berfungsi (baca/tulis Parquet). 17.0.0 dan 18.1.0 tidak saya uji ulang. Pin `<=19.0.1` konsisten. |
| 8 | 3.3 | `cleanlab[datalab]` menarik `datasets` + `pyarrow` terbaru sehingga tidak bisa di `env-dc` | TIDAK SESUAI | Uji: `uv pip install deepchecks==0.19.1 cleanlab[datalab] numpy<2 pyarrow<=19.0.1 pandas<2.3 scikit-learn<1.6 setuptools<81` sukses (cleanlab 2.9.0, datasets 4.0.0, pyarrow 19.0.1, numpy 1.26.4); `Datalab.find_issues` jalan. Metadata `cleanlab` 2.9.0: `datasets>=2.7.0; extra == "datalab"`, tanpa batas atas. |
| 9 | 3.3 | Pin lain tidak menyebut versi Python | TIDAK SESUAI (celah) | `cleanlab` 2.9.0 `requires_python >=3.10` (PyPI). `deepchecks` 0.19.1 tidak mendeklarasikan `requires_python`; classifier setup.py sampai 3.10. Uji: berjalan di 3.11 dan 3.12. Python 3.13 tidak diuji (build dibatalkan karena lama). Spec perlu menetapkan versi Python. |
| 10 | 3.3 | Deepchecks 0.19.1 adalah rilis yang tepat dan terbaru | TERVERIFIKASI | PyPI: 0.19.1 diunggah 2024-12-15, rilis terbaru. GitHub: commit masih ada sampai 2025-11-24 tetapi tanpa rilis baru. |
| 11 | 4.4, 15 | ppscore tidak aktif dikembangkan, rilis terakhir 1.3.x | TIDAK SESUAI (perlu dilunakkan) | PyPI: 1.3.0 (2022-10-02), 1.3.1 (2026-03-11). GitHub `8080labs/ppscore`: tag 1.3.1, commit 2026-03-11 "Remove deprecated pkg_resources, replace with importlib.metadata" (PR #80). Repo tidak di-archive. Fakta: jeda 3,4 tahun lalu satu rilis perawatan. |
| 12 | 9.2 | contoh `ppscore: 1.3.1` | TERVERIFIKASI | PyPI. |
| 13 | 4.3 | Deepchecks menjalankan suite `train_test_validation` + `FeatureLabelCorrelation` (0,8) + `IdentifierLabelCorrelation` (0,2) | TERVERIFIKASI untuk komposisi, TIDAK SESUAI untuk ambang 0,2 sebagai "bawaan" | Suite (DC-src): `DatasetsSizeComparison, NewLabelTrainTest, NewCategoryTrainTest, StringMismatchComparison, DateTrainTestLeakageDuplicates, DateTrainTestLeakageOverlap, IndexTrainTestLeakage, TrainTestSamplesMix, FeatureLabelCorrelationChange, FeatureDrift, LabelDrift, MultivariateDrift`. Suite tidak memuat `FeatureLabelCorrelation` dan `IdentifierLabelCorrelation`, jadi benar ditambahkan manual. `add_condition_feature_pps_less_than(threshold=0.8)` default = 0,8. `add_condition_pps_less_or_equal(max_pps=0)` default = 0, jadi 0,2 adalah keputusan desain. |
| 14 | 4.3 | `Suite.run()` 0.19.1 tidak punya parameter `n_samples` | TERVERIFIKASI | `inspect.signature(suite.run)`: `train_dataset, test_dataset, model, feature_importance, feature_importance_force_permutation, feature_importance_timeout, with_display, y_pred_*, y_proba_*, run_single_dataset, model_classes`. `n_samples` ada di tiap check. |
| 15 | 4.3 | Check leakage tanggal dan indeks aktif hanya bila `time` dan `index` didefinisikan di `Dataset` | TERVERIFIKASI (untuk suite) | Uji: suite dengan `datetime_name` tanpa `index_name` berjalan tanpa error. Namun `IdentifierLabelCorrelation` dijalankan sendiri tanpa keduanya → `DatasetValidationError: Dataset does not contain an index or a datetime`. |
| 16 | 4.3 | Ambang bawaan ketat (leakage tanggal harus 0%) | TERVERIFIKASI | `add_condition_leakage_ratio_less_or_equal(max_ratio=0)` untuk `DateTrainTestLeakageDuplicates` dan `DateTrainTestLeakageOverlap`; `IndexTrainTestLeakage` `max_ratio=0`; `TrainTestSamplesMix` `max_ratio=0.05`. |
| 17 | 2 (L1) | `TrainTestSamplesMix` mendeteksi duplikasi baris train/test | TERVERIFIKASI | Docstring: "Detect samples in the test data that appear also in training data." |
| 18 | 2 (L2) | `IndexTrainTestLeakage` mendeteksi overlap entitas | TIDAK SESUAI | Docstring: "Check if test indexes are present in train data." Uji: `index_name=application_id` → 0; `index_name=customer_id` → 0,577. Hanya benar bila `index_name` = kolom entitas. |
| 19 | 2 (L3) | `DateTrainTestLeakage*` mendeteksi test lebih lama dari train terakhir | TERVERIFIKASI untuk `Overlap`; `Duplicates` berbeda | `DateTrainTestLeakageOverlap`: "Check test data that is dated earlier than the latest date in train." (uji: 0,2475). `DateTrainTestLeakageDuplicates`: "Check if test dates are present in train data." (uji: 0,25). Duplicates menandai tanggal sama (bukan lebih lama), jadi pada data harian dengan banyak baris per hari hampir selalu menyala. |
| 20 | 2 (L4) | `FeatureLabelCorrelation` mendeteksi target leakage fitur | TERVERIFIKASI | Docstring: "A high PPS (close to 1) can mean ... data leakage." Uji: fitur `leak=y` → 1,0; fitur acak ≈ 0,0. |
| 21 | 2 (L5) | `IdentifierLabelCorrelation` mendeteksi ID berurutan berkorelasi target | TERVERIFIKASI dengan batas | Docstring: "Check if identifiers (Index/Date) can be used to predict the label." Hanya `index` dan `datetime` yang didefinisikan di `Dataset`. |
| 22 | 2 (L7) | Deepchecks drift checks relevan | TERVERIFIKASI | Suite menyertakan `FeatureDrift`, `LabelDrift`, `MultivariateDrift`. `MultivariateDrift` memakai domain classifier; skor = `2*AUC-1`, kondisi default `max_drift_value=0.25` (setara AUC 0,625). |
| 23 | 2 (L8), 4.5 | Cleanlab Datalab menyediakan `near_duplicate` dan `label` | TERVERIFIKASI | CL-src `issue_manager_factory.py`; `REGISTRY` klasifikasi memuat `outlier, label, near_duplicate, non_iid, class_imbalance, underperforming_group, data_valuation, null`. |
| 24 | 4.5 | `Datalab(data=df, label_name=target)` lalu `find_issues(features=X, issue_types={"near_duplicate": {}, "label": {}, "outlier": {}})` | TERVERIFIKASI | Uji di cleanlab 2.9.0 (env terpisah numpy 2.4.6 / pandas 3.1.1 / sklearn 1.9.1 dan env gabungan `env-dc`): berjalan, 83 issue pada data uji. |
| 25 | 4.5 | Kolom hasil `near_duplicate_sets` | TERVERIFIKASI | `get_issues("near_duplicate")` menghasilkan kolom `is_near_duplicate_issue, near_duplicate_score, near_duplicate_sets, distance_to_nearest_neighbor`. Uji: 20/20 baris test yang dibuat dari jitter baris train terdeteksi punya anggota set di train. |
| 26 | 4.5 | Temuan `label` pada train sebagai INFO/WARNING | KEPUTUSAN DESAIN | `get_issues("label")` → kolom `is_label_issue, label_score, given_label, predicted_label`. Menilai tingkat keparahan adalah kebijakan. |
| 27 | 4.5 | "Perilaku pada data tabular campuran" dan "waktu eksekusi jutaan baris" | TIDAK BISA DIVERIFIKASI (di luar uji ini) | Tidak diuji. Fakta kode: ambang near-duplicate relatif terhadap median jarak tetangga terdekat (`threshold=0.13`, `mask = distances < threshold * median`, `duplicate.py`), sehingga sensitif terhadap skala fitur dan encoding. |
| 28 | 4.4 | `pps.predictors(df, y=target)`; fitur bocor 1,0 dan lain 0,0 | TERVERIFIKASI | Uji (paket `ppscore`/deepchecks.ppscore): `{'leak': 1.0, 'a': 0.0}`. |
| 29 | 4.4 | "Sampling maksimum 100.000 baris, `random_state` tetap" | TIDAK SESUAI (celah) | PPS-src `calculation.py`: `score(..., sample=5_000, cross_validation=4, random_seed=123)`. Tanpa `sample=100000`, ppscore men-sampling 5.000 baris. Parameter bernama `random_seed`, bukan `random_state`. |
| 30 | 4.4 | ppscore menjadi pembanding yang adil bagi skor "setara" custom (tree depth 3, CV) | TIDAK SESUAI (perbedaan metodologi) | PPS-src: `DecisionTreeClassifier()`/`DecisionTreeRegressor()` tanpa `max_depth`, CV 4-fold, klasifikasi dinormalisasi F1 tertimbang terhadap baseline modus (`_normalized_f1_score`), regresi MAE ternormalisasi. Bukan AUC/R². "Setara PPS" di §4.2 hanya konseptual. |
| 31 | 4.4, 5 | PPS cocok untuk menandai kolom ID (L5) | TIDAK SESUAI untuk kategorikal unik | PPS-src `_feature_is_id`: kolom kategorikal (object/category/bool) dengan nilai unik di setiap baris → kasus `feature_is_id`, skor 0. ID bertipe string tak terdeteksi. |
| 32 | 4.2/5 | Adversarial validation `single feature AUC` | KEPUTUSAN DESAIN | Deepchecks `MultivariateDrift` memakai semua fitur sekaligus, bukan per fitur; tidak sama dengan desain §5. |
| 33 | 6.2 | Aturan semgrep valid dan menandai `fit_transform` sebelum split | TIDAK SESUAI sebagian | Uji `semgrep --validate`: konfigurasi valid. Uji pada contoh kode: kedua `sc.fit_transform(df)` (leak) dan `sc2.fit_transform(Xtr)` (pasca-split, benar) ditandai. Klausa `train_test_split(` setelah transformasi tidak ada di aturan. Spec sudah menyebut "heuristik, false positive". |
| 34 | 7 | `skfolio.model_selection.CombinatorialPurgedCV` ada | TERVERIFIKASI | Uji `skfolio 1.12.7`: signature `(n_folds=10, n_test_folds=8, purged_size=0, embargo_size=0)`. Satuan `purged_size`/`embargo_size` adalah jumlah observasi, bukan hari; `embargo_days` perlu dikonversi. |
| 35 | 7 | `GroupKFold`, `TimeSeriesSplit` | TIDAK DIUJI | Dikenal sebagai API scikit-learn; bukan klaim berisiko. |
| 36 | 1 | "PSAK 71" menjadi dasar cadangan kerugian | TIDAK SESUAI (penomoran) | `https://web.iaiglobal.or.id/SAK-IAI/PSAK%20Umum` (diambil 2026-11-07): daftar SAK umum memuat "PSAK 109 Instrumen Keuangan", "PSAK 107 Instrumen Keuangan: Pengungkapan", "PSAK 232 ... Penyajian", "PSAK 239 ... Pengakuan dan Pengukuran"; "PSAK 71" tidak muncul. Hubungan 71 → 109 tidak dinyatakan eksplisit di halaman itu. |
| 37 | 1, 11 | "Audit OJK" atas model | TIDAK BISA DIVERIFIKASI | Tidak ada ketentuan spesifik yang disitir spec. Spec sendiri di §11 mengatakan pemetaan harus dikonfirmasi tim kepatuhan. |
| 38 | 11 | UU PDP: laporan tidak boleh memuat nilai PII | TERVERIFIKASI sebagian | UU 27/2022 Pasal 4 ayat (3) huruf f: "Data Pribadi yang dikombinasikan untuk mengidentifikasi seseorang" termasuk data pribadi umum. Hash dan kombinasi kuasi-identifier tetap data pribadi; lihat §11. |
| 39 | 11 | "Kerahasiaan bank" mengatur data ini | TIDAK SESUAI | UU 10/1998 Pasal 1 angka 28 dan UU 4/2023 (perubahan Pasal 1 angka 28): Rahasia Bank = informasi tentang "Nasabah Penyimpan dan Simpanan dari Nasabah Penyimpan". Data debitur kredit di luar definisi itu. |
| 40 | 11 | Pemetaan OJK/BI spesifik belum dipastikan | TERVERIFIKASI (spec jujur) | Tidak ada klaim hukum spesifik selain #36-#39; saya tidak mencari POJK manajemen risiko karena spec tidak mengklaimnya. |
| 41 | 13 | Cleanlab Datalab "belum diuji; konflik dependensi dengan `env-dc`" | TIDAK SESUAI | Lihat #8, #24, #25. Status "belum diuji" dapat diperbarui. |
| 42 | 13 | Deepchecks "semua kebocoran terdeteksi" pada data sintetis | TIDAK BISA DIVERIFIKASI | Skrip `deepchecks_leakage.py` dan data sintetis tidak ada di repo (`/root/data-leakage` hanya berisi spec.md dan folder ini). |
| 43 | 13, 4.2 | `leakage_check.py` "sudah ada" | TIDAK BISA DIVERIFIKASI | Berkas tidak ada di repo yang saya periksa. |
| 44 | 12.7 | 15 menit untuk 1 juta baris | TIDAK BISA DIVERIFIKASI | Spec sendiri menandai "perlu diukur". |
| 45 | 5 | Semua ambang (lihat §5 laporan ini) | KEPUTUSAN DESAIN | Spec menyatakan "bukan hasil kalibrasi". |
| 46 | 16 | Pertanyaan terbuka 1-7 | TIDAK BISA DIVERIFIKASI | Pertanyaan organisasi; lihat §9 laporan ini. |
| 47 | 9.2 | Format `config_hash: sha256:...`, MLflow tag | TIDAK DIUJI | Tidak berisiko; di luar lingkup verifikasi teknis ini. |

## 3. Detail §3.3 Environment dan dependensi

### 3.1 Hasil uji pin

Matriks uji (Python 3.11, dasar: `deepchecks==0.19.1 ppscore`, lalu variasi satu pin per sel):

| Variasi | Hasil `TrainTestSamplesMix` + suite | Catatan |
|---|---|---|
| sklearn 1.5.2, numpy 1.26.4, pandas 2.2.3, setuptools 80.10.2, pyarrow 19.0.1 | Lolos | baseline spec |
| sklearn 1.6.1 | Lolos | |
| sklearn 1.7.2 | Lolos | |
| sklearn 1.8.0 / 1.9.1 | Gagal | `get_scorer('max_error')` |
| pandas 2.3.3 | Lolos | |
| pandas 3.0.6 | Gagal pada display | `DataFrame.applymap` dihapus; `with_display=False` lolos |
| numpy 2.4.6 | Gagal | `np.Inf` dihapus |
| setuptools 81.0.0 | Lolos | warning deprecation |
| setuptools 82.0.0 / 84.2.1 | Gagal | `pkg_resources` hilang |
| pyarrow terbaru (26.0.1) + numpy 1.26.4 | Gagal | `pyarrow requires NumPy 2.0 or newer` |
| Python 3.12, semua pin spec | Lolos | |

Interpretasi: pin spec adalah subset aman. Memperlonggar (`scikit-learn<1.8`, `pandas<3`, `setuptools<82`) mungkin diterima, tetapi hanya satu skenario klasifikasi kecil yang diuji, jadi pelonggaran harus diuji ulang pada data nyata (termasuk jalur regresi) sebelum dipakai. Saran praktis: tetap pakai pin spec dan catat bahwa itu konservatif.

### 3.2 Status paket

| Paket | Versi terakhir | Tanggal | Catatan |
|---|---|---|---|
| deepchecks | 0.19.1 | 2024-12-15 | Repo aktif; commit terbaru 2025-11-24 (belum dirilis). Metadata tidak mencantumkan `ppscore`. |
| ppscore | 1.3.1 | 2026-03-11 | Tidak ada wheel (hanya sdist). Metadata tidak mendeklarasikan `requires_dist`. |
| cleanlab | 2.9.0 | 2026-01-13 | `requires_python >=3.10`; extra `datalab` menarik `datasets>=2.7.0`. |

Deepchecks menyertakan modul PPS sendiri (`deepchecks/ppscore.py`, pustaka `import deepchecks.ppscore as pps`). Jadi "ppscore" di `env-dc` hanya diperlukan untuk `ppscore_check.py` (Detektor C), bukan untuk Deepchecks.

## 4. Detail §2 dan §4 (taksonomi dan detektor)

### 4.1 L2 dan konfigurasi `index_col`

`guard.yaml` memberi `entity_col: customer_id` dan `index_col: application_id`. Pemetaan spec: L2 → `IndexTrainTestLeakage`. Karena check membandingkan kolom `index_name`, ada dua kebutuhan yang bertabrakan:

- Untuk L2, `index_name` harus kolom entitas (`customer_id`).
- Untuk L5 (`IdentifierLabelCorrelation`), `index_name` harus kolom ID berurutan (`application_id`) karena hanya kolom itu yang diperiksa.

Satu `Dataset` hanya punya satu `index_name`. Jadi spec perlu menjalankan check dua kali dengan dua objek `Dataset` berbeda (satu per peran), atau memindahkan L2 sepenuhnya ke `leakage_check.py` (group overlap) dan memakai `IndexTrainTestLeakage` hanya sebagai pendukung. Selain itu, `IndexTrainTestLeakage` pada `application_id` tetap berguna untuk duplikasi aplikasi (mendekati L1).

### 4.2 L5 dan `IdentifierLabelCorrelation`

- Hanya mengevaluasi `index` dan `datetime`. Kolom ID lain (mis. `nomor_aplikasi` yang bukan `index_name`) diabaikan.
- Default `max_pps=0`; spec memakai 0,2 (WARNING 0,1). Ini keputusan desain yang perlu dicatat, bukan "ambang bawaan".
- Dengan ppscore murni, ID kategorikal unik bernilai 0 (lihat #31). Jadi deteksi L5 di ppscore hanya bekerja untuk ID numerik.

### 4.3 L3

`DateTrainTestLeakageOverlap` sesuai dengan `temporal` di §5. `DateTrainTestLeakageDuplicates` mengukur tanggal bersama, bukan ketimpangan urutan; pada split acak harian selalu tinggi. Spec boleh tetap memakainya, tetapi harus memberi tahu bahwa metrik ini bukan padanan `temporal`.

### 4.4 L7

Deepchecks `MultivariateDrift` adalah klasifier domain atas semua fitur; `adversarial` di §5 memakai "AUC fitur tunggal". Dua pengukuran berbeda. Ambang `adversarial` (0,70 / 0,95) tidak punya padanan di Deepchecks (default setara AUC 0,625). Cleanlab Datalab juga punya issue type `non_iid` yang relevan untuk L7 dan tidak dipakai spec; opsional.

### 4.5 L8

Detail perilaku Datalab:

- `near_duplicate_sets` berisi indeks baris lain (bukan baris itu sendiri); filter lintas-split di spec (anggota train dan test) bisa diimplementasi dengan kolom `__split__` seperti rancangan. Terverifikasi pada data uji.
- Near-duplicate juga menandai duplikat persis dan duplikat dalam satu split; filter lintas-split di kode sendiri memang diperlukan.
- Ambang `threshold=0.13` relatif terhadap median jarak tetangga terdekat. Pada fitur campuran (one-hot + numerik) skala jarak ditentukan encoding; spec §4.5 sudah menandai ini untuk diverifikasi.
- Datalab menerima `data` DataFrame dengan `label_name`; `features` harus numerik.

## 5. Ambang dan katalog (§5, §8)

Klasifikasi: **S** = ada nilai default pada sumber primer yang sama; **D** = keputusan desain tanpa dasar sumber.

| Ambang spec | Nilai | Klasifikasi | Keterangan |
|---|---|---|---|
| `row_overlap` warn >0%, crit ≥1% | | D | Deepchecks `TrainTestSamplesMix` default kondisi 5%. |
| `group_overlap` crit >0 entitas | | D | Konsisten dengan `IndexTrainTestLeakage` default 0. |
| `temporal` warn >0%, crit ≥5% | | D | Deepchecks Date* default 0. |
| `temporal_embargo` selalu warning | | D | |
| `single_feature` 0,85 / 0,95 | | D | Tidak ada padanan; custom detector. |
| `pps_train` 0,5 / 0,8 | | S sebagian | Deepchecks `FeatureLabelCorrelation` default 0,8 = crit. Warn 0,5 D. |
| `identifier_label` 0,1 / 0,2 | | D | Deepchecks default 0. |
| `adversarial` 0,70 / 0,95 | | D | Deepchecks `MultivariateDrift` default drift 0,25 (AUC 0,625). |
| `near_dup_cross_split` >0 / ≥1% test | | D | Cleanlab `threshold=0.13` mengatur seberapa dekat, bukan batas jumlah. |
| `runtime.max_rows` 100.000 | | S sebagian | Cocok dengan `n_samples=100_000` default `FeatureLabelCorrelation`; bukan default ppscore (5.000). |
| `seed: 42` | | S sebagian | Deepchecks `random_state=42` default untuk banyak check. |
| `embargo_days: 30`, `maturity_window_days: 365` | | D | Pertanyaan terbuka #1; harus ditetapkan per model. |

Rekomendasi: label kolom "sumber ambang" di `guard.yaml` (`basis: deepchecks_default | desain | kalibrasi`) agar auditor tahu mana yang sudah dikalibrasi. Kalibrasi pada model historis tetap di Fase 4 (§14).

## 6. Pencegahan L6 (§6)

- Aturan semgrep: valid; false positive pada pemakaian benar (lihat #33). Saran: hanya tandai `fit_transform` pada variabel yang menjadi argumen `train_test_split`/`cross_val_*` sesudahnya, atau gunakan taint mode; atau perlakukan hasil semgrep sebagai WARNING dan tidak memblokir.
- *Pipeline integrity test*: perilaku dasar scikit-learn (clone dan fit ulang di dalam CV) tidak diuji di sini; tidak berisiko.

## 7. Strategi split (§7)

- `skfolio.model_selection.CombinatorialPurgedCV` terverifikasi ada (skfolio 1.12.7); `purged_size` dan `embargo_size` dalam jumlah observasi, bukan hari. Konversi `embargo_days` → observasi bergantung pada frekuensi data; untuk data kredit dengan banyak baris per hari, konversi tidak langsung. Spec sudah menandai kelayakan perlu dievaluasi.
- Tidak ada klaim sumber lain di §7 yang bisa disalahkan.

## 8. Konfigurasi (§8)

- Kunci `data.entity_col`, `time_col`, `index_col`: lihat §4.1 mengenai `index_col`.
- `prediction.prediction_date_col: application_date` sama dengan `time_col`: tidak ada masalah, tetapi `temporal` memakai `time_col` sedangkan `prediction_date` berbeda secara konsep bila data berupa snapshot bulanan. Perlu penjelasan di spec.
- Waiver `finding_id: group_overlap:customer_id` dan `expires: 2027-02-28`: tidak ada klaim eksternal.

## 9. Pertanyaan terbuka (§16) dan cara menjawabnya

Tidak ada yang bisa dijawab dari sumber primer teknis; semuanya keputusan organisasi. Cara menjawab:

| # | Pertanyaan | Cara menjawab | Pemilik |
|---|---|---|---|
| 1 | `embargo_days` / `maturity_window_days` | Ukur dari data historis: `maturity_window_days` = jendela definisi default (mis. 90+ DPD dalam 12 bulan → ≥ 365 hari); `embargo_days` ≥ jendela fitur berjendela terpanjang. Dokumentasikan per model. | Pemilik model + model risk |
| 2 | Metadata `available_at` | Audit katalog fitur / feature store; hitung proporsi fitur tanpa metadata. Bila belum ada, jadikan prasyarat Fase 1. | Data engineering |
| 3 | Integrasi tiket (Jira) | Keputusan kebijakan; sisipkan pada Gate sebagai langkah opsional. | Model risk / engineering |
| 4 | Pemberi waiver CRITICAL | Kebijakan model risk internal; rekomendasi spec: `owner` + `approved_by` (dua orang berbeda). | Model risk |
| 5 | HTML Deepchecks di luar zona training | Nilai risiko: laporan HTML dapat memuat potongan data (spec §11). Putuskan bersama keamanan informasi; bila perlu, matikan tampilan sampel (`with_display=False` atau n_to_show kecil) atau simpan hanya JSON. Berdasarkan UU PDP Pasal 4(3)(f), potongan data dengan kombinasi atribut dapat menjadi data pribadi. | Keamanan informasi + kepatuhan |
| 6 | Dua bahasa | Keputusan audit eksternal; secara teknis template dua bahasa sederhana (`report.language`). | Kepatuhan |
| 7 | Pengisi `owner_assessment` | Tetapkan peran (bukan orang) di `guard.yaml`, mis. `model_owner_role` dengan eskalasi ke kepala tim; kebijakan tata kelola. | Model risk |

## 10. Status verifikasi internal (§13) yang perlu diperbarui

| Baris §13 | Status saran |
|---|---|
| Cleanlab Datalab "Belum diuji" | Diuji di cleanlab 2.9.0 pada data sintetis kecil: `near_duplicate_sets`, kolom hasil, dan deteksi lintas-split terverifikasi. Belum diuji: data campuran, skala jutaan baris. |
| "Konflik dependensi dengan `env-dc`" | Tidak terbukti bila `pyarrow<=19.0.1` dipin. |
| ppscore "Diuji" | Benar. Tambahkan catatan `sample=5000` dan blind spot ID kategorikal. |
| `deepchecks_leakage.py` "Diuji" | Skrip tidak ada di repo; tidak bisa diverifikasi. |
| Ambang default "Belum dikalibrasi" | Benar. |

## 11. Regulasi dan kepatuhan (§1, §11)

Spec hanya mengklaim empat hal: PSAK 71, "audit OJK", UU PDP/kerahasiaan bank, dan keselarasan model risk. Tidak ada klaim POJK, SR 11-7, atau BI yang spesifik; saya tidak menambahkannya.

- **PSAK 71.** Daftar SAK umum IAI (halaman resmi) saat ini mencantumkan "PSAK 109 Instrumen Keuangan" dan tidak memuat "PSAK 71". Saran: tulis "PSAK 109 (sebelumnya PSAK 71)" **hanya setelah** hubungan penomoran itu dikonfirmasi dari dokumen resmi IAI atau OJK; saya tidak menemukan pernyataan eksplisit di halaman yang diambil. Status: TIDAK SESUAI pada penomoran; konsep (penyisihan kerugian kredit ekspektasian) tidak saya bantah.
- **UU PDP.** Teks: UU No. 27 Tahun 2022 (`https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022`, PDF `.../Download/224884/UU%20Nomor%2027%20Tahun%202022.pdf`).
  - Pasal 4 ayat (3) huruf f: data yang dikombinasikan untuk mengidentifikasi seseorang adalah data pribadi umum. Implikasi: meng-hash `customer_id` atau membuang `nik` saja tidak membuat laporan bebas data pribadi bila ada kombinasi kuasi-identifier (usia, wilayah, tanggal aplikasi). Spec perlu daftar kuasi-identifier, bukan hanya `pii_columns`.
  - Pasal 34: wajib Penilaian Dampak (DPIA) bila ada "pengambilan keputusan secara otomatis" dengan akibat signifikan (ayat 2 huruf a) atau "evaluasi, penskoran, atau pemantauan yang sistematis" (huruf d). Credit scoring termasuk. Ini lebih relevan untuk model yang dilindungi gate ini daripada untuk gate-nya, tetapi layak disebut sebagai konteks kepatuhan.
  - Pasal 10 ayat (1): hak keberatan atas keputusan yang hanya didasarkan pada pemrosesan otomatis, termasuk pemrofilan.
- **Kerahasiaan bank.** UU No. 10 Tahun 1998 (`https://peraturan.bpk.go.id/Details/45486/uu-no-10-tahun-1998`) Pasal 1 angka 28 dan UU No. 4 Tahun 2023 (`https://peraturan.bpk.go.id/Details/240203/uu-no-4-tahun-2023`): Rahasia Bank adalah informasi tentang nasabah penyimpan dan simpanannya. Data debitur untuk credit scoring tidak dicakup definisi ini. Saran: ubah "UU PDP / kerahasiaan bank" menjadi "UU PDP (UU 27/2022); kerahasiaan bank (UU Perbankan, sebagaimana diubah UU 4/2023) berlaku bila data memuat nasabah penyimpan". Ketentuan lanjutan (POJK) tidak diperiksa.
- **Model risk / OJK.** TIDAK BISA DIVERIFIKASI: spec tidak menyebut ketentuan yang bisa dicek. Saran: tetap seperti kalimat penutup §11 (konfirmasi bersama kepatuhan), dan bila ingin mengutip, kutip POJK yang berlaku setelah ditelusuri di `https://www.ojk.go.id`.

## 12. Cara mereproduksi (ringkas)

```
uv venv --python 3.11 dc
uv pip install --python dc/bin/python deepchecks==0.19.1 ppscore "scikit-learn<1.6" "numpy<2" "pandas<2.3" "setuptools<81" "pyarrow<=19.0.1"
# variasi: ganti satu pin (scikit-learn==1.8.0, setuptools==82.0.0, pandas==3.*, numpy>=2)
# gabungan: tambah "cleanlab[datalab]" ke perintah di atas; jalankan Datalab(data=df, label_name="y").find_issues(features=X, issue_types={"near_duplicate":{}, "label":{}, "outlier":{}})
# semgrep: uv pip install semgrep; semgrep --validate --config r.yaml
```

Semua skrip dan virtualenv uji ada di `/tmp/claude-0/w` (sementara; tidak disimpan di repo).

## 13. Daftar koreksi yang disarankan untuk spec.md

Urutan menurut dampak.

1. **§2 L2 / §4.3 / §8:** pisahkan peran `index`. Tulis bahwa `IndexTrainTestLeakage` hanya mendeteksi overlap entitas jika `index_name` = kolom entitas (`customer_id`), dan bahwa `IdentifierLabelCorrelation` hanya memeriksa kolom `index`/`datetime`. Usulan: dua pemanggilan dengan dua `Dataset`, atau `leakage_check.py` sebagai sumber utama L2.
2. **§3.3:** ganti alasan terisolasinya `env-cl`. Teks usulan: "`cleanlab[datalab]` dapat dipasang bersama Deepchecks bila `pyarrow<=19.0.1` dan `numpy<2` dipin (diuji 7 Nov 2026), tetapi tetap dipisahkan agar rilis `datasets`/`pyarrow` baru tidak memaksa `numpy>=2` di `env-dc`." Perbarui juga §13 baris Cleanlab, §15 baris pertama, dan hapus "menarik pyarrow terbaru".
3. **§3.3:** tambahkan versi Python (disarankan 3.11 atau 3.12; 3.13 belum diuji). Cantumkan bahwa pin spec konservatif: batas yang gagal pada uji adalah `scikit-learn>=1.8`, `pandas>=3`, `setuptools>=82`, `numpy>=2`. Alasan `scikit-learn<1.6`: "scorer `max_error` deprecated sejak 1.6 dan dihapus di 1.8".
4. **§4.3:** ubah "ambang 0,2" menjadi "ambang 0,2 (pilihan desain; default Deepchecks 0)". Ubah "(ambang PPS 0,8)" menjadi "(0,8 = default Deepchecks)".
5. **§4.4 dan §15 (ppscore):** (a) sebutkan `sample=` (default 5.000) harus diteruskan ke `pps.predictors` agar "maksimum 100.000" berlaku; (b) parameter bernama `random_seed`; (c) kolom kategorikal unik memperoleh skor 0, jadi PPS tidak mendeteksi ID string; (d) ganti "ppscore tidak aktif dikembangkan (rilis terakhir 1.3.x)" menjadi "ppscore dirilis jarang (1.3.0 Okt 2022, 1.3.1 Mar 2026); pelihara pin dan padanan internal"; (e) catat bahwa Deepchecks memakai modul PPS internalnya sendiri.
6. **§4.2:** ubah "setara PPS" menjadi "mirip secara konsep"; PPS memakai pohon tanpa batas kedalaman, CV 4-fold, metrik F1 ternormalisasi (klasifikasi).
7. **§1:** ganti "PSAK 71" dengan penomoran yang sudah dikonfirmasi dari IAI/OJK (daftar IAI saat ini: PSAK 109 Instrumen Keuangan). Tandai bahwa hubungan penomoran masih perlu konfirmasi.
8. **§11:** ganti "UU PDP / kerahasiaan bank" dengan rujukan yang tepat: UU 27/2022 (khususnya Pasal 4(3)(f), 10, 34) untuk data debitur; kerahasiaan bank hanya untuk nasabah penyimpan. Tambahkan kewajiban mengelola kuasi-identifier selain `pii_columns`, dan catat bahwa hash tidak menghapus status data pribadi.
9. **§5:** tambahkan kolom "basis ambang" (default Deepchecks / desain / kalibrasi) sesuai tabel §5 laporan ini.
10. **§4.4 / §5 `adversarial`:** jelaskan bahwa AUC fitur tunggal berbeda dari `MultivariateDrift` Deepchecks (semua fitur; `2*AUC-1`, default 0,25), dan pertimbangkan `non_iid` Datalab sebagai pendukung L7.
11. **§6.2:** tambahkan catatan bahwa aturan semgrep juga menandai pemakaian benar dan tidak mengimplementasikan klausa `train_test_split`; gunakan sebagai WARNING sampai dituning.
12. **§7 catatan skfolio:** tegaskan satuan `purged_size`/`embargo_size` (observasi), bukan hari.
13. **§13:** perbarui status Cleanlab; tandai `leakage_check.py` dan `deepchecks_leakage.py` sebagai belum ada di repo bila memang demikian, atau sertakan lokasinya.
14. **§4.3 L3:** catat bahwa `DateTrainTestLeakageDuplicates` mengukur tanggal bersama (bukan urutan waktu) dan akan menyala pada hampir semua split acak.

## 14. Batasan verifikasi

- Eksperimen memakai data sintetis kecil (100-1.000 baris) dan skenario klasifikasi; jalur regresi, data campuran, dan skala jutaan baris tidak diuji.
- Python 3.13 tidak diuji.
- Tidak mencari POJK/SE OJK, PBI, atau SR 11-7 karena spec tidak mengklaimnya.
- Tidak ada mekanisme yang memastikan "PSAK 71 ↔ PSAK 109" dari sumber IAI; hanya daftar standar terkini yang dilihat.
- Halaman peraturan.bpk.go.id adalah repositori resmi JDIH BPK; saya membaca PDF salinannya (ekstraksi teks bisa memuat salah OCR kecil, mis. "Pasal 4 (l)" untuk "(1)").
