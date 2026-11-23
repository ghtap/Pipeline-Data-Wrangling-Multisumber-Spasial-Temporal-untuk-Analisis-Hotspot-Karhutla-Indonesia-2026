# Gap Analisis: Proposal vs Panduan Project Akhir Data Wrangling

Dibandingkan: *Proposal_Data_Wrangling_Karhutla_2026* ↔ *Panduan Project Akhir (Gasal 2026/2027)*.
Kolom "Kode" menunjuk modul yang sudah disiapkan di folder ini.

## A. Yang sudah tercakup

| Tuntutan Panduan | Di proposal | Kode / output |
|---|---|---|
| Min. 2 sumber data berbeda (rubrik menulis 3) | FIRMS, CHIRPS, ERA5-Land + geoBoundaries (4) | `s01_ingest.py` |
| Ingestion & integrasi (merge/join/concat) | 3.2, 3.5 | `s01`, `s04` (join `one_to_one`) |
| Profiling: tipe, struktur, summary stats, missing, tidak konsisten | 3.3 | `s02_profiling.py` → `outputs/profiling/` |
| Imputasi/hapus missing | 3.4d | `s03` (6 strategi dibandingkan) |
| Format tanggal YYYY-MM-DD, duplikat | 3.4a,c | `s03` |
| Outlier + alasan penanganan | 3.6 | `s05` → `outputs/tables/outlier_*.csv` |
| Min-Max / Z-score | 3.7 | `s06` (keduanya ditunjukkan) |
| Korelasi + heatmap | 3.9 | `s08` |
| Klasifikasi / clustering | 3.11 | `s10` (LightGBM + LogReg + baseline) |
| Clean data, source code, raw data | 5.1 | `data/cleaned/`, notebook + `scripts/`, `data/raw_sample/` |

## B. Yang KURANG di proposal (dan statusnya)

| # | Kekurangan | Risiko | Sudah ditangani di kode? | Tindakan manual |
|---|---|---|---|---|
| 1 | **Tugas anggota ke-3 (Lady) kosong** di 4.4 | Panduan: anggota tanpa kontribusi bukti = nilai 0; rubrik kontribusi 15% | Tidak (soal manusia) | Isi `docs/06_KONTRIBUSI_ANGGOTA.md` dengan pembagian nyata |
| 2 | Nama arsip di proposal `NoKelompok_NIM1_NIM2`, padahal panduan `NoKelompok_NIM1_NIM2_NIM3` dan kelompok Anda 3 orang | Salah format penamaan | – | Pakai 3 NIM |
| 3 | **No. kelompok & nama kelompok belum ada** | Wajib di identitas laporan & slide | Placeholder di notebook | Isi |
| 4 | **Reshaping** (pivot/unpivot/groupby) tidak disebut eksplisit | Poin Bab II-4a | Ya: `s07.reshape_examples` | Jelaskan di laporan |
| 5 | **Seleksi fitur** tidak eksplisit (hanya "indikasi redundansi") | Panduan: "lakukan seleksi fitur jika diperlukan" | Ya: `s07.select_features` | Tafsirkan tabel `seleksi_fitur.csv` |
| 6 | **String cleaning** (label `confidence`, satelit, spasi/huruf besar) tidak disebut | Poin Bab II-2c | Ya: `s03.clean_firms` | – |
| 7 | Outlier hanya univariat | Panduan: univariat *atau* multivariat → sudah cukup, multivariat nilai tambah | Ya: Isolation Forest | – |
| 8 | Bukti **file mentah tidak diubah** hanya klaim | Indikator 5.2 | Ya: SHA-256 sebelum/sesudah → `raw_integrity.json` | – |
| 9 | Anti-**data leakage** hanya klaim | Kualitas metodologi | Ya: `shift(1)`, split temporal + embargo 7 hari, `tests/test_pipeline.py` | – |
| 10 | **Laporan PDF & PPT** belum ada | Wajib dikumpulkan | Kerangka di `docs/07`, alur di `docs/03` | Tulis/buat dari hasil asli |

## C. Ketidakkonsistenan di Panduan (tanyakan ke dosen/asisten)

1. Bab II-1 "minimal **2** sumber" vs rubrik "minimal **3** sumber" → proposal (3 sumber + 1 pendukung) aman untuk keduanya.
2. Bab III-5 "PPT untuk pemaparan **5 menit**" vs Bab IV "**8 menit** slide + 10 menit tanya jawab". Siapkan 8 menit; pastikan ke dosen.
3. Rubrik melompat dari nomor 2 ke 4 (nomor 3 hilang); total bobot tetap 100.

## D. Risiko integritas akademik (penting)

* Proposal menyatakan proyek **mengadaptasi dataset DIMAS-TI 2026**. Panduan menjatuhkan nilai 0 untuk plagiarisme/manipulasi data.
  Mitigasi yang sudah dirancang: pipeline menjalankan **ulang seluruh wrangling dari data mentah**, angka DIMAS-TI (22.553 grid, 5.841.227 baris, PR-AUC 0,5533) hanya **rujukan pembanding**.
  Jangan hanya memuat `dataset_gabungan_2026.parquet` lama lalu menyebutnya hasil UAS.
* Bila DIMAS-TI dikerjakan bersama orang di luar kelompok UAS ini (manifest memuat nama `orang_a/b/c`), sebutkan peran mereka dan sitasi di laporan.
* **Data demo sintetis** (`--demo`) tidak boleh masuk arsip atau dipresentasikan sebagai hasil.
* Pernyataan pemanfaatan AI di proposal menjanjikan dokumentasi bantuan AI pada tahap pelaksanaan → **perbarui** di laporan akhir (mis. bantuan penulisan kerangka kode pipeline).
* Jika angka hasil pipeline berbeda dari tabel 2.3 proposal, **jelaskan** perbedaannya; jangan dipaksa sama.

## E. Praktis

* Data mentah DIMAS-TI > 1 GB (`firms_raw.csv` 262 MB; 120 file GEE ≈ 731 MB; zip geoBoundaries 14 MB). Batas unggah LMS belum diketahui → siapkan **subset** (provinsi/rentang tanggal) dan minta **persetujuan dosen** (Proposal 4.2). Skrip: `scripts/copy_raw_from_dimasti.py`.
* Referensi proposal masih "awal": verifikasi & samakan gaya sitasi dosen.
* Nama kolom GEE asli belum terlihat (manifest hanya memuat nama file). Bila pipeline berhenti dengan pesan "kolom wajib tidak ditemukan", tambahkan nama kolom ke `config.GEE_ALIASES` / `FIRMS_ALIASES`.
