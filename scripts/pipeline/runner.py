"""runner.py — menjalankan 10 tahap berurutan. Dipakai oleh run_pipeline.py dan notebook."""
from __future__ import annotations
from . import config as C
from .utils import QC, log
from . import (s01_ingest, s02_profiling, s03_cleaning, s04_integration, s05_outliers,
               s06_scaling, s07_features, s08_eda_corr, s09_export, s10_classification)


def run_all(mode: str = "real", raw_dir=None, skip_model: bool = False) -> dict:
    C.set_mode(mode, raw_dir)
    qc = QC()
    log.info("=== MODE: %s | raw: %s ===", mode, C.P.raw)

    raw = s01_ingest.run(qc)                                   # 1. ingestion
    s02_profiling.run(raw, qc)                                 # 2. profiling data mentah
    clean = s03_cleaning.run(raw, qc)                          # 3. standardisasi, cleaning, missing values
    s02_profiling.profile_table(clean["firms"], "firms_bersih")      # profil SESUDAH cleaning (pembanding)
    s02_profiling.profile_table(clean["meteo"], "meteo_bersih")
    integ = s04_integration.run(clean, raw, qc)                # 4. integrasi spasial-temporal
    flagged, iqr_tab = s05_outliers.run(integ, qc)             # 5. outlier
    s06_scaling.run(flagged, qc)                               # 6. scaling
    feat = s07_features.run(flagged, qc)                       # 7. feature engineering + seleksi
    corr = s08_eda_corr.run(feat["df"], feat["selected"], qc)  # 8. EDA + korelasi
    export = s09_export.run(feat["df"], feat["selected"], raw, qc)   # 9. clean dataset
    model = None if skip_model else s10_classification.run(feat["df"], feat["selected"], qc)  # 10. klasifikasi
    qc.save()
    log.info("=== SELESAI. Hasil: %s ===", C.P.cleaned)
    return {"raw": raw, "clean": clean, "integrated": integ, "flagged": flagged, "iqr": iqr_tab,
            "features": feat, "corr": corr, "export": export, "model": model, "qc": qc}
