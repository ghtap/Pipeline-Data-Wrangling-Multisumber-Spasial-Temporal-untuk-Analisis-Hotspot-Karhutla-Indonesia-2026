"""
TAHAP 6 — Normalisasi & Scaling  (Proposal 3.7)

Z-score:  z = (x - mean) / std          Min-Max:  x' = (x - min) / (max - min)
Parameter dihitung HANYA dari periode train (date < VAL_START) agar informasi validasi/uji
tidak bocor ke transformasi. Dataset bersih tetap menyimpan satuan ASLI (mudah ditafsirkan);
scaling dipakai di dalam pipeline model yang memang sensitif skala (Logistic Regression),
dan TIDAK dipakai untuk LightGBM (model pohon tidak peka skala).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from . import config as C
from .utils import QC, save_fig, save_json

SCALE_COLS = ["precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist", "frp_sum"]


def fit_scalers(df: pd.DataFrame) -> dict:
    cols = [c for c in SCALE_COLS if c in df.columns]
    train = df[df["date"] < pd.Timestamp(C.VAL_START)]
    return {c: {"mean": float(train[c].mean()), "std": float(train[c].std()),
                "min": float(train[c].min()), "max": float(train[c].max())} for c in cols}


def apply_scalers(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c, p in params.items():
        out[f"{c}_z"] = (df[c] - p["mean"]) / (p["std"] or 1.0)
        rng = (p["max"] - p["min"]) or 1.0
        out[f"{c}_minmax"] = (df[c] - p["min"]) / rng
    return out


def run(df: pd.DataFrame, qc: QC) -> dict:
    params = fit_scalers(df)
    scaled = apply_scalers(df, params)
    save_json(params, C.P.qc / "scaler_params_train_only.json")

    rows = []
    for c in params:
        for nm, s in ((c, df[c]), (f"{c}_z", scaled[f"{c}_z"]), (f"{c}_minmax", scaled[f"{c}_minmax"])):
            rows.append({"kolom": nm, "mean": s.mean(), "std": s.std(), "min": s.min(), "max": s.max()})
    summ = pd.DataFrame(rows)
    summ.to_csv(C.P.tables / "scaling_sebelum_sesudah.csv", index=False)

    import matplotlib.pyplot as plt
    show = [c for c in ("temp_c", "soil_moist") if c in params]
    fig, axes = plt.subplots(len(show), 3, figsize=(10, 3 * len(show)), squeeze=False)
    smp = df.sample(min(len(df), 100_000), random_state=C.RANDOM_STATE).index
    for i, c in enumerate(show):
        for j, (lab, s) in enumerate((("asli", df.loc[smp, c]), ("Z-score", scaled.loc[smp, f"{c}_z"]),
                                      ("Min-Max", scaled.loc[smp, f"{c}_minmax"]))):
            axes[i, j].hist(s.dropna(), bins=50, color="#4f81bd")
            axes[i, j].set_title(f"{c} — {lab}", fontsize=9)
    fig.tight_layout()
    save_fig(fig, "scaling_sebelum_sesudah.png")
    qc.add("6_scaling", "kolom_diskalakan", list(params))
    qc.add("6_scaling", "catatan", "parameter dari train saja; LightGBM tidak memakai scaling, LogReg memakai StandardScaler")
    return {"params": params, "summary": summ}
