"""Train the disruption-risk model and write risk_model.pkl.

    python train_risk.py              # generate data if missing, train, evaluate, save
    python train_risk.py --rows 20000 # bigger synthetic sample

Saves a payload rather than a bare model so `risk.py` can verify at load time
that the feature order it is about to send matches the order used in training.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                             classification_report, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
import xgboost as xgb
from xgboost import XGBClassifier

from features import FEATURES

HERE = Path(__file__).parent
DATA = HERE / "data" / "training_data.csv"
MODEL_PATH = HERE / "risk_model.pkl"
METRICS_PATH = HERE / "metrics.json"
MODEL_VERSION = "0.1.0"
LABEL = "disrupted_48h"


def load_data(rows: int) -> pd.DataFrame:
    if not DATA.exists():
        print(f"{DATA.name} not found - generating {rows} rows first")
        subprocess.run([sys.executable, str(HERE / "make_dataset.py"), "-n", str(rows)],
                       check=True, cwd=HERE)
    return pd.read_csv(DATA)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=int, default=6000, help="rows to generate if data is missing")
    ap.add_argument("--seed", type=int, default=26002)
    args = ap.parse_args()

    df = load_data(args.rows)
    X, y = df[FEATURES], df[LABEL]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=args.seed, stratify=y)

    # NOTE: deliberately NOT using scale_pos_weight.
    #
    # Disruptions are the minority class, and the instinct is to weight them up
    # because missing one is expensive. That is wrong for this model. Nothing
    # downstream consumes a class label - score.py turns the probability into an
    # accessibility score and routing.py turns it into an expected-delay cost -
    # so what we need is a CALIBRATED probability, not a decision-shifted one.
    #
    # Measured on this data, weighting cost us on every axis that matters:
    # mean prediction 0.264 against a true rate of 0.173, Brier 0.103 -> 0.083
    # unweighted, and the wet-weather gap between a landslide-prone highway and
    # a safe alternate collapsed from 0.148 to 0.036 - which left the router
    # unable to tell the two roads apart at all.
    #
    # The asymmetric cost of being wrong belongs where the decision is made:
    # DISRUPTION_COST_MIN in routing.py and the band thresholds in risk.py.

    model = XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.06,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=4,
        reg_lambda=1.5,
        eval_metric="aucpr",
        random_state=args.seed,
        n_jobs=4,
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    metrics = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "base_rate": round(float(y.mean()), 4),
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "precision": round(float(precision_score(y_test, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_test, proba)), 4),
        "brier": round(float(brier_score_loss(y_test, proba)), 4),
        "confusion_matrix": confusion_matrix(y_test, pred).tolist(),
        "data_source": "synthetic (make_dataset.py) - NOT field-validated",
    }

    # Global feature importance via exact TreeSHAP. `pred_contribs` is XGBoost's
    # built-in implementation, so the dashboard's "why is this road red" panel
    # needs no extra dependency at inference time.
    dtest = xgb.DMatrix(X_test, feature_names=FEATURES)
    contribs = model.get_booster().predict(dtest, pred_contribs=True)
    importance = np.abs(contribs[:, :-1]).mean(axis=0)
    metrics["mean_abs_shap"] = {f: round(float(v), 4)
                                for f, v in sorted(zip(FEATURES, importance),
                                                   key=lambda kv: -kv[1])}

    joblib.dump({"model": model, "features": FEATURES,
                 "xgboost_version": xgb.__version__,
                 "model_version": MODEL_VERSION,
                 "trained_at": metrics["trained_at"],
                 "metrics": {k: metrics[k] for k in
                             ("roc_auc", "pr_auc", "f1", "precision", "recall", "brier")}},
                MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n")

    print(classification_report(y_test, pred, target_names=["clear", "disrupted"],
                                zero_division=0))
    print(f"ROC-AUC {metrics['roc_auc']}  PR-AUC {metrics['pr_auc']}  "
          f"Brier {metrics['brier']}")
    print("\ntop features by mean |SHAP|:")
    for name, value in list(metrics["mean_abs_shap"].items())[:5]:
        print(f"  {name:<18} {value}")
    print(f"\nsaved {MODEL_PATH.name} and {METRICS_PATH.name}")


if __name__ == "__main__":
    main()
