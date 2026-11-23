"""
TAHAP 1 — Data Acquisition & Ingestion  (Proposal 3.2)

Membaca data MENTAH dari beberapa sumber tanpa mengubah isinya:
  - NASA FIRMS  : CSV titik panas (data/raw_sample/firms/*.csv)
  - CHIRPS+ERA5 : CSV hasil ekspor Google Earth Engine (data/raw_sample/gee/*.csv)
  - geoBoundaries: batas provinsi (.zip/.geojson) -> membentuk grid (data/raw_sample/boundary)
  - grid.csv (opsional): grid siap pakai dari proyek DIMAS-TI (data/raw_sample/static)
Mencatat provenance (asal data + SHA-256) agar file mentah bisa dibuktikan tidak berubah.
"""
from __future__ import annotations
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from . import config as C
from .utils import QC, log, resolve_columns, sha256_file, save_json


# ----------------------------------------------------------------- provenance
def _list(dirpath: Path, patterns=("*.csv",)) -> list[Path]:
    files = []
    for p in patterns:
        files += sorted(dirpath.rglob(p))
    return files


def file_provenance(files: list[Path], source: str) -> list[dict]:
    rows = []
    for f in files:
        rows.append({"source": source, "file": str(f.relative_to(C.P.raw)) if C.P.raw in f.parents else str(f),
                     "size_bytes": f.stat().st_size, "sha256": sha256_file(f), "abs_path": str(f)})
    return rows


# ----------------------------------------------------------------- FIRMS
def read_firms() -> pd.DataFrame:
    files = _list(C.P.firms_dir)
    if not files:
        raise FileNotFoundError(
            f"Tidak ada CSV FIRMS di {C.P.firms_dir}.\n"
            "-> Salin firms_raw.csv ke folder itu (lihat README / scripts/copy_raw_from_dimasti.py),\n"
            "   atau jalankan dengan --demo untuk uji coba memakai data sintetis.")
    parts = []
    for f in files:
        d = pd.read_csv(f, low_memory=False)
        d["source_file"] = f.name
        parts.append(d)
        log.info("FIRMS dibaca: %s (%d baris, %d kolom)", f.name, *d.shape)
    return pd.concat(parts, ignore_index=True)


# ----------------------------------------------------------------- GRID
def _read_boundary() -> "gpd.GeoDataFrame":
    try:
        import geopandas as gpd
    except ImportError as e:
        raise ImportError("geopandas belum terpasang: pip install geopandas shapely") from e
    cands = _list(C.P.boundary_dir, ("*.zip", "*.geojson", "*.shp"))
    if not cands:
        raise FileNotFoundError(f"Tidak ada file batas wilayah di {C.P.boundary_dir}")
    f = cands[0]
    if f.suffix == ".zip":
        with zipfile.ZipFile(f) as z:
            gj = [n for n in z.namelist() if n.lower().endswith(".geojson")
                  and "adm1" in n.lower() and "simplified" not in n.lower()]
            if gj:
                gdf = gpd.read_file(io.BytesIO(z.read(gj[0])))
            else:
                shp = [n for n in z.namelist() if n.lower().endswith(".shp") and "adm1" in n.lower()]
                gdf = gpd.read_file(f"zip://{f}!{shp[0]}")
    else:
        gdf = gpd.read_file(f)
    name_col = next((c for c in ("shapeName", "NAME_1", "province", "provinsi", "name") if c in gdf.columns), None)
    if name_col is None:
        raise ValueError(f"Kolom nama provinsi tidak ditemukan. Kolom: {list(gdf.columns)}")
    gdf["province"] = gdf[name_col].astype(str).str.strip().str.lower().map(C.PROVINCE_SYNONYMS)
    gdf = gdf[gdf["province"].isin(C.PROVINCES)][["province", "geometry"]]
    if gdf.empty:
        raise ValueError("Tidak ada provinsi target yang cocok di file batas wilayah.")
    return gdf


def build_grid_from_boundary() -> pd.DataFrame:
    """Bentuk sel grid 0,045° yang pusatnya jatuh di dalam 6 provinsi."""
    import geopandas as gpd
    prov = _read_boundary()
    res = C.GRID_RES
    minx, miny, maxx, maxy = prov.total_bounds
    xs = np.arange(np.floor(minx / res) * res + res / 2, maxx + res, res)
    ys = np.arange(np.floor(miny / res) * res + res / 2, maxy + res, res)
    gx, gy = np.meshgrid(xs, ys)
    pts = gpd.GeoDataFrame({"lon": gx.ravel(), "lat": gy.ravel()},
                           geometry=gpd.points_from_xy(gx.ravel(), gy.ravel()), crs=prov.crs or "EPSG:4326")
    j = gpd.sjoin(pts, prov, predicate="within", how="inner").drop_duplicates(["lat", "lon"])
    iy = np.round((j["lat"] - res / 2) / res).astype(int)
    ix = np.round((j["lon"] - res / 2) / res).astype(int)
    grid = pd.DataFrame({"cell_id": "c" + iy.astype(str) + "_" + ix.astype(str),
                         "lat": j["lat"].values, "lon": j["lon"].values, "province": j["province"].values})
    return grid.reset_index(drop=True)


