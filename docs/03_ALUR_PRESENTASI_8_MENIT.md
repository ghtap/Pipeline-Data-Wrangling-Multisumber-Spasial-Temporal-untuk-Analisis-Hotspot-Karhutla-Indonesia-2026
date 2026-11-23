# Alur Presentasi 8 Menit (+10 menit tanya jawab)

Panduan Bab IV: 8 menit slide + 10 menit tanya jawab teori/kode. Semua anggota wajib hadir dan **semua** bisa ditanya.
Ganti angka `[…]` dengan hasil data ASLI Anda (`outputs/quality_control/qc_ringkasan.md`, `outputs/tables/`). Jangan pakai angka demo.

| # | Slide | Waktu | Isi (satu kalimat kunci) | Gambar/tabel siap pakai | Penyaji |
|---|---|---|---|---|---|
| 1 | Judul & identitas | 0:15 | Nama, NIM, Kelas INT25, nama kelompok | – | |
| 2 | Masalah & tujuan | 0:40 | Karhutla perlu data terintegrasi; sumber beda format/resolusi/satuan → tidak bisa digabung langsung | – | |
| 3 | Sumber data | 1:00 | FIRMS (titik) vs CHIRPS 0,05° vs ERA5-Land ~9 km (raster) + geoBoundaries; satu grid 0,045° | tabel Proposal 2.1 | |
| 4 | Alur 10 tahap | 0:45 | Diagram alur (Gambar 1 proposal); kunci integrasi `cell_id+date` | Gambar 1 proposal | |
| 5 | Profiling & cleaning | 1:10 | Temuan mentah → perbaikan: `[n]` tanggal non-ISO, `[n]` duplikat, `[n]` kode −9999, `[n]` nilai mustahil | `outputs/figures/profil_missing_*.png`, `qc_ringkasan.md` | |
| 6 | Missing & outlier | 1:10 | 6 strategi imputasi diuji dengan *masking* → terpilih `[strategi]`; outlier ekstrem valid dipertahankan + flag | `imputasi_perbandingan.png`, `outlier_distribusi.png` | |
| 7 | Integrasi & fitur | 1:00 | Join `one_to_one`, 0 duplikasi; fitur historis `shift(1)` → bebas leakage; target 7 hari | tabel contoh fitur (notebook Tahap 7), `pivot_hotspot_provinsi_bulan.png` | |
| 8 | Korelasi & seleksi | 0:45 | Heatmap Spearman; `[n]` fitur redundan dibuang | `heatmap_korelasi_spearman.png`, `seleksi_fitur.csv` | |
| 9 | Clean dataset & bukti kegunaan | 0:45 | Parquet + kamus data; PR-AUC `[x]` vs baseline `[prevalensi]` (split temporal) | `klasifikasi_pr_curve.png` | |
| 10 | Kesimpulan, batasan, kontribusi | 0:30 | Kualitas data = fondasi; batasan: hotspot ≠ kebakaran terkonfirmasi; siapa mengerjakan apa | – | |

Total 8:00. Latih dengan stopwatch; potong slide 4 atau 8 bila molor.

## Tips
* Buka notebook **sudah dijalankan** (data asli) sebagai cadangan; jangan menjalankan pipeline penuh saat presentasi.
* Jangan menyebut PR-AUC 0,5533 sebagai hasil baru — itu rujukan DIMAS-TI (Proposal 3.11).
* Setiap penyaji menguasai kode bagiannya (lihat `docs/04_CHEAT_SHEET_TANYA_JAWAB.md`); dosen bisa menunjuk siapa saja untuk menjelaskan baris kode.
* Identitas (Nama, NIM, Kelas, Nama Kelompok) wajib ada di slide.
