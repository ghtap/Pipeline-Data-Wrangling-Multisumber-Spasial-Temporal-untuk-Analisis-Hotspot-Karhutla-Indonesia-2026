# UAS Data Wrangling — Pipeline Karhutla 2026

Pipeline data wrangling multisumber spasial-temporal (NASA FIRMS + CHIRPS + ERA5-Land + geoBoundaries) untuk 6 provinsi,
Jan–Sep 2026. Mengikuti **10 tahap pada Bab III proposal**. Hanya bagian pipeline data (tanpa aplikasi web / model penelitian lama).

> ⚠️ **Status penting:** kode sudah diuji end-to-end memakai **data SINTETIS** (`--demo`). Data asli DIMAS-TI belum pernah dijalankan
> di sini (hanya daftar berkasnya yang terlihat). Jalankan pada data asli, baca pesan error bila ada nama kolom yang berbeda
> (perbaiki di `scripts/pipeline/config.py`), dan **tafsirkan hasil asli Anda sendiri**. Hasil/angka demo tidak boleh dikumpulkan.

## 1. Mulai di VS Code (5 menit)
```bash
# buka folder ini di VS Code: File > Open Folder > uas_data_wrangling
python -m venv .venv
.venv\Scripts\activate            # Windows   |   source .venv/bin/activate  (Mac/Linux)
pip install -r requirements.txt
# VS Code: Ctrl+Shift+P > "Python: Select Interpreter" > pilih .venv
```
Pasang ekstensi yang disarankan (VS Code akan menawarkan): Python, Jupyter.

## 2. Uji coba dulu (data sintetis, ±1 menit)
```bash
python scripts/run_pipeline.py --demo
pytest -q                          # 8 tes: kunci unik, leakage, split temporal, dll.
```
Hasil demo ada di `data/demo/` (terpisah dari folder hasil asli).

## 3. Pakai data asli
```bash
# salin data mentah dari proyek DIMAS-TI (tidak mengubah aslinya); persempit bila terlalu besar
python scripts/copy_raw_from_dimasti.py --root "D:/DIMAS-TI/karhutla" --provinces riau jambi --date-from 2026-06-01
python scripts/run_pipeline.py
```
Lalu buka `notebooks/Data_Wrangling_Karhutla_2026.ipynb`, **Run All**, dan isi kotak *ISI* (keputusan + interpretasi).
Debug: tombol ▶ di VS Code (`Run and Debug` → "Pipeline - DATA ASLI").

Data mentah yang dibutuhkan (`data/raw_sample/`):
| Folder | Isi |
|---|---|
| `firms/` | CSV FIRMS (kolom standar: latitude, longitude, acq_date, acq_time, frp, confidence, satellite, …) |
| `gee/` | CSV ekspor GEE: CHIRPS (hujan) + ERA5-Land (suhu, titik embun, kelembapan tanah, angin u/v) per `cell_id`/`date` |
| `boundary/` | zip/geojson geoBoundaries ADM1 Indonesia |
| `static/` | `grid.csv` (cell_id, lat, lon, province) — opsional; bila kosong, grid dibangun dari batas wilayah |

## 4. Peta pipeline
| Tahap | Modul (`scripts/pipeline/`) | Output utama | Proposal |
|---|---|---|---|
| 1 Ingestion + provenance | `s01_ingest.py` | `outputs/quality_control/provenance_raw.json` | 3.2 |
| 2 Profiling | `s02_profiling.py` | `outputs/profiling/*` | 3.3 |
| 3 Standardisasi, cleaning, missing | `s03_cleaning.py` | `outputs/tables/perbandingan_strategi_imputasi.csv` | 3.4 |
| 4 Integrasi spasial-temporal | `s04_integration.py` | `data/interim/04_integrated.parquet` | 3.5 |
| 5 Outlier | `s05_outliers.py` | `outputs/tables/outlier_*.csv` | 3.6 |
| 6 Scaling | `s06_scaling.py` | `outputs/quality_control/scaler_params_train_only.json` | 3.7 |
| 7 Fitur, reshaping, seleksi | `s07_features.py` | `outputs/tables/seleksi_fitur.csv` | 3.8 |
| 8 EDA & korelasi | `s08_eda_corr.py` | `outputs/figures/heatmap_korelasi_*.png` | 3.9 |
| 9 Clean dataset | `s09_export.py` | `data/cleaned/dataset_karhutla_2026_clean.parquet`, `kamus_data.csv` | 3.10 |
| 10 Klasifikasi | `s10_classification.py` | `outputs/klasifikasi_metrik.json` | 3.11 |

Semua parameter (resolusi grid, aturan domain, horizon, tanggal split, alias kolom) ada di `scripts/pipeline/config.py`.

## 5. Dokumen pendukung (`docs/`)
1. `01_GAP_ANALISIS.md` — apa yang kurang di proposal dibanding panduan, dan risikonya
2. `02_PEMETAAN_DIMASTI_KE_UAS.md` — file DIMAS-TI mana yang diambil / diabaikan
3. `03_ALUR_PRESENTASI_8_MENIT.md` — slide demi slide + pembagian waktu
4. `04_CHEAT_SHEET_TANYA_JAWAB.md` — 32 pertanyaan teori/kode yang mungkin ditanyakan
5. `05_CHECKLIST_PENGUMPULAN.md` — aturan arsip & berkas wajib
6. `06_KONTRIBUSI_ANGGOTA.md` — template pembagian & bukti kontribusi
7. `07_KERANGKA_LAPORAN.md` — kerangka laporan PDF

## 6. Struktur folder
```
uas_data_wrangling/
├── data/{raw_sample, interim, cleaned}   ├── notebooks/Data_Wrangling_Karhutla_2026.ipynb
├── scripts/{run_pipeline.py, make_demo_data.py, copy_raw_from_dimasti.py, pipeline/}
├── outputs/{profiling, figures, quality_control, tables}   ├── tests/   ├── docs/
└── laporan/   presentasi/            (tempat PDF & PPT)
```
