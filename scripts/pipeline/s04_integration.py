"""
TAHAP 4 — Integrasi Spasial-Temporal  (Proposal 3.5)

Aturan emas: SATU BARIS = SATU SEL GRID PADA SATU TANGGAL  (kunci: cell_id + date).
Langkah:
  1. Deteksi FIRMS (titik koordinat) dipetakan ke sel grid terdekat.
  2. Deteksi dalam sel & tanggal yang sama diagregasi -> hotspot_count, frp_sum, frp_max.
  3. Tabel cuaca (CHIRPS+ERA5) di-LEFT JOIN dengan agregat hotspot, validate='one_to_one'
     sehingga pandas menggagalkan proses bila ada penggandaan baris.
  4. Sel-tanggal tanpa deteksi diisi 0 (artinya 'tidak ada hotspot'), BUKAN missing.
"""
from __future__ import annotations
import pandas as pd

from . import config as C
from .s01_ingest import assign_to_grid
from .utils import QC

KEYS = ["cell_id", "date"]


def aggregate_hotspots(firms: pd.DataFrame, grid: pd.DataFrame, qc: QC) -> pd.DataFrame:
    f = assign_to_grid(firms, grid)
    n_unmatched = int(f["cell_id"].isna().sum())
    qc.add("4_integration", "deteksi_firms_di_luar_grid_dibuang", n_unmatched)
    f = f[f["cell_id"].notna()].rename(columns={"acq_date": "date"})
    f["is_high"] = (f["confidence"] == "high") if "confidence" in f.columns else False
    f["is_nom_high"] = f["confidence"].isin(["nominal", "high"]) if "confidence" in f.columns else True
    hs = (f.groupby(KEYS)
            .agg(hotspot_count=("lat", "size"), frp_sum=("frp", "sum"), frp_max=("frp", "max"),
                 n_high_conf=("is_high", "sum"), n_nominal_high=("is_nom_high", "sum"))
            .reset_index())
    hs["hotspot_count"] = hs["hotspot_count"].astype("int32")
    hs["n_high_conf"] = hs["n_high_conf"].astype("int32")
    hs["n_nominal_high"] = hs["n_nominal_high"].astype("int32")
    qc.add("4_integration", "deteksi_firms_dipetakan", len(f))
    qc.add("4_integration", "pasangan_cell_date_dengan_hotspot", len(hs))
    return hs


def integrate(meteo: pd.DataFrame, hs: pd.DataFrame, qc: QC) -> pd.DataFrame:
    assert not meteo.duplicated(KEYS).any(), "Tabel cuaca harus unik per cell_id+date sebelum join"
    n_base = len(meteo)

    # hotspot yang jatuh di sel/tanggal tanpa data cuaca (tidak punya pasangan) -> dicatat, bukan dihilangkan diam-diam
    chk = hs.merge(meteo[KEYS], on=KEYS, how="left", indicator=True)
    orphan = chk[chk["_merge"] == "left_only"]
    qc.add("4_integration", "pasangan_hotspot_tanpa_data_cuaca", len(orphan))
    qc.add("4_integration", "deteksi_hilang_karena_tanpa_cuaca", int(orphan["hotspot_count"].sum()))
    if len(orphan):
        orphan.drop(columns="_merge").to_csv(C.P.tables / "hotspot_tanpa_data_cuaca.csv", index=False)

    out = meteo.merge(hs, on=KEYS, how="left", validate="one_to_one")
    for c in ("hotspot_count", "n_high_conf", "n_nominal_high"):
        out[c] = out[c].fillna(0).astype("int32")
    for c in ("frp_sum", "frp_max"):
        out[c] = out[c].fillna(0).astype("float32")

    # ----- pemeriksaan integritas hasil integrasi
    assert len(out) == n_base, "Jumlah baris berubah setelah join -> ada penggandaan observasi!"
    assert not out.duplicated(KEYS).any(), "Ada duplikasi cell_id+date pada hasil integrasi"
    qc.add("4_integration", "baris_sebelum_join", n_base)
    qc.add("4_integration", "baris_sesudah_join", len(out))
    qc.add("4_integration", "duplikasi_cell_date", 0)
    qc.add("4_integration", "jumlah_sel", int(out["cell_id"].nunique()))
    qc.add("4_integration", "rentang_tanggal", [out["date"].min(), out["date"].max()])
    qc.add("4_integration", "persen_baris_ada_hotspot", round(100 * float((out["hotspot_count"] > 0).mean()), 3))
    out = out.sort_values(KEYS).reset_index(drop=True)
    out.to_parquet(C.P.interim / "04_integrated.parquet", index=False)
    return out


def run(clean: dict, raw: dict, qc: QC) -> pd.DataFrame:
    hs = aggregate_hotspots(clean["firms"], raw["grid"], qc)
    return integrate(clean["meteo"], hs, qc)
