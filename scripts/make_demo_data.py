"""
make_demo_data.py — membuat DATA SINTETIS untuk UJI COBA pipeline (python scripts/run_pipeline.py --demo)

!!! PERINGATAN !!!
Data ini PALSU (hasil simulasi), hanya untuk memastikan kode berjalan di laptop Anda tanpa menunggu
data asli. JANGAN dimasukkan ke arsip pengumpulan dan JANGAN dipresentasikan sebagai hasil penelitian
(Panduan Bab I.3: manipulasi data = nilai 0). Output demo ditulis ke data/demo/ dan outputs di sana.

Data sengaja dibuat 'kotor' (duplikat, tanggal campur format, label tidak konsisten, kode -9999,
nilai mustahil, missing) supaya semua tahap cleaning punya sesuatu untuk dikerjakan.
Skema kolom meniru FIRMS (kolom standar NASA) dan ekspor GEE (tebakan nama kolom; sesuaikan di config.GEE_ALIASES).
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import config as C  # noqa: E402

# pojok kiri-bawah blok 10x10 sel per provinsi (lat, lon) — koordinat realistis kasar
CORNERS = {"Riau": (0.0, 100.5), "Jambi": (-2.0, 102.0), "Sumatera Selatan": (-3.5, 104.0),
           "Kalimantan Barat": (0.0, 110.0), "Kalimantan Tengah": (-2.0, 112.5), "Kalimantan Selatan": (-3.2, 115.0)}


def _slug(p: str) -> str:
    return p.lower().replace(" ", "_")


def generate(n_side: int = 10, seed: int = 42, force: bool = False) -> Path:
    root = C.ROOT / "data" / "demo" / "raw"
    if (root / "firms" / "firms_demo.csv").exists() and not force:
        return root
    rng = np.random.default_rng(seed)
    res = C.GRID_RES
    for sub in ("firms", "gee", "static", "boundary"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "LIHAT_INI_DATA_SINTETIS.txt").write_text(
        "Data di folder ini adalah SIMULASI untuk uji coba kode. Bukan data asli. Jangan dikumpulkan.", encoding="utf-8")

    # ---------------- grid
    rows = []
    for prov, (la0, lo0) in CORNERS.items():
        for iy in range(n_side):
            for ix in range(n_side):
                lat, lon = la0 + iy * res + res / 2, lo0 + ix * res + res / 2
                cid = f"c{int(round((lat - res / 2) / res))}_{int(round((lon - res / 2) / res))}"
                rows.append((cid, lat, lon, prov))
    grid = pd.DataFrame(rows, columns=["cell_id", "lat", "lon", "province"])
    grid.to_csv(root / "static" / "grid.csv", index=False)
    nc = len(grid)
    prov_idx = grid["province"].map({p: i for i, p in enumerate(CORNERS)}).to_numpy()

    # ---------------- simulasi harian
    dates = pd.date_range(C.DATE_START, C.DATE_END, freq="D")
    nd = len(dates)
    doy = np.arange(1, nd + 1)
    dry_season = np.clip((doy - 100) / 170, 0, 1) ** 1.1          # 0 = musim hujan, 1 = puncak kemarau (Agu-Sep)
    p_rain = np.clip(0.6 - 0.45 * dry_season, 0.08, 0.9)
    event = rng.random((nd, 6)) < (p_rain[:, None] + rng.normal(0, 0.05, 6)[None, :])
    cell_event = event[:, prov_idx] | (rng.random((nd, nc)) < 0.05)
    rain = np.where(cell_event & (rng.random((nd, nc)) > 0.25), rng.gamma(1.2, 8.0, (nd, nc)), 0.0)
    soil = np.zeros((nd, nc))
    s = np.full(nc, 0.38)
    for t in range(nd):
        s = np.clip(s * 0.985 + 0.0035 * rain[t], 0.08, 0.45)
        soil[t] = s
    temp_c = 26.5 + 1.5 * dry_season[:, None] + rng.normal(0, 0.8, (nd, nc)) + rng.normal(0, 0.3, nc)[None, :]
    spread = np.clip(2.5 + 9 * (0.45 - soil) / 0.37 + rng.normal(0, 0.7, (nd, nc)), 0.2, None)
    dew_c = temp_c - spread
    u, v = rng.normal(0.5, 2.0, (nd, nc)), rng.normal(0.3, 2.0, (nd, nc))

    # hotspot: dipicu kekeringan + 'kenangan' kebakaran sebelumnya + kerentanan sel
    fc = rng.normal(0, 1, nc)
    act = np.zeros(nc)
    hs = np.zeros((nd, nc), dtype=int)
    for t in range(nd):
        dryness = 1 - (soil[t] - 0.08) / 0.37
        lam = np.minimum(0.002 + 0.5 * dryness ** 3 * np.exp(0.9 * fc) * (1 + 1.5 * np.minimum(act, 3)), 3.0)
        hs[t] = rng.poisson(lam)
        act = act * 0.85 + hs[t]

    # ---------------- FIRMS (mentah, kotor)
    ti, ci = np.nonzero(hs)
    rep = hs[ti, ci]
    ti, ci = np.repeat(ti, rep), np.repeat(ci, rep)
    n = len(ti)
    inst = rng.choice(["MODIS", "VIIRS"], n, p=[0.5, 0.5])
    conf = np.where(inst == "MODIS", rng.integers(0, 101, n).astype(str), rng.choice(["l", "n", "h"], n, p=[.2, .6, .2]))
    hhmm = rng.choice([530, 540, 1030, 1315, 1730, 2200], n)
    f = pd.DataFrame({
        "latitude": grid["lat"].to_numpy()[ci] + rng.uniform(-res / 2, res / 2, n),
        "longitude": grid["lon"].to_numpy()[ci] + rng.uniform(-res / 2, res / 2, n),
        "brightness": rng.uniform(300, 400, n).round(1), "scan": 1.0, "track": 1.0,
        "acq_date": dates[ti].strftime("%Y-%m-%d"), "acq_time": hhmm,
        "satellite": np.where(inst == "MODIS", rng.choice(["Terra", "Aqua"], n), "N"),
        "instrument": inst, "confidence": conf, "version": "6.1NRT", "bright_t31": rng.uniform(280, 310, n).round(1),
        "frp": np.round(rng.lognormal(2.2, 0.9, n), 1), "daynight": np.where(hhmm < 1200, "N", "D"), "type": 0})
    # --- kotoran
    k = lambda p: rng.random(len(f)) < p
    f.loc[k(0.004), "acq_date"] = "05/03/2026"                                  # format tanggal beda
    f.loc[k(0.03), "satellite"] = f["satellite"].str.upper() + " "              # huruf besar + spasi
    m = f["instrument"].eq("VIIRS") & k(0.10)
    f.loc[m, "confidence"] = f.loc[m, "confidence"].map({"l": "Low", "n": "Nominal ", "h": "HIGH"})
    f.loc[k(0.003), "frp"] = -1.0                                                # FRP negatif (tak mungkin)
    f.loc[k(0.005), "frp"] = np.nan
    extra = f.sample(max(1, int(0.015 * len(f))), random_state=seed)            # duplikat (unduhan tumpang tindih)
    bad_coord = f.head(15).copy()
    bad_coord[["latitude", "longitude"]] = [0.0, 0.0]                            # di luar Indonesia
    old = f.head(10).copy()
    old["acq_date"] = "2025-12-30"                                               # di luar periode proyek
    f = pd.concat([f, extra, bad_coord, old], ignore_index=True).sample(frac=1, random_state=seed)
    f.to_csv(root / "firms" / "firms_demo.csv", index=False)

    # ---------------- GEE (CHIRPS + ERA5-Land) — per provinsi x jendela 14 hari
    cid = grid["cell_id"].to_numpy()
    long = pd.DataFrame({
        "cell_id": np.tile(cid, nd), "date": np.repeat(dates, nc), "lat": np.tile(grid["lat"], nd), "lon": np.tile(grid["lon"], nd),
        "precipitation": rain.ravel().round(2),
        "temperature_2m": (temp_c.ravel() + 273.15).round(2),
        "dewpoint_temperature_2m": (dew_c.ravel() + 273.15).round(2),
        "volumetric_soil_water_layer_1": soil.ravel().round(4),
        "u_component_of_wind_10m": u.ravel().round(2), "v_component_of_wind_10m": v.ravel().round(2),
        "prov": np.tile(prov_idx, nd)})
    L = len(long)
    r = lambda p: rng.random(L) < p
    era = ["temperature_2m", "dewpoint_temperature_2m", "volumetric_soil_water_layer_1",
           "u_component_of_wind_10m", "v_component_of_wind_10m"]
    long.loc[r(0.0125), era] = np.nan                                            # ERA5 kosong acak ~1,25%
    long.loc[long["cell_id"].isin(cid[[7, 207]]), era] = np.nan                  # 2 sel tak pernah punya ERA5
    long.loc[r(0.0005), "precipitation"] = -9999                                 # kode nodata CHIRPS
    long.loc[r(0.0002), "temperature_2m"] = 0.0                                  # suhu mustahil (0 Kelvin)
    long.loc[r(0.0001), "u_component_of_wind_10m"] = 999.0                       # angin mustahil
    prov_names = list(CORNERS)
    edges = pd.date_range(C.DATE_START, periods=21, freq="14D")
    for pi, pname in enumerate(prov_names):
        for a, b in zip(edges[:-1], edges[1:]):
            part = long[(long["prov"] == pi) & (long["date"] >= a) & (long["date"] < b)].drop(columns="prov").copy()
            if part.empty:
                continue
            part = pd.concat([part, part.sample(max(1, int(0.002 * len(part))), random_state=1)], ignore_index=True)  # duplikat persis
            part["date"] = part["date"].dt.strftime("%Y-%m-%d")
            part.loc[rng.random(len(part)) < 0.003, "date"] = pd.to_datetime(part["date"]).dt.strftime("%d/%m/%Y")
            part.to_csv(root / "gee" / f"gee26_{a:%Y%m%d}_{b:%Y%m%d}_{_slug(pname)}_c00000_demo.csv", index=False)
    return root


if __name__ == "__main__":
    print("Data demo dibuat di:", generate(force=True))
