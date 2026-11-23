"""
TAHAP 9 — Persiapan Clean Dataset  (Proposal 3.10)

Keluaran:
  - dataset_karhutla_2026_clean.parquet  (format utama, seluruh data)
  - dataset_karhutla_2026_clean_sample.csv (subset ringan untuk inspeksi/demo: N sel x semua tanggal)
  - kamus_data.csv (nama kolom, tipe, satuan, sumber, deskripsi)
  - qc_ringkasan.md + qc_report.json (laporan quality control)
  - raw_integrity.json (bukti: SHA-256 file mentah sebelum = sesudah pipeline -> file mentah tidak diubah)
"""
from __future__ import annotations
import pandas as pd

from pathlib import Path

from . import config as C
from .utils import QC, log, save_json, sha256_file

DICTIONARY = {
    "cell_id": ("ID sel grid ~5 km (kunci bersama cell_id+date)", "-", "grid"),
    "date": ("Tanggal pengamatan (YYYY-MM-DD)", "tanggal", "-"),
    "province": ("Provinsi tempat sel berada", "-", "geoBoundaries / grid"),
    "lat": ("Lintang pusat sel", "derajat", "grid"),
    "lon": ("Bujur pusat sel", "derajat", "grid"),
    "precip_mm": ("Curah hujan harian", "mm/hari", "CHIRPS (via GEE)"),
    "temp_c": ("Suhu udara 2 m (dari Kelvin)", "°C", "ERA5-Land (via GEE)"),
    "rh_pct": ("Kelembapan relatif (dihitung dari suhu & titik embun, rumus Magnus)", "%", "ERA5-Land (turunan)"),
    "wind_ms": ("Kecepatan angin 10 m = sqrt(u^2+v^2)", "m/s", "ERA5-Land (turunan)"),
    "soil_moist": ("Kelembapan tanah lapisan 1", "m3/m3", "ERA5-Land (via GEE)"),
    "n_imputed": ("Jumlah variabel cuaca yang diisi imputasi pada baris ini", "jumlah", "hasil wrangling"),
    "hotspot_count": ("Jumlah deteksi hotspot di sel pada tanggal tsb (0 = tidak ada deteksi)", "jumlah", "NASA FIRMS"),
    "frp_sum": ("Total Fire Radiative Power deteksi di sel-tanggal", "MW", "NASA FIRMS"),
    "frp_max": ("FRP maksimum deteksi di sel-tanggal", "MW", "NASA FIRMS"),
    "n_high_conf": ("Jumlah deteksi berkepercayaan tinggi", "jumlah", "NASA FIRMS"),
    "rain_prev7_mm": ("Akumulasi hujan 7 hari sebelumnya", "mm", "fitur turunan"),
    "rain_prev14_mm": ("Akumulasi hujan 14 hari sebelumnya", "mm", "fitur turunan"),
    "rain_prev30_mm": ("Akumulasi hujan 30 hari sebelumnya", "mm", "fitur turunan"),
    "dry_days_streak": ("Hari kering berturut-turut sampai hari t (hujan < 1 mm)", "hari", "fitur turunan"),
    "n_nominal_high": ("Jumlah deteksi berkepercayaan nominal/tinggi", "jumlah", "NASA FIRMS"),
    "split": ("Pembagian waktu: train (sebelum Agu-7hari) / val (Agu) / test (Sep) / excluded", "kategori", "penanda"),
    "hotspot_prev7": ("Jumlah hotspot 7 hari sebelumnya", "jumlah", "fitur turunan"),
    "hotspot_prev14": ("Jumlah hotspot 14 hari sebelumnya", "jumlah", "fitur turunan"),
    "frp_prev7": ("Total FRP 7 hari sebelumnya", "MW", "fitur turunan"),
    "temp_prev7_mean": ("Rata-rata suhu 7 hari sebelumnya", "°C", "fitur turunan"),
    "rh_prev7_mean": ("Rata-rata RH 7 hari sebelumnya", "%", "fitur turunan"),
    "soil_prev7_mean": ("Rata-rata kelembapan tanah 7 hari sebelumnya", "m3/m3", "fitur turunan"),
    "wind_prev7_mean": ("Rata-rata kecepatan angin 7 hari sebelumnya", "m/s", "fitur turunan"),
    "month_2026": ("Bulan pengamatan", "1-12", "fitur turunan"),
    "province_code": ("Kode numerik provinsi (urutan di config.PROVINCES)", "kode", "fitur turunan"),
    "y_hotspot_next7": ("TARGET: 1 bila ada >=1 hotspot pada t+1..t+7, 0 bila tidak; kosong bila 7 hari ke depan belum lengkap", "0/1", "fitur turunan"),
    "warmup": ("True = 14 hari awal, fitur historis belum lengkap (jangan dipakai modeling)", "bool", "penanda"),
    "out_multivariat": ("Penanda anomali multivariat (Isolation Forest)", "bool", "penanda outlier"),
}


def verify_raw(provenance: list[dict], qc: QC) -> dict:
    changed = []
    for p in provenance:
        path = p.get("abs_path")
        if path and sha256_file(Path(path)) != p["sha256"]:
            changed.append(p["file"])
    res = {"files_checked": len(provenance), "files_changed": changed, "raw_intact": not changed}
    save_json(res, C.P.qc / "raw_integrity.json")
    qc.add("9_export", "file_mentah_utuh", res["raw_intact"])
    return res


