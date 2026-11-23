# Checklist Pengumpulan (Panduan Bab III)

**Tempat:** slot submission LMS SiDia · **Batas:** paling lambat **H-2** sebelum sesi presentasi Minggu ke-15 · **Telat:** potongan nilai 10%.

**Nama arsip (.zip/.rar):** `NoKelompok_NIM1_NIM2_NIM3`  → mis. `07_25031554023_25031554194_25031554173.zip` *(ganti 07 dengan nomor kelompok Anda)*

| ✔ | Berkas wajib | Letak di folder ini | Catatan |
|---|---|---|---|
| ☐ | **Raw data** ≥ 2 sumber | `data/raw_sample/` | FIRMS + GEE (CHIRPS/ERA5) + geoBoundaries + grid. Jika subset: dijelaskan di laporan + persetujuan dosen. **Bukan data demo.** |
| ☐ | **Source code** utuh | `notebooks/Data_Wrangling_Karhutla_2026.ipynb` + `scripts/` + `requirements.txt` + `config` | Notebook sudah dijalankan pada data asli, kotak *ISI* terisi |
| ☐ | **Clean data** | `data/cleaned/` | parquet + CSV sampel + `kamus_data.csv` |
| ☐ | **Laporan PDF** | `laporan/` | Semua tahap + **pembagian kontribusi anggota** (lihat `docs/07_KERANGKA_LAPORAN.md`) |
| ☐ | **Presentasi PPT** | `presentasi/` | Ringkasan untuk pemaparan (lihat `docs/03`) |
| ☐ | Identitas di laporan & slide | – | Nama, NIM, Kelas, **Nama Kelompok** |

## Sebelum zip
* ☐ `python scripts/run_pipeline.py` sukses pada data asli, `pytest -q` lulus
* ☐ `outputs/` berisi hasil data ASLI (hapus sisa hasil demo bila ada; demo ada di `data/demo/`, jangan ikut dizip)
* ☐ `raw_integrity.json` → `raw_intact: true`
* ☐ Hapus `.venv/`, `__pycache__/`, `data/demo/`, file besar yang tidak perlu
* ☐ Ukuran arsip sesuai batas LMS
* ☐ Pernyataan pemanfaatan AI diperbarui di laporan
* ☐ Semua anggota hadir saat presentasi (kelompok lain juga wajib hadir di kelas)
