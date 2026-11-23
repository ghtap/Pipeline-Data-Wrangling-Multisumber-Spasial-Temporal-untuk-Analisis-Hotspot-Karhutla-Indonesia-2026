"""
TAHAP 10 — Analisis Lanjutan: Klasifikasi Biner  (Proposal 3.11)

Tujuan: MEMBUKTIKAN dataset hasil wrangling layak dipakai, bukan mengejar skor tertinggi.
Target  : 1 bila ada >= 1 hotspot pada 7 hari setelah tanggal pengamatan.
Split   : TEMPORAL — train Jan-Jul, validasi Agustus, uji September — dengan jeda (embargo) 7 hari.
Model   : LightGBM (utama; tanpa scaling), Logistic Regression (pembanding; dengan StandardScaler dari train),
          dan baseline 'prevalensi' (tebakan acak sesuai proporsi kelas positif).
Metrik  : PR-AUC (average precision), precision, recall, F1 — ambang dipilih dari VALIDASI, bukan dari uji.
Catatan : angka PR-AUC 0,5533 / F1 0,5363 dari penelitian DIMAS-TI adalah RUJUKAN terdahulu;
          angka di sini dihitung ulang dan tidak boleh disamakan begitu saja.
"""
from __future__ import annotations
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message=".*eval_set.*")

from . import config as C
from .utils import QC, log, save_fig, save_json, temporal_split


def _best_threshold(y, p) -> float:
    from sklearn.metrics import precision_recall_curve
    pr, rc, th = precision_recall_curve(y, p)
    f1 = 2 * pr[:-1] * rc[:-1] / np.maximum(pr[:-1] + rc[:-1], 1e-12)
    return float(th[int(np.nanargmax(f1))]) if len(th) else 0.5


