"""
Jalankan seluruh pipeline dari terminal VS Code:

    python scripts/run_pipeline.py --demo          # uji coba dengan DATA SINTETIS (otomatis dibuat)
    python scripts/run_pipeline.py                 # DATA ASLI di data/raw_sample/
    python scripts/run_pipeline.py --raw-dir D:/karhutla/raw_full   # data asli di lokasi lain
    python scripts/run_pipeline.py --skip-model    # lewati tahap klasifikasi
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.runner import run_all  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Pipeline Data Wrangling Karhutla 2026")
    ap.add_argument("--demo", action="store_true", help="pakai data sintetis (HANYA uji coba, bukan untuk dikumpulkan)")
    ap.add_argument("--raw-dir", default=None, help="folder data mentah (default: data/raw_sample)")
    ap.add_argument("--skip-model", action="store_true", help="lewati tahap 10 (klasifikasi)")
    a = ap.parse_args()
    if a.demo:
        from make_demo_data import generate
        generate()
    run_all("demo" if a.demo else "real", a.raw_dir, a.skip_model)


if __name__ == "__main__":
    main()
