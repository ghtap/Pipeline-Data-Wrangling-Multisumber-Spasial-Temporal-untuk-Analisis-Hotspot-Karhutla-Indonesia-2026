"""
TAHAP 8 — Exploratory Data Analysis & Analisis Korelasi  (Proposal 3.9)

Korelasi Pearson (hubungan linear) dan Spearman (berbasis peringkat; lebih cocok untuk data
miring/zero-inflated). Korelasi BUKAN sebab-akibat. Dihitung pada sampel acak berukuran tetap
agar cepat dan reproduktibel (random_state tetap).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from . import config as C
from .utils import QC, save_fig


def eda_plots(d: pd.DataFrame):
    import matplotlib.pyplot as plt
    s = d.sample(min(len(d), 200_000), random_state=C.RANDOM_STATE)

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    axes[0].hist(s["precip_mm"].clip(upper=s["precip_mm"].quantile(0.995)), bins=60, color="#4f81bd")
    axes[0].set_title("Curah hujan harian (dipotong P99,5 untuk tampilan)")
    axes[1].hist(s["temp_c"].dropna(), bins=60, color="#f79646")
    axes[1].set_title("Suhu udara 2 m (°C)")
    vc = d["hotspot_count"].clip(upper=10).value_counts().sort_index()
    axes[2].bar(vc.index.to_numpy(), vc.values, color="#c0504d")
    axes[2].set_yscale("log")
    axes[2].set_title("Hotspot per sel-hari (log; 10 = ≥10)")
    fig.tight_layout()
    save_fig(fig, "eda_distribusi.png")

    daily = d.groupby("date").agg(hotspot=("hotspot_count", "sum"), hujan=("precip_mm", "mean"))
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.bar(daily.index, daily["hotspot"], color="#c0504d", width=1.0, label="total hotspot/hari")
    ax.set_ylabel("hotspot")
    ax2 = ax.twinx()
    ax2.plot(daily.index, daily["hujan"].rolling(7, min_periods=1).mean(), color="#1f77b4", label="hujan rata-rata (MA7)")
    ax2.set_ylabel("mm/hari")
    ax.set_title("Tren harian hotspot vs curah hujan (seluruh wilayah)")
    fig.legend(loc="upper left", bbox_to_anchor=(0.08, 0.88))
    save_fig(fig, "eda_tren_harian.png")

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, col in zip(axes, ("temp_c", "soil_moist", "rh_pct")):
        groups = [g[col].dropna().to_numpy() for _, g in s.groupby("province")]
        ax.boxplot(groups, tick_labels=[p[:12] for p in sorted(s["province"].dropna().unique())], showfliers=False)
        ax.set_title(f"{col} per provinsi")
        ax.tick_params(axis="x", rotation=40)
    fig.tight_layout()
    save_fig(fig, "eda_boxplot_provinsi.png")


def correlation(d: pd.DataFrame, features: list[str], qc: QC) -> dict:
    import seaborn as sns
    import matplotlib.pyplot as plt
    cols = features + ["y_hotspot_next7"]
    base = d[~d["warmup"]]
    s = base.sample(min(len(base), C.EDA_SAMPLE_ROWS), random_state=C.RANDOM_STATE)[cols].astype("float64")
    out = {}
    for method in ("pearson", "spearman"):
        cm = s.corr(method=method)
        cm.round(4).to_csv(C.P.tables / f"matriks_korelasi_{method}.csv")
        n = len(cols)
        fig, ax = plt.subplots(figsize=(max(7, 0.55 * n + 3), max(6, 0.5 * n + 2.5)))
        sns.heatmap(cm, annot=True, fmt=".2f", annot_kws={"size": 6}, cmap="coolwarm", vmin=-1, vmax=1,
                    square=True, cbar_kws={"shrink": 0.7}, ax=ax)
        ax.set_title(f"Heatmap korelasi {method.capitalize()} (sampel {len(s):,} baris)")
        save_fig(fig, f"heatmap_korelasi_{method}.png")
        out[method] = cm
    cm = out["spearman"]
    pairs = (cm.where(np.triu(np.ones(cm.shape, dtype=bool), 1)).stack().rename("rho").reset_index()
               .rename(columns={"level_0": "fitur_a", "level_1": "fitur_b"}))
    pairs["abs_rho"] = pairs["rho"].abs()
    pairs = pairs[~pairs[["fitur_a", "fitur_b"]].isin(["y_hotspot_next7"]).any(axis=1)].sort_values("abs_rho", ascending=False)
    pairs.head(20).to_csv(C.P.tables / "pasangan_fitur_terkorelasi_tertinggi.csv", index=False)
    tgt = cm["y_hotspot_next7"].drop("y_hotspot_next7").sort_values(key=abs, ascending=False)
    tgt.to_csv(C.P.tables / "korelasi_fitur_dengan_target.csv", header=["spearman_rho"])
    qc.add("8_eda", "korelasi_target_top5", tgt.head(5).round(3).to_dict())
    qc.add("8_eda", "pasangan_terkorelasi_top3", pairs.head(3).round(3).to_dict("records"))
    return {"pearson": out["pearson"], "spearman": cm, "pairs": pairs, "target_corr": tgt}


def run(d: pd.DataFrame, features: list[str], qc: QC) -> dict:
    eda_plots(d)
    return correlation(d, features, qc)
