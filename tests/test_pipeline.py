"""
Uji otomatis pipeline (jalankan: pytest -q). Memakai DATA DEMO sintetis, jadi aman dijalankan kapan saja.
Tes-tes ini juga bahan jawaban untuk pertanyaan dosen: 'bagaimana Anda memastikan hasilnya benar?'
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_demo_data import generate            # noqa: E402
from pipeline.runner import run_all            # noqa: E402
from pipeline import s07_features, config as C  # noqa: E402
from pipeline.utils import QC, temporal_split  # noqa: E402


@pytest.fixture(scope="module")
def res():
    generate()
    return run_all("demo", skip_model=False)


def test_kunci_unik_dan_tidak_ada_penggandaan_baris(res):
    integ = res["integrated"]
    assert not integ.duplicated(["cell_id", "date"]).any()
    assert res["qc"].data["stages"]["4_integration"]["baris_sebelum_join"] == len(integ)


def test_clean_dataset_bersih(res):
    f = res["export"]["final"]
    assert f[["precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist"]].isna().sum().sum() == 0
    assert (f["date"] == f["date"].dt.normalize()).all()
    assert f["rh_pct"].between(0, 100).all() and f["temp_c"].between(-15, 50).all()
    assert (f["precip_mm"] >= 0).all()


def test_file_mentah_tidak_berubah(res):
    assert res["export"]["integrity"]["raw_intact"]


def test_file_output_ada(res):
    for n in ("dataset_karhutla_2026_clean.parquet", "dataset_karhutla_2026_clean_sample.csv", "kamus_data.csv"):
        assert (C.P.cleaned / n).exists()


def test_tidak_ada_data_leakage_pada_fitur_historis(res):
    """Ubah SEMUA nilai mulai tanggal t0. Fitur baris dengan tanggal <= t0 tidak boleh berubah."""
    base = res["flagged"].copy()
    t0 = pd.Timestamp("2026-06-15")
    a = s07_features.build_features(base, QC())
    pert = base.copy()
    m = pert["date"] >= t0
    rng = np.random.default_rng(0)
    for c in ("precip_mm", "temp_c", "rh_pct", "wind_ms", "soil_moist", "frp_sum"):
        pert.loc[m, c] = rng.uniform(0, 50, m.sum()).astype("float32")
    pert.loc[m, "hotspot_count"] = rng.integers(0, 5, m.sum()).astype("int32")
    b = s07_features.build_features(pert, QC())
    lag = list(s07_features.LAG_SPEC)
    sel = a["date"] <= t0
    pd.testing.assert_frame_equal(a.loc[sel, lag].reset_index(drop=True), b.loc[sel, lag].reset_index(drop=True))
    # hari kering berturut-turut memakai data sampai t (termasuk t), jadi cek hanya tanggal sebelum t0
    sel2 = a["date"] < t0
    pd.testing.assert_series_equal(a.loc[sel2, "dry_days_streak"].reset_index(drop=True),
                                   b.loc[sel2, "dry_days_streak"].reset_index(drop=True))


def test_target_memakai_horizon_7_hari(res):
    d = res["features"]["df"]
    last7 = d["date"] > d["date"].max() - pd.Timedelta(days=C.HORIZON)
    assert d.loc[last7, "y_hotspot_next7"].isna().all()
    one = d[d["cell_id"] == d["cell_id"].iloc[0]].sort_values("date").reset_index(drop=True)
    i = 100
    expected = int(one.loc[i + 1:i + 7, "hotspot_count"].sum() > 0)
    assert int(one.loc[i, "y_hotspot_next7"]) == expected


def test_split_temporal_tanpa_tumpang_tindih(res):
    d = res["features"]["df"]
    m = temporal_split(d)
    assert d.loc[m["train"], "date"].max() < d.loc[m["val"], "date"].min()
    assert d.loc[m["val"], "date"].max() < d.loc[m["test"], "date"].min()
    gap = d.loc[m["val"], "date"].min() - d.loc[m["train"], "date"].max()
    assert gap >= pd.Timedelta(days=C.HORIZON)


def test_klasifikasi_menghasilkan_metrik(res):
    r = res["model"]
    for k in ("baseline_prevalensi", "logreg_scaled", "lightgbm"):
        assert 0 <= r[k]["pr_auc"] <= 1