def load_grid() -> pd.DataFrame:
    """Prioritas: grid.csv dari DIMAS-TI (supaya cell_id sama) -> kalau tidak ada, bangun dari batas wilayah."""
    cands = [p for p in _list(C.P.static_dir) if "grid" in p.name.lower()]
    if cands:
        g = resolve_columns(pd.read_csv(cands[0]), C.GRID_ALIASES, required=("cell_id", "lat", "lon"), name="grid")
        if "province" not in g.columns:
            g["province"] = pd.NA
        log.info("grid dibaca dari %s", cands[0].name)
    else:
        log.info("grid.csv tidak ada -> membangun grid dari batas wilayah (geoBoundaries)")
        g = build_grid_from_boundary()
    g = g[["cell_id", "lat", "lon", "province"]].copy()
    g["cell_id"] = g["cell_id"].astype(str)
    assert g["cell_id"].is_unique, "cell_id pada grid harus unik"
    return g.reset_index(drop=True)


def assign_to_grid(df: pd.DataFrame, grid: pd.DataFrame, lat="lat", lon="lon") -> pd.DataFrame:
    """Petakan koordinat titik ke sel grid terdekat (KD-Tree). Titik yang jauh dari semua sel -> cell_id NaN."""
    tree = cKDTree(grid[["lat", "lon"]].to_numpy())
    dist, idx = tree.query(df[[lat, lon]].to_numpy(dtype="float64"), k=1)
    ok = dist <= C.GRID_RES * C.GRID_MATCH_FACTOR
    out = df.copy()
    out["cell_id"] = np.where(ok, grid["cell_id"].to_numpy()[idx], None)
    return out


# ----------------------------------------------------------------- GEE (CHIRPS + ERA5-Land)
def read_gee(grid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Baca semua CSV hasil ekspor GEE. Satu file boleh memuat CHIRPS+ERA5 sekaligus,
    atau terpisah (chirps_*.csv, era5_*.csv). Hasil: (tabel CHIRPS, tabel ERA5-Land)."""
    files = _list(C.P.gee_dir)
    if not files:
        raise FileNotFoundError(f"Tidak ada CSV GEE di {C.P.gee_dir}")
    chirps_parts, era5_parts = [], []
    for f in files:
        d = resolve_columns(pd.read_csv(f, low_memory=False), C.GEE_ALIASES, name=f.name)
        if "date" not in d.columns:
            raise ValueError(f"[{f.name}] kolom tanggal tidak ditemukan. Kolom: {list(d.columns)}")
        if "cell_id" not in d.columns:
            if not {"lat", "lon"} <= set(d.columns):
                raise ValueError(f"[{f.name}] tidak ada cell_id maupun lat/lon. Kolom: {list(d.columns)}")
            d = assign_to_grid(d, grid)
        d["source_file"] = f.name
        key = ["cell_id", "date", "source_file"]
        has_p = "precip_mm" in d.columns
        era_cols = [c for c in C.ERA5_COLS if c in d.columns]
        if has_p:
            chirps_parts.append(d[key + ["precip_mm"]])
        if era_cols:
            era5_parts.append(d[key + era_cols])
        log.info("GEE dibaca: %s (%d baris) | CHIRPS=%s ERA5=%s", f.name, len(d), has_p, era_cols)
    if not chirps_parts:
        raise ValueError("Kolom curah hujan (CHIRPS) tidak ditemukan di file GEE. Cek GEE_ALIASES['precip_mm'].")
    if not era5_parts:
        raise ValueError("Kolom ERA5-Land tidak ditemukan di file GEE. Cek GEE_ALIASES.")
    return pd.concat(chirps_parts, ignore_index=True), pd.concat(era5_parts, ignore_index=True)


# ----------------------------------------------------------------- orkestrasi tahap 1
def run(qc: QC) -> dict:
    prov = []
    firms = read_firms()
    prov += file_provenance(_list(C.P.firms_dir), "NASA FIRMS")
    grid = load_grid()
    prov += file_provenance(_list(C.P.static_dir), "grid (DIMAS-TI)") if _list(C.P.static_dir) else []
    prov += file_provenance(_list(C.P.boundary_dir, ("*.zip", "*.geojson", "*.shp")), "geoBoundaries")
    chirps, era5 = read_gee(grid)
    prov += file_provenance(_list(C.P.gee_dir), "GEE (CHIRPS + ERA5-Land)")

    qc.add("1_ingest", "firms_rows_raw", len(firms))
    qc.add("1_ingest", "chirps_rows_raw", len(chirps))
    qc.add("1_ingest", "era5_rows_raw", len(era5))
    qc.add("1_ingest", "grid_cells", len(grid))
    qc.add("1_ingest", "n_source_files", len(prov))

    save_json({"raw_dir": C.P.raw.name, "files": [{k: v for k, v in r.items() if k != "abs_path"} for r in prov]},
              C.P.qc / "provenance_raw.json")
    return {"firms": firms, "chirps": chirps, "era5": era5, "grid": grid, "provenance": prov}
