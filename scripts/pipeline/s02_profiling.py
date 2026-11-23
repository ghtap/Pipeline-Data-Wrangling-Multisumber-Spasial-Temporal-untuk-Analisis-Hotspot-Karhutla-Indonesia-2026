"""
TAHAP 2 — Data Profiling & Audit Kualitas  (Proposal 3.3)

Memeriksa data MENTAH sebelum diubah: tipe data, struktur, statistik deskriptif,
missing values, duplikat, rentang tanggal/koordinat, dan nilai di luar domain.
Hasilnya disimpan sebagai tabel + gambar sehingga kondisi AWAL bisa dibandingkan
dengan kondisi SESUDAH cleaning.
"""
from __future__ import annotations
import re

import numpy as np
import pandas as pd

from . import config as C
from .utils import QC, log, save_fig, resolve_columns

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def profile_table(df: pd.DataFrame, name: str, save: bool = True) -> pd.DataFrame:
    """Satu baris per kolom: tipe, jumlah/persen missing, nilai unik, contoh nilai, statistik numerik."""
    rows = []
    n = len(df)
    for c in df.columns:
        s = df[c]
        r = {"column": c, "dtype": str(s.dtype), "n_missing": int(s.isna().sum()),
             "pct_missing": round(100 * s.isna().mean(), 3), "n_unique": int(s.nunique(dropna=True))}
        is_num = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        if is_num:
            x = pd.to_numeric(s, errors="coerce").astype("float64")
            r.update(min=x.min(), q1=x.quantile(0.25), median=x.median(), mean=x.mean(),
                     q3=x.quantile(0.75), max=x.max(), std=x.std())
        else:
            top = s.dropna().astype(str).value_counts().head(3)
            r["top_values"] = "; ".join(f"{k} ({v})" for k, v in top.items())
            # kolom teks yang sebenarnya angka? hitung entri yang gagal dikonversi (nilai tidak konsisten)
            if not pd.api.types.is_bool_dtype(s):
                num = pd.to_numeric(s, errors="coerce")
                if num.notna().mean() > 0.9:
                    r["n_non_numeric"] = int(num.isna().sum() - s.isna().sum())
        rows.append(r)
    out = pd.DataFrame(rows)
    if save:
        out.to_csv(C.P.profiling / f"profil_{name}.csv", index=False)
    return out


def check_dates(s: pd.Series) -> dict:
    """Berapa persen tanggal yang BUKAN format YYYY-MM-DD?"""
    t = s.dropna().astype(str).str.strip()
    non_iso = int((~t.str.match(ISO)).sum())
    return {"n_total": int(len(t)), "n_non_iso": non_iso, "pct_non_iso": round(100 * non_iso / max(len(t), 1), 3),
            "contoh_non_iso": t[~t.str.match(ISO)].head(5).tolist()}


def firms_audit(firms: pd.DataFrame) -> dict:
    d = resolve_columns(firms, C.FIRMS_ALIASES, required=("lat", "lon", "acq_date"), name="FIRMS (audit)")
    lat, lon = pd.to_numeric(d["lat"], errors="coerce"), pd.to_numeric(d["lon"], errors="coerce")
    bb = C.INDONESIA_BBOX
    out = {
        "n_rows": len(d), "n_cols": d.shape[1],
        "tanggal": check_dates(d["acq_date"]),
        "koordinat_di_luar_indonesia": int((~lat.between(*bb["lat"]) | ~lon.between(*bb["lon"])).sum()),
        "koordinat_tidak_numerik": int(lat.isna().sum() + lon.isna().sum() - d["lat"].isna().sum() - d["lon"].isna().sum()),
    }
    if "frp" in d.columns:
        frp = pd.to_numeric(d["frp"], errors="coerce")
        out["frp_negatif"] = int((frp < 0).sum())
        out["frp_missing"] = int(frp.isna().sum())
    keys = [c for c in ("lat", "lon", "acq_date", "acq_time", "satellite", "instrument") if c in d.columns]
    out["duplikat_kunci_deteksi"] = int(d.duplicated(keys).sum())
    cats = {}
    for c in ("confidence", "satellite", "instrument", "daynight"):
        if c in d.columns:
            cats[c] = d[c].astype(str).str.strip().value_counts(dropna=False).head(15).to_dict()
    out["kategori_mentah"] = cats       # label tidak konsisten (mis. 'h', 'High', 'HIGH') terlihat di sini
    return out


def gee_audit(chirps: pd.DataFrame, era5: pd.DataFrame) -> dict:
    out = {"chirps_rows": len(chirps), "era5_rows": len(era5),
           "tanggal_chirps": check_dates(chirps["date"]),
           "duplikat_cell_date_chirps": int(chirps.duplicated(["cell_id", "date"]).sum()),
           "duplikat_cell_date_era5": int(era5.duplicated(["cell_id", "date"]).sum())}
    p = pd.to_numeric(chirps["precip_mm"], errors="coerce")
    out["precip_sentinel_atau_negatif"] = int((p < 0).sum())
    for c in C.ERA5_COLS:
        if c in era5.columns:
            v = pd.to_numeric(era5[c], errors="coerce")
            out[f"{c}_missing"] = int(v.isna().sum())
            out[f"{c}_sentinel"] = int(v.isin(C.NODATA_SENTINELS).sum())
    return out


def plot_missing(prof: pd.DataFrame, name: str):
    import matplotlib.pyplot as plt
    p = prof[prof["pct_missing"] > 0].sort_values("pct_missing")
    fig, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * max(len(p), 1) + 1)))
    if p.empty:
        ax.text(0.5, 0.5, "Tidak ada missing value", ha="center", va="center")
        ax.axis("off")
    else:
        ax.barh(p["column"], p["pct_missing"], color="#c0504d")
        ax.set_xlabel("% missing")
        ax.set_title(f"Missing values — {name} (data mentah)")
    return save_fig(fig, f"profil_missing_{name}.png")


def run(raw: dict, qc: QC) -> dict:
    profiles = {}
    for nm, df in (("firms_mentah", raw["firms"]), ("chirps_mentah", raw["chirps"]), ("era5_mentah", raw["era5"])):
        profiles[nm] = profile_table(df, nm)
        plot_missing(profiles[nm], nm)
    audit = {"firms": firms_audit(raw["firms"]), "gee": gee_audit(raw["chirps"], raw["era5"])}
    qc.add("2_profiling", "audit_mentah", audit)
    from .utils import save_json
    save_json(audit, C.P.profiling / "audit_data_mentah.json")
    log.info("Profiling selesai. Lihat folder %s", C.P.profiling)
    return {"profiles": profiles, "audit": audit}
