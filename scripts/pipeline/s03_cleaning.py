"""
TAHAP 3 — Standardisasi & Data Cleaning  (Proposal 3.4)

a. Standardisasi tipe data & tanggal (YYYY-MM-DD)
b. Standardisasi nama kolom & satuan (Kelvin -> Celsius, u/v angin -> kecepatan angin, titik embun -> RH)
c. Penanganan duplikasi (tanpa membuang deteksi hotspot yang memang berbeda)
d. Missing values: nilai tak valid -> NaN (bukan 0), lalu BANDINGKAN beberapa strategi imputasi
   dengan cara menyembunyikan sebagian nilai asli dan melihat strategi mana yang paling akurat.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from . import config as C
from .utils import QC, log, resolve_columns, parse_dates_flex, save_fig

MET_COLS = ["precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist"]
CONF_TEXT = {"l": "low", "low": "low", "n": "nominal", "nominal": "nominal", "h": "high", "high": "high"}


# =========================================================== helper
def _std_confidence(s: pd.Series) -> pd.Series:
    """Samakan label confidence: teks (l/n/h, High, ...) dan angka 0-100 (MODIS) -> low/nominal/high."""
    txt = s.astype("string").str.strip().str.lower()
    mapped = txt.map(CONF_TEXT)
    num = pd.to_numeric(txt, errors="coerce")
    bucket = pd.cut(num, bins=[-0.1, 29.999, 79.999, 100.0], labels=["low", "nominal", "high"]).astype("string")
    return mapped.astype("string").where(mapped.notna(), bucket)


def _domain_to_nan(df: pd.DataFrame, col: str, rule: str, counts: dict):
    lo, hi = C.DOMAIN_RULES[rule]
    bad = df[col].notna() & ~df[col].between(lo, hi)
    counts[col] = int(bad.sum())
    df.loc[bad, col] = np.nan


# =========================================================== FIRMS
def clean_firms(firms: pd.DataFrame, qc: QC) -> pd.DataFrame:
    d = resolve_columns(firms, C.FIRMS_ALIASES, required=("lat", "lon", "acq_date"), name="FIRMS")
    log_ = {"baris_awal": len(d)}

    # --- string cleaning: spasi, huruf besar/kecil, label konsisten
    for c in ("satellite", "instrument", "daynight"):
        if c in d.columns:
            d[c] = d[c].astype("string").str.strip().str.lower()
    if "daynight" in d.columns:
        d["daynight"] = d["daynight"].replace({"d": "day", "n": "night"})
    if "confidence" in d.columns:
        log_["confidence_label_sebelum"] = int(d["confidence"].astype(str).str.strip().nunique())
        d["confidence"] = _std_confidence(d["confidence"])
        log_["confidence_label_sesudah"] = int(d["confidence"].nunique())

    # --- tanggal -> YYYY-MM-DD
    d["acq_date"], n_fixed, n_fail = parse_dates_flex(d["acq_date"])
    log_["tanggal_format_diperbaiki"], log_["tanggal_gagal_parse"] = n_fixed, n_fail
    d = d[d["acq_date"].notna()]

    # --- jam akuisisi 'HHMM' (nol di depan sering hilang)
    if "acq_time" in d.columns:
        t = pd.to_numeric(d["acq_time"], errors="coerce").astype("Int64").astype("string")
        d["acq_time"] = t.str.zfill(4)

    # --- koordinat harus numerik dan berada di wilayah Indonesia
    d["lat"], d["lon"] = pd.to_numeric(d["lat"], errors="coerce"), pd.to_numeric(d["lon"], errors="coerce")
    bb = C.INDONESIA_BBOX
    ok = d["lat"].between(*bb["lat"]) & d["lon"].between(*bb["lon"])
    log_["koordinat_tidak_valid_dibuang"] = int((~ok).sum())
    d = d[ok]

    # --- FRP: negatif tidak masuk akal -> NaN (bukan 0)
    if "frp" in d.columns:
        d["frp"] = pd.to_numeric(d["frp"], errors="coerce")
        bad = d["frp"].notna() & ~d["frp"].between(*C.DOMAIN_RULES["frp"])
        log_["frp_di_luar_domain_jadi_nan"] = int(bad.sum())
        d.loc[bad, "frp"] = np.nan

    # --- batasi periode proyek
    inrange = d["acq_date"].between(pd.Timestamp(C.DATE_START), pd.Timestamp(C.DATE_END))
    log_["di_luar_periode_dibuang"] = int((~inrange).sum())
    d = d[inrange]

    # --- duplikat: kunci = lokasi+tanggal+jam+satelit+instrumen. Deteksi berbeda (jam/satelit lain) DIPERTAHANKAN.
    keys = [c for c in ("lat", "lon", "acq_date", "acq_time", "satellite", "instrument") if c in d.columns]
    dup = d.duplicated(keys)
    log_["duplikat_dibuang"] = int(dup.sum())
    d = d[~dup]

    keep = [c for c in ("lat", "lon", "acq_date", "acq_time", "frp", "confidence", "satellite", "instrument",
                        "daynight", "brightness") if c in d.columns]
    d = d[keep].reset_index(drop=True)
    log_["baris_akhir"] = len(d)
    qc.add("3_cleaning_firms", "ringkasan", log_)
    return d


# =========================================================== CHIRPS + ERA5-Land
def _prep_table(df: pd.DataFrame, value_cols: list[str], name: str, log_: dict) -> pd.DataFrame:
    d = df.drop(columns=["source_file"], errors="ignore").copy()
    d = d[d["cell_id"].notna()]
    d["cell_id"] = d["cell_id"].astype(str)
    d["date"], n_fixed, n_fail = parse_dates_flex(d["date"])
    log_[f"{name}_tanggal_format_diperbaiki"], log_[f"{name}_tanggal_gagal_parse"] = n_fixed, n_fail
    d = d[d["date"].notna()]
    for c in value_cols:
        d[c] = pd.to_numeric(d[c], errors="coerce")
        sent = d[c].isin(C.NODATA_SENTINELS)           # -9999 dst. = kode "tidak ada data", BUKAN nilai fisik
        log_[f"{name}_{c}_sentinel_jadi_nan"] = int(sent.sum())
        d.loc[sent, c] = np.nan
    log_[f"{name}_duplikat_persis_dibuang"] = int(d.duplicated().sum())
    d = d.drop_duplicates()
    n_key = int(d.duplicated(["cell_id", "date"]).sum())
    log_[f"{name}_duplikat_cell_date_digabung_rata2"] = n_key
    if n_key:
        d = d.groupby(["cell_id", "date"], as_index=False)[value_cols].mean()
    return d


def clean_meteo(chirps: pd.DataFrame, era5: pd.DataFrame, grid: pd.DataFrame, qc: QC) -> pd.DataFrame:
    L: dict = {}
    c = _prep_table(chirps, ["precip_mm"], "chirps", L)
    era_cols = [x for x in C.ERA5_COLS if x in era5.columns]
    e = _prep_table(era5, era_cols, "era5", L)

    # --- satuan: Kelvin -> Celsius (dideteksi dari nilai tengah), komponen angin -> kecepatan angin
    dom: dict = {}
    if "t2m_k" in e.columns:
        e["temp_c"] = e["t2m_k"] - 273.15 if np.nanmedian(e["t2m_k"]) > 100 else e["t2m_k"]
        _domain_to_nan(e, "temp_c", "temp_c", dom)
    if "d2m_k" in e.columns:
        e["dewpoint_c"] = e["d2m_k"] - 273.15 if np.nanmedian(e["d2m_k"]) > 100 else e["d2m_k"]
        _domain_to_nan(e, "dewpoint_c", "dewpoint_c", dom)
    if {"temp_c", "dewpoint_c"} <= set(e.columns):
        # RH dari suhu & titik embun (rumus Magnus)
        a, b = 17.625, 243.04
        rh = 100 * np.exp(a * e["dewpoint_c"] / (b + e["dewpoint_c"])) / np.exp(a * e["temp_c"] / (b + e["temp_c"]))
        L["rh_di_atas_100_dipotong"] = int((rh > 100).sum())
        e["rh_pct"] = rh.clip(0, 100)
    if {"u10", "v10"} <= set(e.columns):
        e["wind_ms"] = np.hypot(e["u10"], e["v10"])
        _domain_to_nan(e, "wind_ms", "wind_ms", dom)
    if "soil_moist" in e.columns:
        _domain_to_nan(e, "soil_moist", "soil_moist", dom)
    _domain_to_nan(c, "precip_mm", "precip_mm", dom)
    L["nilai_di_luar_domain_jadi_nan"] = dom
    e = e[["cell_id", "date"] + [x for x in ("temp_c", "rh_pct", "wind_ms", "soil_moist") if x in e.columns]]

    # --- gabungkan CHIRPS & ERA5: outer join supaya baris yang hanya ada di satu sumber ketahuan
    m = c.merge(e, on=["cell_id", "date"], how="outer", validate="one_to_one", indicator=True)
    L["join_chirps_era5"] = m["_merge"].astype(str).value_counts().to_dict()
    m = m.drop(columns="_merge")

    # --- tempelkan atribut sel (lat, lon, provinsi)
    n0 = len(m)
    m = m.merge(grid, on="cell_id", how="left", validate="many_to_one", indicator=True)
    unmatched = int((m["_merge"] == "left_only").sum())
    L["baris_cell_id_tidak_ada_di_grid_dibuang"] = unmatched
    if unmatched > 0.5 * n0:
        raise ValueError("Lebih dari 50% cell_id data GEE tidak ada di grid -> grid dan data GEE tidak cocok. "
                         "Pakai grid.csv dari proyek yang sama (data/raw_sample/static/).")
    m = m[m["_merge"] == "both"].drop(columns="_merge")

    for col in MET_COLS:
        if col in m.columns:
            m[col] = m[col].astype("float32")
    m = m.sort_values(["cell_id", "date"]).reset_index(drop=True)
    L["baris_akhir"] = len(m)
    qc.add("3_cleaning_meteo", "ringkasan", L)
    return m


# =========================================================== MISSING VALUES
def missing_report(meteo: pd.DataFrame, qc: QC) -> pd.DataFrame:
    cols = [c for c in MET_COLS if c in meteo.columns]
    rows = []
    for c in cols:
        per_cell = meteo.groupby("cell_id")[c].apply(lambda s: s.notna().sum())
        rows.append({"variabel": c, "n_missing": int(meteo[c].isna().sum()),
                     "pct_missing": round(100 * meteo[c].isna().mean(), 3),
                     "sel_yang_seluruhnya_kosong": int((per_cell == 0).sum())})
    rep = pd.DataFrame(rows)
    rep.to_csv(C.P.tables / "missing_values_sebelum_imputasi.csv", index=False)
    qc.add("3_missing", "baris_dengan_missing_apa_pun", int(meteo[cols].isna().any(axis=1).sum()))
    qc.add("3_missing", "laporan", rep.to_dict("records"))
    return rep


def _impute(d: pd.DataFrame, cols: list[str], strategy: str, train_mask: pd.Series) -> pd.DataFrame:
    """d harus terurut (cell_id, date) dan index 0..n-1. Parameter statistik HANYA dari periode train."""
    out = d[cols].copy()
    gmean = d.loc[train_mask, cols].mean()

    def prov_date():
        return d.groupby([d["province"], d["date"]], dropna=False)[cols].transform("mean")

    if strategy == "global_mean":
        out = out.fillna(gmean)
    elif strategy == "cell_median":
        med = d.loc[train_mask].groupby("cell_id")[cols].median().reindex(d["cell_id"])
        med.index = d.index
        out = out.fillna(med).fillna(gmean)
    elif strategy == "ffill_cell":
        out = out.groupby(d["cell_id"]).ffill(limit=C.FFILL_LIMIT).fillna(gmean)
    elif strategy == "province_date_mean":
        out = out.fillna(prov_date()).fillna(gmean)
    elif strategy == "ffill_then_province_date":
        out = out.groupby(d["cell_id"]).ffill(limit=C.FFILL_LIMIT)
        out = out.fillna(prov_date()).fillna(gmean)
    elif strategy == "interp_cell":      # NON-kausal: memakai nilai hari berikutnya -> hanya pembanding
        out = out.groupby(d["cell_id"]).transform(
            lambda s: s.interpolate(limit=C.FFILL_LIMIT, limit_direction="both")).fillna(gmean)
    else:
        raise ValueError(strategy)
    return out


STRATEGIES = C.CAUSAL_STRATEGIES + ["interp_cell"]


def compare_imputation(meteo: pd.DataFrame, qc: QC) -> tuple[pd.DataFrame, str]:
    """Uji strategi imputasi: sembunyikan IMPUTE_MASK_FRAC nilai ASLI di periode validasi/uji,
    isi dengan tiap strategi, lalu ukur kesalahan (NRMSE = RMSE / simpangan baku nilai asli)."""
    cols = [c for c in MET_COLS if c in meteo.columns]
    rng = np.random.default_rng(C.RANDOM_STATE)
    cells = meteo["cell_id"].unique()
    pick = rng.choice(cells, size=min(C.IMPUTE_EVAL_CELLS, len(cells)), replace=False)
    d = meteo[meteo["cell_id"].isin(pick)].sort_values(["cell_id", "date"]).reset_index(drop=True)
    train_mask = d["date"] < pd.Timestamp(C.VAL_START)
    heldout = ~train_mask

    masked = d.copy()
    pos = {}
    for c in cols:
        m = heldout & d[c].notna() & (rng.random(len(d)) < C.IMPUTE_MASK_FRAC)
        pos[c] = m
        masked.loc[m, c] = np.nan

    rows = []
    for strat in STRATEGIES:
        imp = _impute(masked, cols, strat, train_mask)
        r = {"strategi": strat, "kausal": strat in C.CAUSAL_STRATEGIES}
        nr = []
        for c in cols:
            truth, pred = d.loc[pos[c], c], imp.loc[pos[c], c]
            rmse = float(np.sqrt(((truth - pred) ** 2).mean()))
            r[f"rmse_{c}"] = round(rmse, 4)
            nr.append(rmse / float(truth.std()) if truth.std() > 0 else np.nan)
        r["nrmse_rata2"] = round(float(np.nanmean(nr)), 4)
        rows.append(r)
    tab = pd.DataFrame(rows).sort_values("nrmse_rata2").reset_index(drop=True)
    tab.to_csv(C.P.tables / "perbandingan_strategi_imputasi.csv", index=False)
    best = tab[tab["kausal"]].iloc[0]["strategi"]
    qc.add("3_missing", "strategi_imputasi_terpilih", best)
    qc.add("3_missing", "tabel_perbandingan", tab.to_dict("records"))

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 3.5))
    colors = ["#4f81bd" if k else "#bfbfbf" for k in tab["kausal"]]
    ax.barh(tab["strategi"][::-1], tab["nrmse_rata2"][::-1], color=colors[::-1])
    ax.set_xlabel("NRMSE rata-rata (lebih kecil = lebih baik)")
    ax.set_title("Perbandingan strategi imputasi (abu-abu = non-kausal, hanya pembanding)")
    save_fig(fig, "imputasi_perbandingan.png")
    return tab, best


def apply_imputation(meteo: pd.DataFrame, strategy: str, qc: QC) -> pd.DataFrame:
    cols = [c for c in MET_COLS if c in meteo.columns]
    d = meteo.sort_values(["cell_id", "date"]).reset_index(drop=True)
    train_mask = d["date"] < pd.Timestamp(C.VAL_START)
    was_na = d[cols].isna()
    imp = _impute(d, cols, strategy, train_mask)
    out = d.copy()
    out[cols] = imp.astype("float32")
    out["n_imputed"] = (was_na & imp.notna()).sum(axis=1).astype("int8")   # penanda: berapa variabel diisi pada baris ini
    qc.add("3_missing", "nilai_diimputasi_total", int(out["n_imputed"].sum()))
    qc.add("3_missing", "baris_yang_punya_imputasi", int((out["n_imputed"] > 0).sum()))
    qc.add("3_missing", "missing_tersisa", int(out[cols].isna().sum().sum()))
    return out


# =========================================================== orkestrasi
def run(raw: dict, qc: QC) -> dict:
    firms = clean_firms(raw["firms"], qc)
    meteo = clean_meteo(raw["chirps"], raw["era5"], raw["grid"], qc)
    rep = missing_report(meteo, qc)
    tab, best = compare_imputation(meteo, qc)
    meteo_imp = apply_imputation(meteo, best, qc)
    firms.to_parquet(C.P.interim / "03_firms_clean.parquet", index=False)
    meteo_imp.to_parquet(C.P.interim / "03_meteo_clean.parquet", index=False)
    return {"firms": firms, "meteo": meteo_imp, "meteo_before_impute": meteo,
            "missing_report": rep, "imputation_table": tab, "imputation_best": best}