def _metrics(y, p, thr) -> dict:
    from sklearn.metrics import average_precision_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score
    pred = (p >= thr).astype(int)
    out = {"pr_auc": float(average_precision_score(y, p)), "precision": float(precision_score(y, pred, zero_division=0)),
           "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0)),
           "threshold": float(thr), "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist()}
    try:
        out["roc_auc"] = float(roc_auc_score(y, p))
    except ValueError:
        out["roc_auc"] = None
    return out


def run(d: pd.DataFrame, features: list[str], qc: QC) -> dict:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    import matplotlib.pyplot as plt

    m = temporal_split(d)
    tr, va, te = d[m["train"]], d[m["val"]], d[m["test"]]
    if C.MAX_TRAIN_ROWS and len(tr) > C.MAX_TRAIN_ROWS:
        tr = tr.sample(C.MAX_TRAIN_ROWS, random_state=C.RANDOM_STATE)
    Xtr, ytr = tr[features].astype("float32"), tr["y_hotspot_next7"].astype(int)
    Xva, yva = va[features].astype("float32"), va["y_hotspot_next7"].astype(int)
    Xte, yte = te[features].astype("float32"), te["y_hotspot_next7"].astype(int)
    info = {"n_train": len(tr), "n_val": len(va), "n_test": len(te),
            "prevalensi_train": round(float(ytr.mean()), 4), "prevalensi_test": round(float(yte.mean()), 4),
            "train_s.d.": str(tr["date"].max().date()), "val_rentang": [str(va["date"].min().date()), str(va["date"].max().date())],
            "test_rentang": [str(te["date"].min().date()), str(te["date"].max().date())], "fitur": features}
    qc.add("10_classification", "split", info)
    if yte.nunique() < 2 or ytr.nunique() < 2:
        log.warning("Salah satu split hanya punya 1 kelas -> klasifikasi dilewati")
        return {"info": info}

    results, probs = {}, {}
    # --- baseline prevalensi: PR-AUC = proporsi positif pada data uji
    results["baseline_prevalensi"] = {"pr_auc": float(yte.mean()), "precision": float(yte.mean()),
                                      "recall": 1.0, "f1": float(2 * yte.mean() / (1 + yte.mean())), "threshold": 0.0}

    # --- Logistic Regression (butuh imputasi + scaling; parameter scaling dari train saja)
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(max_iter=1000, class_weight="balanced"))
    lr.fit(Xtr, ytr)
    p_va, p_te = lr.predict_proba(Xva)[:, 1], lr.predict_proba(Xte)[:, 1]
    results["logreg_scaled"] = _metrics(yte, p_te, _best_threshold(yva, p_va))
    probs["Logistic Regression (scaled)"] = p_te

    # --- LightGBM (tanpa scaling; menangani NaN sendiri); fallback ke HistGradientBoosting
    importance = None
    try:
        import lightgbm as lgb
        gbm = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.05, num_leaves=31, min_child_samples=100,
                                 subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_alpha=0.1,
                                 reg_lambda=1.0, random_state=C.RANDOM_STATE, n_jobs=-1, verbose=-1)
        fit_kw = {"eval_set": [(Xva, yva)], "eval_metric": "average_precision",
                  "callbacks": [lgb.early_stopping(50, verbose=False)]} if len(va) and yva.nunique() > 1 else {}
        gbm.fit(Xtr, ytr, **fit_kw)
        importance = pd.Series(gbm.booster_.feature_importance("gain"), index=features).sort_values()
        name = "LightGBM (regularized)"
        info["lightgbm_best_iteration"] = int(gbm.best_iteration_ or gbm.n_estimators)
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingClassifier
        gbm = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=C.RANDOM_STATE)
        gbm.fit(Xtr, ytr)
        name = "HistGradientBoosting (fallback; LightGBM belum terpasang)"
    p_va, p_te = gbm.predict_proba(Xva)[:, 1], gbm.predict_proba(Xte)[:, 1]
    results["lightgbm"] = _metrics(yte, p_te, _best_threshold(yva, p_va))
    results["lightgbm"]["model_name"] = name
    probs[name] = p_te

    # --- gambar
    from sklearn.metrics import precision_recall_curve
    fig, ax = plt.subplots(figsize=(6, 4.5))
    for nm, p in probs.items():
        pr, rc, _ = precision_recall_curve(yte, p)
        ax.plot(rc, pr, label=nm)
    ax.axhline(yte.mean(), color="gray", ls="--", label=f"baseline prevalensi ({yte.mean():.3f})")
    ax.set_xlabel("recall")
    ax.set_ylabel("precision")
    ax.set_title("Kurva Precision-Recall pada data uji (temporal)")
    ax.legend(fontsize=8)
    save_fig(fig, "klasifikasi_pr_curve.png")

    cm = np.array(results["lightgbm"]["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(3.8, 3.4))
    ax.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, f"{v:,}", ha="center", va="center", color="black")
    ax.set_xticks([0, 1], ["pred 0", "pred 1"])
    ax.set_yticks([0, 1], ["aktual 0", "aktual 1"])
    ax.set_title("Confusion matrix (uji)")
    save_fig(fig, "klasifikasi_confusion_matrix.png")

    if importance is not None:
        fig, ax = plt.subplots(figsize=(6, 0.3 * len(importance) + 1.5))
        ax.barh(importance.index, importance.values, color="#4f81bd")
        ax.set_title("Kepentingan fitur LightGBM (gain)")
        save_fig(fig, "klasifikasi_feature_importance.png")

    results["info"] = info
    save_json(results, C.P.out / "klasifikasi_metrik.json")
    pd.DataFrame({k: v for k, v in results.items() if k not in ("info",)}).T.drop(columns="confusion_matrix", errors="ignore") \
        .to_csv(C.P.tables / "klasifikasi_metrik.csv")
    qc.add("10_classification", "metrik_uji", {k: {m_: round(v_, 4) for m_, v_ in v.items() if isinstance(v_, float)}
                                                for k, v in results.items() if k != "info"})
    return results
