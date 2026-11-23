# Cheat Sheet Tanya Jawab (Pemahaman Teori Individu = 20%)

Format: **pertanyaan → jawaban singkat → lokasi kode**. Hafalkan alasannya, bukan kalimatnya.

## Integrasi & ingestion
1. **Kenapa grid 0,045°?** ≈ 5 km, mendekati resolusi CHIRPS (0,05°). ERA5-Land ±9 km, jadi beberapa sel bertetangga berbagi nilai ERA5 yang mirip — ini keterbatasan, bukan kesalahan. → `config.GRID_RES`
2. **Bagaimana titik FIRMS masuk ke grid?** Sel terdekat via KD-Tree; jika jarak ke pusat > 0,75×resolusi, titik dianggap di luar grid dan dicatat. → `s01_ingest.assign_to_grid`
3. **Kenapa `left join` + `validate="one_to_one"`?** Tabel cuaca adalah basis (satu baris per sel-hari). Bila ada duplikat kunci, pandas melempar error → mustahil terjadi penggandaan baris diam-diam. → `s04_integration.integrate`
4. **Kenapa hotspot kosong diisi 0 tapi cuaca kosong tidak?** Tidak ada deteksi = fakta (0). Cuaca kosong = informasi hilang (NaN) → tidak boleh dianggap 0.
5. **Apa itu data provenance & bukti file mentah utuh?** Catatan asal + SHA-256 tiap file di awal dan akhir; sama berarti tidak berubah. → `s01.file_provenance`, `s09.verify_raw`

## Profiling & cleaning
6. **Kenapa −9999 diganti NaN?** Itu kode "tidak ada data" CHIRPS, bukan curah hujan; jika dibiarkan merusak rata-rata. → `s03._prep_table`
7. **Kenapa suhu Kelvin→Celsius dan RH dihitung?** Satuan harus seragam & mudah ditafsirkan; RH dari suhu + titik embun (rumus Magnus). → `s03.clean_meteo`
8. **Duplikat hotspot dibuang berdasarkan apa?** Lokasi+tanggal+jam+satelit+instrumen sama. Deteksi berbeda jam/satelit di sel yang sama tetap dipertahankan. → `s03.clean_firms`
9. **Nilai mustahil vs outlier?** RH 140% atau −273 °C = kesalahan data → NaN. Hujan 100 mm/hari = ekstrem tetapi mungkin → dipertahankan + flag. → `config.DOMAIN_RULES`

## Missing values
10. **Kenapa membandingkan strategi imputasi?** Tidak ada strategi yang selalu benar. Kami menyembunyikan 5% nilai asli di periode validasi/uji, mengisinya dengan tiap strategi, lalu mengukur NRMSE. → `s03.compare_imputation`
11. **Kenapa hanya strategi "kausal"?** Interpolasi memakai nilai hari berikutnya = informasi masa depan bocor ke fitur. Ia hanya ditampilkan sebagai pembanding.
12. **Kenapa statistik imputasi dari periode train saja?** Agar data validasi/uji tidak memengaruhi nilai pengisi. → `_impute(..., train_mask)`
13. **Keterbatasan?** Uji masking mengandaikan hilang acak (MCAR); sel yang *seluruhnya* tanpa ERA5 hanya terisi rata-rata global (ditandai `n_imputed`).

## Outlier
14. **Rumus IQR?** Batas = Q1 − 1,5·IQR dan Q3 + 1,5·IQR. → `s05.iqr_bounds`
15. **Kenapa IQR hujan/FRP dihitung pada nilai >0?** Data zero-inflated: Q1=Q3=0 membuat setiap hari hujan tampak outlier. → `config.IQR_ON_POSITIVE`
16. **Kenapa outlier tidak dihapus?** Pada data lingkungan ekstrem sering kejadian nyata yang justru penting; dibandingkan keep/cap/remove, lalu diputuskan *keep + flag*. → `outlier_perbandingan_perlakuan.csv`
17. **Isolation Forest?** Memisahkan titik "mudah terisolasi" lewat pohon acak; menangkap kombinasi janggal antar variabel. `contamination=0,5%` adalah asumsi yang bisa diubah. → `s05.isolation_forest_flag`

## Scaling
18. **Z-score vs Min-Max?** Z = (x−μ)/σ; Min-Max = (x−min)/(max−min) ke [0,1]. Min-Max peka outlier.
19. **Kenapa parameter dari train?** Menghindari kebocoran informasi uji. **Kenapa LightGBM tanpa scaling?** Model pohon hanya membandingkan urutan nilai. → `s06_scaling`

## Fitur
20. **Kenapa `shift(1)` sebelum rolling?** Fitur untuk tanggal t hanya boleh memakai t−1 dan sebelumnya. Dibuktikan oleh `test_tidak_ada_data_leakage_pada_fitur_historis`. → `s07.build_features`
21. **Target?** 1 bila ada ≥1 hotspot pada t+1…t+7; 7 hari terakhir data tidak punya target (NaN). 14 hari awal ditandai `warmup`.
22. **Reshaping apa yang dilakukan?** `pivot_table` (provinsi×bulan), `melt` (unpivot variabel cuaca), `groupby` mingguan. → `s07.reshape_examples`
23. **Seleksi fitur?** Buang konstan; pada pasangan |Spearman|>0,95 buang yang kurang berkorelasi dengan target; peringkat Mutual Information. → `s07.select_features`
24. **Catatan `month_2026`:** train Jan–Jul, uji September; bulan uji tak ada di train, jadi fitur ini tidak informatif untuk model pohon (dipertahankan karena ada di proposal).

## Korelasi
25. **Pearson vs Spearman?** Pearson = linear pada nilai; Spearman = pada peringkat, tahan outlier & distribusi miring (cocok untuk hujan/FRP). **Korelasi bukan sebab-akibat.** → `s08`

## Klasifikasi
26. **Kenapa split temporal + embargo 7 hari?** Acak membocorkan masa depan (hotspot hari berdekatan sangat mirip). Target t melihat t+7, jadi baris train terakhir harus ≥7 hari sebelum validasi. → `utils.temporal_split`
27. **Kenapa PR-AUC, bukan akurasi?** Kelas positif jarang; akurasi tinggi hanya dengan menebak 0. Pembanding wajar: PR-AUC baseline = proporsi positif. → `s10`
28. **Ambang klasifikasi?** Dipilih dari validasi (maks. F1), lalu dipakai di uji — bukan disetel pada data uji.
29. **Kenapa klasifikasi hanya "analisis lanjutan"?** Rubrik: wrangling 35%, analisis lanjutan 15%; klasifikasi sekadar bukti kegunaan data.

## Umum
30. **Parquet vs CSV?** Parquet: kolom bertipe, terkompresi, cepat untuk jutaan baris. CSV hanya subset ringan untuk inspeksi.
31. **Reproduktibilitas?** Semua parameter di `config.py`, `random_state=42`, versi library di `requirements.txt`, satu perintah `run_pipeline.py`.
32. **Keterbatasan data?** Hotspot = deteksi satelit, bukan kebakaran terkonfirmasi; resolusi ERA5 kasar; subset data (bila dipakai).
