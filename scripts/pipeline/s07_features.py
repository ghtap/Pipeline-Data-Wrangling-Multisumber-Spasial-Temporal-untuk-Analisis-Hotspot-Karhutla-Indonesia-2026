"""
TAHAP 7 — Feature Engineering, Reshaping & Feature Selection  (Proposal 3.8 + Panduan Bab II-4a)

Fitur historis (rolling 7/14 hari) dihitung dari data SEBELUM tanggal t  (shift(1) dulu, baru rolling)
sehingga tidak ada kebocoran data (data leakage). Target = ada hotspot dalam t+1 .. t+7.

Implementasi memakai matriks (tanggal x sel) + rolling vektor supaya cepat untuk jutaan baris.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from . import config as C
from .utils import QC, log, save_fig, save_json, temporal_split

# (kolom_sumber, jendela, agregasi) -> nama fitur sesuai tabel Proposal 3.8
LAG_SPEC = {
    "rain_prev7_mm": ("precip_mm", 7, "sum"),
    "rain_prev14_mm": ("precip_mm", 14, "sum"),
    "rain_prev30_mm": ("precip_mm", 30, "sum"),
    "hotspot_prev7": ("hotspot_count", 7, "sum"),
    "hotspot_prev14": ("hotspot_count", 14, "sum"),
    "frp_prev7": ("frp_sum", 7, "sum"),
    "temp_prev7_mean": ("temp_c", 7, "mean"),
    "rh_prev7_mean": ("rh_pct", 7, "mean"),
    "soil_prev7_mean": ("soil_moist", 7, "mean"),
    "wind_prev7_mean": ("wind_ms", 7, "mean"),
}
SAME_DAY = ["precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist", "hotspot_count", "dry_days_streak"]
STATIC = ["lat", "lon", "province_code"]


def _grid_index(df: pd.DataFrame):
    dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    cells = pd.Index(df["cell_id"].unique())
    di = dates.get_indexer(pd.DatetimeIndex(df["date"]))
    ci = cells.get_indexer(df["cell_id"])
    return dates, cells, di, ci


def _matrix(values: np.ndarray, di, ci, n_days, n_cells) -> np.ndarray:
    M = np.full((n_days, n_cells), np.nan, dtype="float32")
    M[di, ci] = values.astype("float32")
    return M


def build_features(df: pd.DataFrame, qc: QC) -> pd.DataFrame:
    d = df.sort_values(["cell_id", "date"]).reset_index(drop=True)
    dates, cells, di, ci = _grid_index(d)
    nd, nc = len(dates), len(cells)
    mats = {}
    for src in {v[0] for v in LAG_SPEC.values()} | {"hotspot_count"}:
        mats[src] = _matrix(d[src].to_numpy(), di, ci, nd, nc)

    for name, (src, w, how) in LAG_SPEC.items():
        r = pd.DataFrame(mats[src]).shift(1).rolling(w, min_periods=w)   # shift(1) = HANYA hari sebelum t
        r = r.sum() if how == "sum" else r.mean()
        d[name] = r.to_numpy()[di, ci].astype("float32")

    # hari kering berturut-turut sampai hari t (memakai data <= t, boleh karena t sudah diketahui)
    P, streak = mats["precip_mm"], np.zeros(nc, dtype="float32")
    S = np.full((nd, nc), np.nan, dtype="float32")
    for t in range(nd):
        streak = np.where(np.isnan(P[t]), np.nan, np.where(P[t] >= C.DRY_DAY_MM, 0, streak + 1)).astype("float32")
        S[t] = streak
    d["dry_days_streak"] = S[di, ci]

    # target: jumlah hotspot pada t+1..t+H  (rolling H hari lalu digeser mundur H hari)
    H = C.HORIZON
    tgt_col = "n_nominal_high" if C.LABEL_NOMINAL_HIGH_ONLY and "n_nominal_high" in d.columns else "hotspot_count"
    mats["target_src"] = _matrix(d[tgt_col].to_numpy(), di, ci, nd, nc)
    fut = pd.DataFrame(mats["target_src"]).rolling(H, min_periods=H).sum().shift(-H).to_numpy()[di, ci]
    y = np.where(np.isnan(fut), np.nan, (fut > 0).astype("float32"))
    d["y_hotspot_next7"] = pd.array(y, dtype="Int8")

    d["month_2026"] = d["date"].dt.month.astype("int8")
    codes = {p: i for i, p in enumerate(C.PROVINCES)}
    d["province_code"] = d["province"].map(codes).fillna(-1).astype("int8")
    d["warmup"] = d["date"] < (pd.Timestamp(C.DATE_START) + pd.Timedelta(days=C.WARMUP_DAYS))

    m = temporal_split(d)           # kolom split (aturan waktu): train / val / test / excluded
    d["split"] = np.select([m["train"], m["val"], m["test"]], ["train", "val", "test"], default="excluded")
    qc.add("7_features", "jumlah_baris_per_split", d["split"].value_counts().to_dict())
    qc.add("7_features", "label_nominal_high_saja", C.LABEL_NOMINAL_HIGH_ONLY)
    qc.add("7_features", "fitur_historis", list(LAG_SPEC))
    qc.add("7_features", "baris_warmup_tanpa_fitur_lengkap", int(d["warmup"].sum()))
    qc.add("7_features", "baris_tanpa_target_(7_hari_terakhir)", int(d["y_hotspot_next7"].isna().sum()))
    pos = d.loc[~d["warmup"] & d["y_hotspot_next7"].notna(), "y_hotspot_next7"].astype(float)
    qc.add("7_features", "proporsi_kelas_positif", round(float(pos.mean()), 4) if len(pos) else None)
    return d


# ------------------------------------------------------------------ reshaping (pivot / unpivot / groupby)
def reshape_examples(d: pd.DataFrame, qc: QC) -> dict:
    x = d.copy()
    x["bulan"] = x["date"].dt.month
    # 1) PIVOT: provinsi x bulan
    piv_hs = x.pivot_table(index="province", columns="bulan", values="hotspot_count", aggfunc="sum", fill_value=0)
    piv_rain = x.pivot_table(index="province", columns="bulan", values="precip_mm", aggfunc="mean")
    piv_hs.to_csv(C.P.tables / "pivot_hotspot_provinsi_bulan.csv")
    piv_rain.round(3).to_csv(C.P.tables / "pivot_curah_hujan_provinsi_bulan.csv")
    # 2) UNPIVOT (melt): variabel cuaca wide -> long, untuk boxplot per variabel
    wide = x.sample(min(len(x), 50_000), random_state=C.RANDOM_STATE)[["cell_id", "date", "province",
                                                                         "temp_c", "rh_pct", "wind_ms", "soil_moist"]]
    long = wide.melt(id_vars=["cell_id", "date", "province"], var_name="variabel", value_name="nilai")
    long.head(1000).to_csv(C.P.tables / "contoh_unpivot_long.csv", index=False)
    # 3) GROUPING: agregasi mingguan per provinsi
    x["minggu"] = x["date"].dt.to_period("W").dt.start_time
    weekly = (x.groupby(["province", "minggu"])
                .agg(hotspot=("hotspot_count", "sum"), hujan_rata2=("precip_mm", "mean"),
                     suhu_rata2=("temp_c", "mean")).reset_index())
    weekly.to_csv(C.P.tables / "agregasi_mingguan_provinsi.csv", index=False)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.8))
    im = ax.imshow(np.log1p(piv_hs.to_numpy()), aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(piv_hs.shape[1]), piv_hs.columns)
    ax.set_yticks(range(piv_hs.shape[0]), piv_hs.index)
    for i in range(piv_hs.shape[0]):
        for j in range(piv_hs.shape[1]):
            ax.text(j, i, int(piv_hs.iloc[i, j]), ha="center", va="center", fontsize=7)
    ax.set_title("Jumlah deteksi hotspot per provinsi x bulan (hasil pivot; warna = log)")
    ax.set_xlabel("bulan 2026")
    fig.colorbar(im, ax=ax, label="log(1+jumlah)")
    save_fig(fig, "pivot_hotspot_provinsi_bulan.png")
    qc.add("7_features", "reshaping", ["pivot_table provinsi x bulan", "melt (unpivot) variabel cuaca", "groupby mingguan"])
    return {"pivot_hotspot": piv_hs, "pivot_rain": piv_rain, "unpivot_long": long, "weekly": weekly}


# ------------------------------------------------------------------ feature selection
def select_features(d: pd.DataFrame, qc: QC) -> tuple[list[str], pd.DataFrame]:
    cand = [c for c in (SAME_DAY + list(LAG_SPEC) + STATIC + ["month_2026"]) if c in d.columns]
    train = d[temporal_split(d)["train"]]
    smp = train.sample(min(len(train), 300_000), random_state=C.RANDOM_STATE)
    X, y = smp[cand].astype("float64"), smp["y_hotspot_next7"].astype(float)

    status = {c: ("dipertahankan", "") for c in cand}
    # 1) buang fitur konstan
    for c in cand:
        if X[c].nunique(dropna=True) <= 1:
            status[c] = ("dibuang", "konstan (varians 0)")
    keep = [c for c in cand if status[c][0] == "dipertahankan"]
    # 2) buang salah satu dari pasangan sangat berkorelasi (|Spearman| > ambang), simpan yang lebih berkorelasi dg target
    corr = X[keep].corr(method="spearman").abs()
    tcorr = X[keep].corrwith(y, method="spearman").abs()
    pairs = [(a, b, corr.loc[a, b]) for i, a in enumerate(keep) for b in keep[i + 1:] if corr.loc[a, b] > C.CORR_DROP_THRESHOLD]
    for a, b, r in sorted(pairs, key=lambda t: -t[2]):
        if status[a][0] == "dibuang" or status[b][0] == "dibuang":
            continue
        drop = a if tcorr[a] < tcorr[b] else b
        other = b if drop == a else a
        status[drop] = ("dibuang", f"redundan dg {other} (|rho|={r:.2f})")
    keep = [c for c in cand if status[c][0] == "dipertahankan"]
    # 3) peringkat Mutual Information (informatif, tidak memotong fitur)
    from sklearn.feature_selection import mutual_info_classif
    mi_s = smp.sample(min(len(smp), 30_000), random_state=C.RANDOM_STATE)
    Xm = mi_s[keep].astype("float64")
    Xm = Xm.fillna(Xm.median())
    mi = pd.Series(mutual_info_classif(Xm, mi_s["y_hotspot_next7"].astype(int), random_state=C.RANDOM_STATE), index=keep)

    tab = pd.DataFrame({"fitur": cand,
                        "status": [status[c][0] for c in cand],
                        "alasan": [status[c][1] for c in cand],
                        "korelasi_spearman_dg_target": [round(float(X[c].corr(y, method="spearman")), 4) for c in cand],
                        "mutual_information": [round(float(mi.get(c, np.nan)), 5) if c in mi.index else np.nan for c in cand]})
    tab = tab.sort_values(["status", "mutual_information"], ascending=[True, False]).reset_index(drop=True)
    tab.to_csv(C.P.tables / "seleksi_fitur.csv", index=False)
    save_json({"selected_features": keep, "candidates": cand}, C.P.qc / "selected_features.json")
    qc.add("7_features", "fitur_kandidat", len(cand))
    qc.add("7_features", "fitur_terpilih", keep)
    qc.add("7_features", "fitur_dibuang", {c: status[c][1] for c in cand if status[c][0] == "dibuang"})
    return keep, tab


def run(df: pd.DataFrame, qc: QC) -> dict:
    d = build_features(df, qc)
    reshape = reshape_examples(d, qc)
    selected, tab = select_features(d, qc)
    d.to_parquet(C.P.interim / "07_features.parquet", index=False)
    return {"df": d, "selected": selected, "selection_table": tab, "reshape": reshape}
