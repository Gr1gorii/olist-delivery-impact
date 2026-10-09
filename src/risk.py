import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.data import ROOT, time_split

NUMERIC = [
    "log_price", "freight_share", "item_count", "seller_count", "weight",
    "promised_days", "purchase_month", "purchase_weekday", "purchase_hour", "same_state",
    "seller_past_count", "seller_past_late", "region_past_count", "region_past_late",
    "category_past_count", "category_past_late",
]
CATEGORICAL = ["customer_state", "seller_state", "category"]
FEATURES = NUMERIC + CATEGORICAL


def make_model(kind, leaves=15):
    numeric = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    columns = ColumnTransformer([
        ("numeric", numeric, NUMERIC),
        ("category", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])
    if kind == "logistic":
        model = LogisticRegression(max_iter=1000, C=0.3, random_state=42)
    else:
        model = HistGradientBoostingClassifier(
            max_iter=150, max_leaf_nodes=leaves, learning_rate=0.07,
            l2_regularization=5, min_samples_leaf=50, early_stopping=False, random_state=42,
        )
    return make_pipeline(columns, model)


def metrics(y, probability):
    y = np.asarray(y)
    limit = max(1, int(np.ceil(len(y) * 0.1)))
    selected = np.argsort(-probability, kind="stable")[:limit]
    precision = y[selected].mean()
    return {
        "orders": len(y), "late_rate": float(y.mean()),
        "average_precision": float(average_precision_score(y, probability)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "brier": float(brier_score_loss(y, probability)),
        "precision_at_10pct": float(precision),
        "recall_at_10pct": float(y[selected].sum() / y.sum()),
        "lift_at_10pct": float(precision / y.mean()),
    }


def train_risk(frame):
    train, valid, test = time_split(frame)
    rows = []
    candidates = {}
    for name, kind, leaves in [("Logistic regression", "logistic", 15), ("Boosting 7", "boosting", 7), ("Boosting 15", "boosting", 15)]:
        model = make_model(kind, leaves)
        model.fit(train[FEATURES], train["late"])
        probability = model.predict_proba(valid[FEATURES])[:, 1]
        rows.append({"model": name, "period": "validation", **metrics(valid["late"], probability)})
        candidates[name] = (kind, leaves)
    best = max(rows, key=lambda row: row["average_precision"])["model"]
    refit = frame.loc[
        frame["order_purchase_timestamp"].lt("2018-04-01")
        & frame["order_delivered_customer_date"].lt("2018-04-01")
    ]
    for name in ["Constant", "Logistic regression", best]:
        if name == "Constant":
            probability = np.full(len(test), refit["late"].mean())
            result = metrics(test["late"], probability)
            result.update(precision_at_10pct=float(test["late"].mean()), recall_at_10pct=0.1, lift_at_10pct=1.0)
        else:
            kind, leaves = candidates[name]
            model = make_model(kind, leaves)
            model.fit(refit[FEATURES], refit["late"])
            probability = model.predict_proba(test[FEATURES])[:, 1]
            result = metrics(test["late"], probability)
            if name == best:
                joblib.dump(model, ROOT / "models" / "late_risk.joblib")
                test["risk"] = probability
        rows.append({"model": name, "period": "test", **result})
    summary = pd.DataFrame(rows).drop_duplicates(["model", "period"])
    splits = {
        "train": len(train), "validation": len(valid), "refit": len(refit), "test": len(test),
        "train_late_rate": float(train["late"].mean()),
        "validation_late_rate": float(valid["late"].mean()),
        "test_late_rate": float(test["late"].mean()), "selected": best,
    }
    return summary, test, refit, splits
