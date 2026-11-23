# Pipeline Data Wrangling Multisumber Spasial-Temporal untuk Analisis Hotspot Karhutla Indonesia 2026

Project akhir mata kuliah **Data Wrangling** (Semester Gasal 2026/2027).
Pipeline end-to-end yang mengubah empat sumber data mentah yang berbeda format, resolusi, dan satuan menjadi **satu dataset bersih sel-grid × hari** untuk enam provinsi rawan karhutla (Riau, Jambi, Sumatera Selatan, Kalimantan Barat, Kalimantan Tengah, Kalimantan Selatan), periode 1 Januari – 30 September 2026.

**Tim:** Ghita Natasha Putri · Sabrina Matrza Aulia · Lady Puspa Khansa Yuasa — Kelas INT25 — Kelompok: 4

## Hasil ringkas

| Indikator | Nilai |
|---|---|
| Unit pengamatan | 22.553 sel grid (±5 km) × 273 hari = **6.156.969 baris**, 39 kolom |
| Kunci integrasi | `cell_id + date`, 0 duplikasi, join `one_to_one` |
| Missing value | 307.944 nilai cuaca diimputasi dengan *forward-fill* per sel (dipilih dari 6 strategi yang diuji) |
| Outlier | IQR + Isolation Forest; nilai ekstrem valid dipertahankan dan diberi penanda |
| Target | ada hotspot dalam 7 hari ke depan (proporsi positif keseluruhan 6,5%) |
| Pembuktian kegunaan data | LightGBM PR-AUC **0,659** vs baseline prevalensi 0,201 (split temporal: latih s.d. Juli, validasi Agustus, uji September) |
| Integritas data mentah | SHA-256 file mentah sebelum = sesudah pipeline |

Catatan: prevalensi positif data latih 1,8% sedangkan data uji 20,1% (September adalah puncak musim kebakaran), sehingga ada pergeseran distribusi. Klasifikasi dipakai sebagai bukti kelayakan data, bukan tujuan utama.

## Sumber data

| Sumber | Isi | Penyedia |
|---|---|---|
| NASA FIRMS | titik panas (hotspot) | NASA |
| CHIRPS | curah hujan harian | Climate Hazards Center, UC Santa Barbara |
| ERA5-Land | suhu, titik embun, kelembapan tanah, angin | Copernicus / ECMWF |
| geoBoundaries | batas provinsi | geoBoundaries (William & Mary geoLab) |

CHIRPS dan ERA5-Land diekstrak melalui Google Earth Engine. **Data mentah dan dataset bersih lengkap tidak disertakan di repositori ini** karena ukurannya (>1 GB); lihat bagian *Menjalankan dengan data asli*.

## Alur pipeline (10 tahap)

| Tahap | Modul (`scripts/pipeline/`) | Keluaran utama |
|---|---|---|
| 1 Ingestion + provenance (SHA-256) | `s01_ingest.py` | `outputs/quality_control/provenance_raw.json` |
| 2 Profiling & audit kualitas | `s02_profiling.py` | `outputs/profiling/` |
| 3 Standardisasi, cleaning, missing values | `s03_cleaning.py` | `outputs/tables/perbandingan_strategi_imputasi.csv` |
| 4 Integrasi spasial-temporal | `s04_integration.py` | `data/interim/04_integrated.parquet` |
| 5 Deteksi & penanganan outlier | `s05_outliers.py` | `outputs/tables/outlier_*.csv` |
| 6 Normalisasi & scaling | `s06_scaling.py` | `outputs/quality_control/scaler_params_train_only.json` |
| 7 Feature engineering, reshaping, seleksi fitur | `s07_features.py` | `outputs/tables/seleksi_fitur.csv` |
| 8 EDA & analisis korelasi | `s08_eda_corr.py` | `outputs/figures/heatmap_korelasi_*.png` |
| 9 Clean dataset & kamus data | `s09_export.py` | `data/cleaned/` |
| 10 Klasifikasi (analisis lanjutan) | `s10_classification.py` | `outputs/klasifikasi_metrik.json` |

Prinsip metodologis: fitur historis hanya memakai data sebelum tanggal pengamatan (`shift(1)` lalu rolling), split bersifat temporal dengan jeda 7 hari, dan seluruh statistik imputasi/scaling dihitung dari periode latih saja. Semua parameter ada di `scripts/pipeline/config.py`.

## Menjalankan

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows   |   source .venv/bin/activate  (Mac/Linux)
pip install -r requirements.txt
```

**Uji cepat dengan data sintetis** (tanpa data asli, ±1 menit; hanya untuk memeriksa kode):
```bash
python scripts/run_pipeline.py --demo
pytest -q                           # 8 tes: kunci unik, anti-leakage, split temporal, dll.
```

**Menjalankan dengan data asli:** letakkan data mentah di `data/raw_sample/`

| Folder | Isi |
|---|---|
| `firms/` | CSV FIRMS |
| `gee/` | CSV ekspor GEE (CHIRPS + ERA5-Land per sel-tanggal) |
| `boundary/` | zip/geojson geoBoundaries ADM1 Indonesia |
| `static/` | `grid.csv` (cell_id, lat, lon, province) — opsional |

```bash
python scripts/run_pipeline.py
```
Lalu buka `notebooks/Data_Wrangling_Karhutla_2026.ipynb` dan **Run All**. Nama kolom yang berbeda dapat disesuaikan di `config.py` (`FIRMS_ALIASES`, `GEE_ALIASES`).

## Struktur folder
```
├── data/{raw_sample, interim, cleaned}     (isi data tidak disertakan di GitHub)
├── notebooks/Data_Wrangling_Karhutla_2026.ipynb
├── scripts/{run_pipeline.py, make_demo_data.py, copy_raw_from_dimasti.py, isi_notebook.py, pipeline/}
├── outputs/{profiling, figures, quality_control, tables}
├── tests/          docs/          laporan/          presentasi/
```

## Dokumentasi pendukung (`docs/`)
`01_GAP_ANALISIS` · `02_PEMETAAN_DIMASTI_KE_UAS` · `03_ALUR_PRESENTASI_8_MENIT` · `04_CHEAT_SHEET_TANYA_JAWAB` · `05_CHECKLIST_PENGUMPULAN` · `06_KONTRIBUSI_ANGGOTA` · `07_KERANGKA_LAPORAN`

## Asal proyek dan pemanfaatan AI
