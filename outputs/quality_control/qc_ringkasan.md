# Ringkasan Quality Control (dibuat otomatis oleh pipeline)

Mode: **real**  |  Waktu proses: 469 detik

## Sebelum vs sesudah
| Tahap | Indikator | Nilai |
|---|---|---|
| Ingestion | baris FIRMS mentah | 2613261 |
| Ingestion | baris CHIRPS / ERA5 mentah | 6156969 / 6156969 |
| Cleaning FIRMS | tanggal non-ISO diperbaiki | 0 |
| Cleaning FIRMS | koordinat tak valid dibuang | 0 |
| Cleaning FIRMS | duplikat deteksi dibuang | 0 |
| Cleaning FIRMS | baris akhir | 817096 |
| Cleaning cuaca | duplikat persis dibuang (CHIRPS) | 0 |
| Cleaning cuaca | nilai di luar domain -> NaN | {'temp_c': 0, 'dewpoint_c': 0, 'wind_ms': 0, 'soil_moist': 0, 'precip_mm': 0} |
| Missing | strategi imputasi terpilih | ffill_cell |
| Missing | nilai diimputasi | 307944 |
| Integrasi | baris sebelum / sesudah join | 6156969 / 6156969 |
| Integrasi | duplikasi cell_id+date | 0 |
| Outlier | anomali multivariat (IsoForest) | 30828 |
| Fitur | proporsi kelas positif target | 0.0652 |
| Akhir | baris x kolom | 6156969 x 39 |
| Akhir | file mentah utuh (SHA-256) | True |

Detail lengkap: `qc_report.json`, tabel di `outputs/tables/`, profil di `outputs/profiling/`.