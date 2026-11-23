"""
config.py — SATU-SATUNYA tempat mengatur path dan parameter pipeline.

Kalau dosen bertanya "kenapa angkanya segini?", jawabannya ada di sini:
semua parameter (resolusi grid, horizon target, batas split, dll.) dikumpulkan
dan diberi komentar alasan.
"""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]          # folder uas_data_wrangling/

# --------------------------------------------------------------------------
# 1. PATH  (mode "real" = data asli di data/raw_sample, mode "demo" = data sintetis uji coba)
# --------------------------------------------------------------------------
P = SimpleNamespace()


def set_mode(mode: str = "real", raw_dir: str | Path | None = None) -> SimpleNamespace:
    """Atur semua path sesuai mode. Dipanggil oleh run_pipeline.py / notebook."""
    assert mode in ("real", "demo")
    if mode == "demo":
        base = ROOT / "data" / "demo"
        P.raw = base / "raw"
        P.interim = base / "interim"
        P.cleaned = base / "cleaned"
        P.out = base / "outputs"
    else:
        P.raw = Path(raw_dir) if raw_dir else ROOT / "data" / "raw_sample"
        P.interim = ROOT / "data" / "interim"
        P.cleaned = ROOT / "data" / "cleaned"
        P.out = ROOT / "outputs"
    P.mode = mode
    P.firms_dir = P.raw / "firms"
    P.gee_dir = P.raw / "gee"
    P.boundary_dir = P.raw / "boundary"
    P.static_dir = P.raw / "static"
    P.profiling = P.out / "profiling"
    P.figures = P.out / "figures"
    P.qc = P.out / "quality_control"
    P.tables = P.out / "tables"
    for d in (P.interim, P.cleaned, P.profiling, P.figures, P.qc, P.tables):
        d.mkdir(parents=True, exist_ok=True)
    return P


set_mode("real")

# --------------------------------------------------------------------------
# 2. CAKUPAN PROYEK (Proposal Subbab 1.5)
# --------------------------------------------------------------------------
PROVINCES = ["Kalimantan Tengah", "Kalimantan Barat", "Kalimantan Selatan",
             "Sumatera Selatan", "Jambi", "Riau"]
# geoBoundaries kadang memakai nama Inggris -> samakan
PROVINCE_SYNONYMS = {
    "central kalimantan": "Kalimantan Tengah", "west kalimantan": "Kalimantan Barat",
    "south kalimantan": "Kalimantan Selatan", "south sumatra": "Sumatera Selatan",
    "south sumatera": "Sumatera Selatan", "kalimantan tengah": "Kalimantan Tengah",
    "kalimantan barat": "Kalimantan Barat", "kalimantan selatan": "Kalimantan Selatan",
    "sumatera selatan": "Sumatera Selatan", "jambi": "Jambi", "riau": "Riau",
}
DATE_START = "2026-01-01"
DATE_END = "2026-09-30"
GRID_RES = 0.045            # derajat (~5 km) -> unit pengamatan
GRID_MATCH_FACTOR = 0.75    # titik dianggap masuk grid bila jarak ke pusat sel <= 0.75*GRID_RES
INDONESIA_BBOX = dict(lat=(-11.5, 6.5), lon=(94.5, 141.5))   # untuk membuang koordinat ngawur

# --------------------------------------------------------------------------
# 3. ALIAS NAMA KOLOM  (kalau kolom data asli beda nama, TAMBAHKAN di sini)
#    Pencocokan tidak peka huruf besar/kecil dan mengabaikan tanda baca.
# --------------------------------------------------------------------------
FIRMS_ALIASES = {
    "lat": ["latitude", "lat"],
    "lon": ["longitude", "lon", "long", "lng"],
    "acq_date": ["acq_date", "date", "tanggal"],
    "acq_time": ["acq_time", "time"],
    "frp": ["frp", "fire_radiative_power"],
    "confidence": ["confidence", "conf"],
    "satellite": ["satellite", "sat"],
    "instrument": ["instrument"],
    "daynight": ["daynight", "day_night"],
    "brightness": ["brightness", "bright_ti4", "bright_t21"],
}
GEE_ALIASES = {
    "cell_id": ["cell_id", "cellid", "grid_id"],
    "date": ["date", "tanggal", "acq_date"],
    "lat": ["lat", "latitude"],
    "lon": ["lon", "longitude", "lng"],
    "province": ["province", "provinsi", "shapeName"],
    "precip_mm": ["precip_mm", "precipitation", "precip", "chirps_precip", "rain_mm", "rain"],
    "t2m_k": ["temperature_2m", "t2m", "temp_k", "temperature_2m_k"],
    "d2m_k": ["dewpoint_temperature_2m", "d2m", "dewpoint_k"],
    "soil_moist": ["volumetric_soil_water_layer_1", "swvl1", "soil_moisture", "soil_moist"],
    "u10": ["u_component_of_wind_10m", "u10", "wind_u"],
    "v10": ["v_component_of_wind_10m", "v10", "wind_v"],
}
GRID_ALIASES = {
    "cell_id": ["cell_id", "cellid", "grid_id"],
    "lat": ["lat", "latitude", "lat_center", "center_lat"],
    "lon": ["lon", "longitude", "lon_center", "center_lon"],
    "province": ["province", "provinsi", "shapeName"],
}
ERA5_COLS = ["t2m_k", "d2m_k", "soil_moist", "u10", "v10"]

