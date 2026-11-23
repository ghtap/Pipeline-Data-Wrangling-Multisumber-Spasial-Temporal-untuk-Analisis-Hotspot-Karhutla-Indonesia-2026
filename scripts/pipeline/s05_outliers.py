"""
TAHAP 5 — Deteksi & Penanganan Outlier  (Proposal 3.6)

Dua lapis:
  (1) Nilai MUSTAHIL secara fisik (mis. RH 140%, suhu -273 °C) sudah diubah jadi NaN di Tahap 3
      -> itu KESALAHAN DATA.
  (2) Nilai ekstrem yang MASIH MASUK AKAL (hujan deras, FRP besar) dideteksi dengan IQR (univariat)
      dan Isolation Forest (multivariat). Secara default DIPERTAHANKAN dan DIBERI PENANDA, karena
      di data lingkungan nilai ekstrem sering justru kejadian nyata yang penting.
Catatan: variabel zero-inflated (hujan, FRP, jumlah hotspot) dihitung IQR-nya hanya pada nilai > 0;
kalau tidak, Q1=Q3=0 dan SETIAP hari hujan akan salah dianggap outlier.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from . import config as C
from .utils import QC, log, save_fig

# hotspot_count tidak dimasukkan: variabel cacah diskret (Q1=Q3=1) sehingga IQR tidak bermakna
VARS = ["precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist", "frp_sum"]


def _base_series(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[col]
    if col in C.IQR_ON_POSITIVE:
        thr = C.WET_DAY_MM if col == "precip_mm" else 0
        s = s[s > thr]
    return s.dropna()


def iqr_bounds(s: pd.Series, k: float = C.IQR_K) -> tuple[float, float, float, float]:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return float(q1), float(q3), float(q1 - k * iqr), float(q3 + k * iqr)


def iqr_table(df: pd.DataFrame, qc: QC) -> pd.DataFrame:
    rows = []
    for c in [v for v in VARS if v in df.columns]:
        b = _base_series(df, c)
        q1, q3, lo, hi = iqr_bounds(b)
        out_mask = (b < lo) | (b > hi)
        rows.append({"variabel": c, "dasar_hitung": "nilai > 0" if c in C.IQR_ON_POSITIVE else "semua baris",
                     "n_dipakai": len(b), "Q1": q1, "Q3": q3, "IQR": q3 - q1, "batas_bawah": lo, "batas_atas": hi,
                     "n_outlier": int(out_mask.sum()), "pct_outlier": round(100 * out_mask.mean(), 3),
                     "min": float(b.min()), "max": float(b.max()), "keputusan": C.OUTLIER_DECISION.get(c, "keep_flag")})
    tab = pd.DataFrame(rows)
    tab.to_csv(C.P.tables / "outlier_iqr.csv", index=False)
    qc.add("5_outlier", "iqr", tab[["variabel", "n_outlier", "pct_outlier", "keputusan"]].to_dict("records"))
    return tab


def treatment_comparison(df: pd.DataFrame, tab: pd.DataFrame) -> pd.DataFrame:
    """Bandingkan 3 opsi perlakuan: pertahankan (keep), potong ke batas IQR (cap), buang baris (remove)."""
    rows = []
    for _, r in tab.iterrows():
        c = r["variabel"]
        s = df[c].dropna()
        capped = s.clip(r["batas_bawah"] if c not in C.IQR_ON_POSITIVE else s.min(), r["batas_atas"])
        removed = s[(s <= r["batas_atas"]) & ((s >= r["batas_bawah"]) | (c in C.IQR_ON_POSITIVE))]
        for nm, v in (("keep", s), ("cap", capped), ("remove", removed)):
            rows.append({"variabel": c, "opsi": nm, "n": len(v), "mean": v.mean(), "std": v.std(),
                         "skew": v.skew(), "max": v.max()})
    out = pd.DataFrame(rows)
    out.to_csv(C.P.tables / "outlier_perbandingan_perlakuan.csv", index=False)
    return out


def flag_iqr(df: pd.DataFrame, tab: pd.DataFrame) -> pd.DataFrame:
    """Beri penanda out_<var>. Perlakuan sesuai OUTLIER_DECISION (default: keep_flag = nilai tetap, diberi flag)."""
    d = df.copy()
    for _, r in tab.iterrows():
        c = r["variabel"]
        positive_only = c in C.IQR_ON_POSITIVE
        is_out = d[c] > r["batas_atas"]
        if not positive_only:                       # batas bawah hanya bermakna untuk variabel non zero-inflated
            is_out = is_out | (d[c] < r["batas_bawah"])
        d[f"out_{c}"] = is_out.fillna(False)
        dec = r["keputusan"]
        if dec == "cap":
            d[c] = d[c].clip(upper=r["batas_atas"])
        elif dec == "remove":
            d = d[~d[f"out_{c}"]]
    return d.reset_index(drop=True)


def isolation_forest_flag(df: pd.DataFrame, qc: QC) -> pd.DataFrame:
    """Outlier MULTIVARIAT: kombinasi nilai yang janggal walau tiap variabelnya tampak normal."""
    from sklearn.ensemble import IsolationForest
    cols = [c for c in ("temp_c", "rh_pct", "precip_mm", "wind_ms", "soil_moist") if c in df.columns]
    X = df[cols].to_numpy(dtype="float32")
    ok = ~np.isnan(X).any(axis=1)
    rng = np.random.default_rng(C.RANDOM_STATE)
    idx = np.flatnonzero(ok)
    fit_idx = rng.choice(idx, size=min(C.MV_FIT_ROWS, len(idx)), replace=False)
    iso = IsolationForest(n_estimators=100, contamination=C.MV_CONTAMINATION, random_state=C.RANDOM_STATE, n_jobs=-1)
    iso.fit(X[fit_idx])
    flag = np.zeros(len(df), dtype=bool)
    flag[ok] = iso.predict(X[ok]) == -1
    out = df.copy()
    out["out_multivariat"] = flag
    qc.add("5_outlier", "isolation_forest_n_anomali", int(flag.sum()))
    qc.add("5_outlier", "isolation_forest_pct", round(100 * flag.mean(), 3))
    return out


def plot_outliers(df: pd.DataFrame, tab: pd.DataFrame):
    import matplotlib.pyplot as plt
    cols = [c for c in ("precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist", "frp_sum") if c in df.columns]
    s = df.sample(min(len(df), 200_000), random_state=C.RANDOM_STATE)
    fig, axes = plt.subplots(2, len(cols), figsize=(3 * len(cols), 6))
    for j, c in enumerate(cols):
        v = s[c].dropna()
        if c in C.IQR_ON_POSITIVE:
            v = v[v > (C.WET_DAY_MM if c == "precip_mm" else 0)]
        axes[0, j].hist(v, bins=60, color="#4f81bd")
        axes[0, j].set_title(c + (" (>0)" if c in C.IQR_ON_POSITIVE else ""), fontsize=9)
        axes[1, j].boxplot(v, vert=True, showfliers=True, flierprops=dict(markersize=2, alpha=0.3))
        r = tab[tab["variabel"] == c]
        if len(r):
            axes[1, j].axhline(float(r["batas_atas"].iloc[0]), color="red", ls="--", lw=0.8)
    axes[0, 0].set_ylabel("histogram")
    axes[1, 0].set_ylabel("boxplot (garis merah = batas atas IQR)")
    fig.suptitle("Distribusi & outlier per variabel", y=1.0)
    fig.tight_layout()
    save_fig(fig, "outlier_distribusi.png")


def run(df: pd.DataFrame, qc: QC) -> tuple[pd.DataFrame, pd.DataFrame]:
    tab = iqr_table(df, qc)
    treatment_comparison(df, tab)
    plot_outliers(df, tab)
    d = flag_iqr(df, tab)
    d = isolation_forest_flag(d, qc)
    qc.add("5_outlier", "baris_setelah_perlakuan", len(d))
    d.to_parquet(C.P.interim / "05_outlier_flagged.parquet", index=False)
    return d, tab