def run(d: pd.DataFrame, selected: list[str], raw: dict, qc: QC) -> dict:
    out_cols = [c for c in DICTIONARY if c in d.columns]
    out_cols += [c for c in d.columns if c.startswith("out_") and c not in out_cols]
    final = d[out_cols].copy()

    # ---- pemeriksaan akhir (bukti 'clean')
    key_dups = int(final.duplicated(["cell_id", "date"]).sum())
    assert key_dups == 0, "Dataset akhir masih punya duplikasi cell_id+date"
    assert (final["date"] == final["date"].dt.normalize()).all(), "Tanggal harus tanpa komponen jam (YYYY-MM-DD)"
    met = [c for c in ("precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist") if c in final.columns]
    qc.add("9_export", "missing_variabel_cuaca_akhir", int(final[met].isna().sum().sum()))
    qc.add("9_export", "duplikasi_cell_date_akhir", key_dups)
    qc.add("9_export", "baris_akhir", len(final))
    qc.add("9_export", "kolom_akhir", final.shape[1])

    pq = C.P.cleaned / "dataset_karhutla_2026_clean.parquet"
    final.to_parquet(pq, index=False)

    # CSV ringan: N sel (acak tetap, mewakili semua provinsi) x semua tanggal
    cells = final[["cell_id", "province"]].drop_duplicates()
    per_prov = max(1, C.CSV_SAMPLE_CELLS // max(cells["province"].nunique(), 1))
    pick = (cells.groupby("province", group_keys=False)
                 .apply(lambda g: g.sample(min(len(g), per_prov), random_state=C.RANDOM_STATE)))["cell_id"]
    sample = final[final["cell_id"].isin(pick)]
    csv = C.P.cleaned / "dataset_karhutla_2026_clean_sample.csv"
    sample.to_csv(csv, index=False, date_format="%Y-%m-%d")
    qc.add("9_export", "csv_sample_baris", len(sample))

    # kamus data
    kd = pd.DataFrame([{"kolom": c, "tipe": str(final[c].dtype),
                        "deskripsi": DICTIONARY.get(c, ("Penanda outlier IQR untuk variabel terkait", "bool", "penanda outlier"))[0],
                        "satuan": DICTIONARY.get(c, ("", "bool", ""))[1],
                        "sumber": DICTIONARY.get(c, ("", "", "penanda outlier"))[2],
                        "dipakai_model": c in selected} for c in final.columns])
    kd.to_csv(C.P.cleaned / "kamus_data.csv", index=False)

    integ = verify_raw(raw["provenance"], qc)
    qc.add("9_export", "file_hasil", [pq.name, csv.name, "kamus_data.csv"])
    write_qc_markdown(qc, final, integ)
    qc.save()
    log.info("Clean dataset: %s (%.1f MB)", pq, pq.stat().st_size / 1e6)
    return {"final": final, "dictionary": kd, "integrity": integ}


def write_qc_markdown(qc: QC, final: pd.DataFrame, integ: dict):
    S = qc.data["stages"]
    g = lambda st, k, default="-": S.get(st, {}).get(k, default)
    fr = g("3_cleaning_firms", "ringkasan", {})
    mt = g("3_cleaning_meteo", "ringkasan", {})
    lines = [
        "# Ringkasan Quality Control (dibuat otomatis oleh pipeline)", "",
        f"Mode: **{qc.data['mode']}**  |  Waktu proses: {round(__import__('time').time() - qc.t0)} detik", "",
        "## Sebelum vs sesudah",
        "| Tahap | Indikator | Nilai |", "|---|---|---|",
        f"| Ingestion | baris FIRMS mentah | {g('1_ingest', 'firms_rows_raw')} |",
        f"| Ingestion | baris CHIRPS / ERA5 mentah | {g('1_ingest', 'chirps_rows_raw')} / {g('1_ingest', 'era5_rows_raw')} |",
        f"| Cleaning FIRMS | tanggal non-ISO diperbaiki | {fr.get('tanggal_format_diperbaiki', '-')} |",
        f"| Cleaning FIRMS | koordinat tak valid dibuang | {fr.get('koordinat_tidak_valid_dibuang', '-')} |",
        f"| Cleaning FIRMS | duplikat deteksi dibuang | {fr.get('duplikat_dibuang', '-')} |",
        f"| Cleaning FIRMS | baris akhir | {fr.get('baris_akhir', '-')} |",
        f"| Cleaning cuaca | duplikat persis dibuang (CHIRPS) | {mt.get('chirps_duplikat_persis_dibuang', '-')} |",
        f"| Cleaning cuaca | nilai di luar domain -> NaN | {mt.get('nilai_di_luar_domain_jadi_nan', '-')} |",
        f"| Missing | strategi imputasi terpilih | {g('3_missing', 'strategi_imputasi_terpilih')} |",
        f"| Missing | nilai diimputasi | {g('3_missing', 'nilai_diimputasi_total')} |",
        f"| Integrasi | baris sebelum / sesudah join | {g('4_integration', 'baris_sebelum_join')} / {g('4_integration', 'baris_sesudah_join')} |",
        f"| Integrasi | duplikasi cell_id+date | {g('4_integration', 'duplikasi_cell_date')} |",
        f"| Outlier | anomali multivariat (IsoForest) | {g('5_outlier', 'isolation_forest_n_anomali')} |",
        f"| Fitur | proporsi kelas positif target | {g('7_features', 'proporsi_kelas_positif')} |",
        f"| Akhir | baris x kolom | {len(final)} x {final.shape[1]} |",
        f"| Akhir | file mentah utuh (SHA-256) | {integ['raw_intact']} |", "",
        "Detail lengkap: `qc_report.json`, tabel di `outputs/tables/`, profil di `outputs/profiling/`.",
    ]
    (C.P.qc / "qc_ringkasan.md").write_text("\n".join(lines), encoding="utf-8")
