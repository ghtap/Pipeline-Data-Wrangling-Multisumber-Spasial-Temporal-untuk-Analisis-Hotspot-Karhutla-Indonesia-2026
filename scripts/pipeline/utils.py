"""utils.py — fungsi bantu: logging, hash file (bukti file mentah utuh), catatan QC, simpan gambar."""
from __future__ import annotations
import hashlib
import json
import logging
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("wrangling")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def resolve_columns(df: pd.DataFrame, aliases: dict, required=(), name: str = "") -> pd.DataFrame:
    """Samakan nama kolom dari sumber berbeda ke nama baku (standardisasi nama kolom, Proposal 3.4b)."""
    lookup = {_norm(c): c for c in df.columns}
    rename, used = {}, set()
    for canon, alts in aliases.items():
        for a in [canon, *alts]:
            src = lookup.get(_norm(a))
            if src is not None and src not in used:
                rename[src] = canon
                used.add(src)
                break
    out = df.rename(columns=rename)
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(
            f"[{name}] kolom wajib tidak ditemukan: {missing}\n"
            f"Kolom yang ada di file: {list(df.columns)}\n"
            f"-> Tambahkan nama kolom aslinya ke alias di scripts/pipeline/config.py")
    return out


def parse_dates_flex(s: pd.Series) -> tuple[pd.Series, int, int]:
    """Ubah teks tanggal campur-aduk menjadi datetime baku (YYYY-MM-DD).
    Return: (datetime, jumlah_format_non_ISO_yang_diperbaiki, jumlah_gagal_parse)."""
    s = s.astype("string").str.strip()
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    bad = iso.isna() & s.notna()
    n_fixed = 0
    if bad.any():
        alt = pd.to_datetime(s[bad], dayfirst=True, errors="coerce", format="mixed")
        iso.loc[bad] = alt
        n_fixed = int(alt.notna().sum())
    n_fail = int(iso.isna().sum() - s.isna().sum())
    return iso.dt.normalize(), n_fixed, n_fail


class QC:
    """Pencatat kualitas data: setiap tahap menulis angka sebelum/sesudah -> qc_report.json."""

    def __init__(self):
        self.data: dict = {"mode": C.P.mode, "stages": {}}
        self.t0 = time.time()

    def add(self, stage: str, key: str, value):
        self.data["stages"].setdefault(stage, {})[key] = _jsonable(value)
        log.info("[%s] %s = %s", stage, key, value if not isinstance(value, (dict, list)) else "...")

    def save(self, path: Path | None = None):
        path = path or (C.P.qc / "qc_report.json")
        self.data["runtime_seconds"] = round(time.time() - self.t0, 1)
        path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime("%Y-%m-%d")
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, float) and np.isnan(o):
        return None
    return o


def save_json(obj, path: Path):
    Path(path).write_text(json.dumps(_jsonable(obj), indent=2, ensure_ascii=False), encoding="utf-8")


def save_fig(fig, name: str):
    path = C.P.figures / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    log.info("gambar disimpan: %s", path.name)
    return path


def temporal_split(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Split TEMPORAL (bukan acak) + embargo selama HORIZON hari.
    Target baris tanggal t memakai data t+1..t+7, jadi baris train terakhir harus
    >= 7 hari sebelum awal validasi, supaya tidak ada informasi masa depan bocor."""
    d = df["date"]
    h = pd.Timedelta(days=C.HORIZON)
    ok = df["y_hotspot_next7"].notna() & ~df["warmup"]
    val_s, test_s = pd.Timestamp(C.VAL_START), pd.Timestamp(C.TEST_START)
    return {
        "train": ok & (d < val_s - h),
        "val": ok & (d >= val_s) & (d < test_s - h),
        "test": ok & (d >= test_s),
    }
