# Pemetaan Manifest DIMAS-TI → Pipeline UAS

Berdasarkan `DIMAS-TI-A_manifest.csv` (5.042 berkas). **Yang dibaca hanya daftar nama & ukuran berkas, bukan isinya** —
jadi kode di sini ditulis ulang mengikuti proposal, bukan hasil salin kode lama.

## Diambil (bagian pipeline data)

| Di proyek DIMAS-TI | Peran | Di folder ini |
|---|---|---|
| `data/raw/firms_raw.csv` (262 MB) | FIRMS mentah | `data/raw_sample/firms/` |
| `data/processing/gee_2026_downloads/gee26_<mulai>_<akhir>_<provinsi>_c00000_<hash>.csv` (120 file, ±731 MB) | CHIRPS + ERA5-Land hasil ekspor GEE, 6 provinsi × 20 jendela 2 minggu | `data/raw_sample/gee/` |
| `data/raw/geoBoundaries-IDN-ADM1-all.zip` | batas provinsi | `data/raw_sample/boundary/` |
| `data/interim/grid.csv` (22.553 sel) | grid acuan (agar `cell_id` sama) | `data/raw_sample/static/` |
| `src/data/*.py` (fetch_firms, fetch_climate, build_grid, prepare_boundary, make_dataset, build_features, …) | kode pipeline lama | **rujukan** — baca untuk mencocokkan dengan `scripts/pipeline/s01…s07` |
| `data/processed/QC_gabungan_2026.json`, `dataset_gabungan_2026.parquet` | hasil lama | **pembanding** angka Subbab 2.3 proposal, bukan bahan jadi |
| `notebooks/EDA_Cleaning.ipynb`, `Validasi_Grid.ipynb` | EDA lama | rujukan |

Salin otomatis (tidak mengubah/menghapus apa pun di DIMAS-TI):
`python scripts/copy_raw_from_dimasti.py --root "<path>/karhutla" [--provinces riau jambi] [--date-from 2026-06-01 --date-to 2026-09-30]`

## Sengaja TIDAK diambil

| Berkas | Alasan |
|---|---|
| `lightgbm-3.3.0/` (721 berkas C++/header), `lightgbm-3.3.0.tar.gz` | kode sumber library, bukan bagian proyek; pasang lewat `pip install lightgbm` |
| `karhutla/data/raw/firms_cache/` (3.938 CSV kecil) dan `firms_cache.zip` | cache unduhan; isinya sudah ada di `firms_raw.csv` (verifikasi sendiri) |
| `karhutla/results_orang_b/`, `reports/orang_b/`, `models_final/`, `figures/orang_b/` | tahap pemodelan penelitian lama (RandomForest, LightGBM v2/v3, SHAP) |
| `karhutla/dist_orang_c_2026/`, `src/app/` | aplikasi web peta risiko |
| `BACKUP_UAS_DATA_WRANGLING_2026.zip` (163 MB), `KIRIM_*`, `DIMASTI_BAHAN_MAKALAH_RINGKAS.zip` | arsip cadangan/kiriman |
| `data/processed/dataset_fitur_2026_v2/v3.parquet` (241 MB/150 MB) | fitur hasil lama — UAS harus membuat ulang |

## Sumber kecil lain di `data/raw/` (belum ada di proposal)
`suhu.csv`, `curah hujan.csv`, `kelembapan.csv`, `angin membawa ktp.csv`, `oni.csv`, `dmi_raw.txt`, `mcd64a1_monthly.csv`, `interim/enso_monthly.csv`, `src/data/gambut_indonesia_gpm2.tif`.
Tidak dipakai pipeline ini karena proposal menetapkan 3 sumber + geoBoundaries. Bila ingin menambah (mis. ONI/ENSO sebagai fitur iklim), ubah proposal/laporan dan tambahkan reader di `s01_ingest.py`.

## Mencocokkan hasil dengan angka proposal (Subbab 2.3)
Setelah menjalankan data asli, bandingkan `outputs/quality_control/qc_report.json` dengan: 22.553 grid · 5.841.227 observasi · 0 duplikasi grid-tanggal · 0 missing CHIRPS · 73.038 baris missing ERA5.
Selisih wajar bila Anda memakai subset atau aturan cleaning berbeda — **catat dan jelaskan**, jangan disamakan paksa.
