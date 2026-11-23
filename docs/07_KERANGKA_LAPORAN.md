# Kerangka Laporan PDF (Panduan: "seluruh tahapan hingga pembagian kontribusi")

Gunakan struktur proposal (Bab I–VI) sebagai tulang, lalu ganti "rencana" menjadi "hasil". Identitas wajib di sampul.

| Bab | Isi | Ambil dari |
|---|---|---|
| Sampul & ringkasan | Nama, NIM, Kelas, Nama Kelompok; ringkasan hasil dengan angka asli | proposal, `qc_ringkasan.md` |
| I Pendahuluan | latar belakang, rumusan, tujuan, manfaat, batasan, literatur | proposal 1.1–1.7 (perbarui referensi) |
| II Sumber data | 4 sumber, format, kondisi awal | proposal Bab II + `provenance_raw.json`, `audit_data_mentah.json` |
| III Hasil per tahap | 1 ingestion · 2 profiling (tabel+gambar) · 3 cleaning & imputasi · 4 integrasi · 5 outlier · 6 scaling · 7 fitur & seleksi · 8 korelasi · 9 clean dataset | `outputs/tables/`, `outputs/figures/`, notebook |
| IV Analisis lanjutan | klasifikasi: split temporal, metrik, interpretasi, batasan | `klasifikasi_metrik.json`, gambar PR-curve |
| V Pembahasan | keputusan metodologis & alasannya (missing, outlier, leakage), keterbatasan, perbandingan dengan angka DIMAS-TI | kotak *ISI* notebook |
| VI Penutup | kesimpulan & saran | – |
| Lampiran | tautan repositori, kode penting, sumber data & lisensi, **kontribusi anggota** (`docs/06`), **pernyataan pemanfaatan AI (diperbarui)** | – |