# --------------------------------------------------------------------------
# 4. ATURAN DOMAIN FISIK  (nilai di luar rentang = KESALAHAN DATA, bukan kejadian ekstrem)
# --------------------------------------------------------------------------
NODATA_SENTINELS = [-9999, -999, 9999, 65535]
DOMAIN_RULES = {                # (min, max) inklusif
    "precip_mm": (0, 1000),     # curah hujan harian tidak negatif; >1000 mm/hari mustahil
    "temp_c": (-15, 50),
    "dewpoint_c": (-40, 40),
    "rh_pct": (0, 100),
    "wind_ms": (0, 60),
    "soil_moist": (0, 1),       # m3/m3
    "frp": (0, 5000),           # MW
}

# --------------------------------------------------------------------------
# 5. MISSING VALUES & OUTLIER
# --------------------------------------------------------------------------
IMPUTE_MASK_FRAC = 0.05         # % nilai yang disembunyikan untuk menguji strategi imputasi
IMPUTE_EVAL_CELLS = 500         # jumlah sel sampel untuk evaluasi (supaya cepat)
FFILL_LIMIT = 3                 # maks. hari forward-fill
CAUSAL_STRATEGIES = ["global_mean", "cell_median", "ffill_cell", "province_date_mean",
                     "ffill_then_province_date"]   # hanya memakai informasi masa lalu / hari yang sama
IQR_K = 1.5
IQR_ON_POSITIVE = ["precip_mm", "frp_sum"]   # data zero-inflated: IQR dihitung pada nilai > 0
WET_DAY_MM = 0.1
# Keputusan perlakuan outlier per variabel: keep_flag | cap | remove  (alasan dibahas di notebook)
OUTLIER_DECISION = {"precip_mm": "keep_flag", "temp_c": "keep_flag", "rh_pct": "keep_flag",
                    "wind_ms": "keep_flag", "soil_moist": "keep_flag",
                    "frp_sum": "keep_flag"}
MV_CONTAMINATION = 0.005        # Isolation Forest: kira-kira 0,5% baris dianggap anomali multivariat
MV_FIT_ROWS = 100_000

# --------------------------------------------------------------------------
# 6. FEATURE ENGINEERING / SPLIT / MODEL
# --------------------------------------------------------------------------
HORIZON = 7                     # target: ada hotspot dalam 7 hari ke depan
LABEL_NOMINAL_HIGH_ONLY = False # True = target hanya menghitung deteksi berkepercayaan nominal/tinggi (spesifikasi Orang A lomba); False = semua deteksi (sesuai proposal UAS)
DRY_DAY_MM = 1.0                # hari kering = hujan < 1 mm
LAG_WINDOWS = (7, 14, 30)
WARMUP_DAYS = 30                # 30 hari pertama fitur historis (jendela terpanjang) belum lengkap
VAL_START = "2026-08-01"        # train: Jan-Jul | validasi: Agustus | uji: September (sesuai proposal)
TEST_START = "2026-09-01"
CORR_DROP_THRESHOLD = 0.95      # pasangan fitur dg |Spearman| > ini dianggap redundan
EDA_SAMPLE_ROWS = 300_000
MAX_TRAIN_ROWS = None           # isi mis. 1_500_000 bila laptop kewalahan
CSV_SAMPLE_CELLS = 300          # CSV ringan = 300 sel x semua tanggal
RANDOM_STATE = 42
