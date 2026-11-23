"""
copy_raw_from_dimasti.py — SALIN (bukan pindah) data mentah dari folder proyek DIMAS-TI ke data/raw_sample/

Contoh (Windows):
  python scripts/copy_raw_from_dimasti.py --root "D:/DIMAS-TI/karhutla"
  python scripts/copy_raw_from_dimasti.py --root "D:/DIMAS-TI/karhutla" --provinces riau jambi --date-from 2026-06-01 --date-to 2026-09-30

Yang disalin (sesuai manifest DIMAS-TI):
  data/raw/firms_raw.csv                         -> data/raw_sample/firms/        (bisa difilter tanggal)
  data/processing/gee_2026_downloads/gee26_*.csv -> data/raw_sample/gee/          (difilter provinsi & tanggal dari nama file)
  data/raw/geoBoundaries-IDN-ADM1-all.zip        -> data/raw_sample/boundary/
  data/interim/grid.csv                          -> data/raw_sample/static/       (agar cell_id sama dg proyek lama)
Tidak ada file DIMAS-TI yang diubah/dihapus. Model, aplikasi web, dan lightgbm-3.3.0 SENGAJA tidak disalin
(bukan bagian pipeline data).
Subset (provinsi/tanggal) harus disetujui dosen (Proposal 4.2) dan dijelaskan di laporan.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw_sample"


def mb(p: Path) -> float:
    return p.stat().st_size / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="folder 'karhutla' dari proyek DIMAS-TI")
    ap.add_argument("--provinces", nargs="*", default=None,
                    help="filter provinsi untuk file GEE, mis. riau jambi kalimantan_tengah (default: semua)")
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    a = ap.parse_args()
    src = Path(a.root)
    if not (src / "data").exists():
        sys.exit(f"Folder {src} tidak berisi subfolder 'data'. Arahkan --root ke folder 'karhutla'.")
    for sub in ("firms", "gee", "boundary", "static"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    d0 = pd.Timestamp(a.date_from) if a.date_from else None
    d1 = pd.Timestamp(a.date_to) if a.date_to else None
    total = 0.0

    # --- FIRMS (dibaca per potongan agar hemat memori)
    f = src / "data" / "raw" / "firms_raw.csv"
    if f.exists():
        dst = OUT / "firms" / "firms_raw.csv"
        if d0 is None and d1 is None:
            shutil.copy2(f, dst)
        else:
            first = True
            for chunk in pd.read_csv(f, chunksize=500_000, low_memory=False):
                col = next((c for c in chunk.columns if c.lower() in ("acq_date", "date", "tanggal")), None)
                if col is None:
                    sys.exit(f"Kolom tanggal tidak ditemukan di {f.name}: {list(chunk.columns)}")
                dt = pd.to_datetime(chunk[col], errors="coerce")
                keep = pd.Series(True, index=chunk.index)
                if d0 is not None:
                    keep &= dt >= d0
                if d1 is not None:
                    keep &= dt <= d1
                chunk[keep].to_csv(dst, mode="w" if first else "a", header=first, index=False)
                first = False
        print(f"FIRMS      -> {dst.name}  {mb(dst):8.1f} MB")
        total += mb(dst)
    else:
        print("! firms_raw.csv tidak ditemukan di", f)

    # --- GEE: filter dari nama file  gee26_YYYYMMDD_YYYYMMDD_<provinsi>_cXXXXX_hash.csv
    n = 0
    for g in sorted((src / "data" / "processing" / "gee_2026_downloads").glob("gee26_*.csv")):
        m = re.match(r"gee26_(\d{8})_(\d{8})_(.+?)_c\d+_", g.name)
        if not m:
            continue
        s, e, prov = pd.Timestamp(m.group(1)), pd.Timestamp(m.group(2)), m.group(3)
        if a.provinces and prov not in a.provinces:
            continue
        if (d0 is not None and e < d0) or (d1 is not None and s > d1):
            continue
        shutil.copy2(g, OUT / "gee" / g.name)
        n += 1
        total += mb(g)
    print(f"GEE        -> {n} file")

    for rel, sub in (("data/raw/geoBoundaries-IDN-ADM1-all.zip", "boundary"), ("data/interim/grid.csv", "static")):
        p = src / rel
        if p.exists():
            shutil.copy2(p, OUT / sub / p.name)
            total += mb(p)
            print(f"{sub:10s} -> {p.name}")
        else:
            print("! tidak ditemukan:", p)
    print(f"\nTotal ukuran data mentah di data/raw_sample: {total:.0f} MB")
    print("Batas unggah LMS? Persempit dengan --provinces / --date-from / --date-to (dan minta persetujuan dosen).")
    print("Berikutnya:  python scripts/run_pipeline.py")


if __name__ == "__main__":
    main()
