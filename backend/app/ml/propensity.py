"""Lead propensity model: which leads are worth a call?

Trained on the 5,000 Q2 leads using only what is known when a lead arrives
(no funnel dates or outcomes, so no leakage). Logistic regression is used on
purpose: each lead's score can be explained as a sum of feature effects,
which a sales partner can read ("has GSTIN +, mobile hotspot today -").
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.data_store import get_store

CATEGORICAL = ["lead_source", "segment", "preferred_language", "annual_turnover_band", "current_internet", "contact_role"]
NUMERIC = ["city_tier", "log_employees", "num_sites", "gst", "udyam", "log_spend", "n_interest"]

PRETTY = {
    "gst": "Has GSTIN", "udyam": "Has Udyam", "log_employees": "Team size", "num_sites": "Number of sites",
    "log_spend": "Current telecom spend", "n_interest": "Products asked about", "city_tier": "City tier",
}

# Drop reasons a digital journey can recover (no salesperson needed).
RECOVERABLE = {
    "Owner had no time for a visit": "Send the WhatsApp advisor link; no visit needed",
    "Visit not scheduled by sales": "Send the WhatsApp advisor link; no visit needed",
    "Quote took too long to arrive": "Instant quote in the advisor",
    "Quote too complex to understand": "One-line monthly price with plain-language reasons",
    "Found paperwork too long": "2-minute GSTIN lookup and photo KYC",
    "Missing GST or Udyam document": "Instant GSTIN/Udyam lookup instead of uploads",
    "Authorised signatory not available": "Remote e-sign by the signatory",
    "Unreachable after 3 attempts": "WhatsApp nudge in preferred language",
    "Price too high": "Show a cheaper eligible bundle (e.g. 5G AirFiber)",
    "Decided to wait": "Reminder with the saved quote",
}


def features(df: pd.DataFrame) -> pd.DataFrame:
    out = df[CATEGORICAL].copy()
    out["city_tier"] = df["city_tier"].astype(float)
    out["log_employees"] = np.log1p(df["employee_count"].astype(float))
    out["num_sites"] = df["num_sites"].astype(float)
    out["gst"] = (df["has_gstin"] == "Y").astype(float)
    out["udyam"] = (df["has_udyam"] == "Y").astype(float)
    out["log_spend"] = np.log1p(df["monthly_telecom_spend_inr"].fillna(0).astype(float))
    out["n_interest"] = df["products_of_interest"].fillna("").str.count(";") + 1
    return out


class PropensityModel:
    def __init__(self) -> None:
        leads = get_store().leads
        X, y = features(leads), (leads["outcome"] == "Activated").astype(int)
        pre = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", StandardScaler(), NUMERIC),
        ])
        self.pipe = Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced"))])
        oof = cross_val_predict(self.pipe, X, y, cv=5, method="predict_proba")[:, 1]
        self.auc = round(float(roc_auc_score(y, oof)), 3)
        self.pipe.fit(X, y)
        self.base_rate = float(y.mean())
        # lift: activation rate in the top 20% of scores vs overall
        top = oof >= np.quantile(oof, 0.8)
        self.top20_rate = round(float(y[top].mean()), 3)
        self.top20_capture = round(float(y[top].sum() / y.sum()), 3)
        self.names = list(self.pipe.named_steps["pre"].get_feature_names_out())
        self.coef = self.pipe.named_steps["lr"].coef_[0]

    def score(self, df: pd.DataFrame) -> np.ndarray:
        return self.pipe.predict_proba(features(df))[:, 1]

    def explain(self, row: pd.DataFrame, k: int = 3) -> list[dict]:
        """Top feature contributions (in log-odds) for one lead."""
        x = self.pipe.named_steps["pre"].transform(features(row))
        x = x.toarray()[0] if hasattr(x, "toarray") else x[0]
        contrib = x * self.coef
        order = np.argsort(-np.abs(contrib))[:k]
        out = []
        for i in order:
            name = self.names[i].split("__", 1)[1]
            for c in CATEGORICAL:
                if name.startswith(c + "_"):
                    name = f"{c.replace('_', ' ').title()}: {name[len(c) + 1:]}"
                    break
            else:
                name = PRETTY.get(name, name)
            out.append({"factor": name, "effect": "up" if contrib[i] > 0 else "down", "weight": round(float(contrib[i]), 2)})
        return out

    def summary(self) -> dict:
        return {"auc": self.auc, "base_rate": round(self.base_rate, 3), "top20_activation_rate": self.top20_rate,
                "top20_share_of_activations": self.top20_capture, "model": "Logistic regression, 5-fold CV"}


@lru_cache
def get_model() -> PropensityModel:
    return PropensityModel()


def call_list(limit: int = 50) -> list[dict]:
    """Dropped leads ranked by win probability, with the digital fix for their drop reason."""
    leads = get_store().leads
    dropped = leads[(leads["outcome"] == "Dropped") & leads["drop_reason"].isin(RECOVERABLE)].copy()
    m = get_model()
    dropped["score"] = m.score(dropped)
    top = dropped.sort_values("score", ascending=False).head(limit)
    out = []
    for _, r in top.iterrows():
        row = top.loc[[_]]
        out.append({
            "lead_id": r.lead_id, "business_name": r.business_name, "business_type": r.business_type,
            "segment": r.segment, "city": r.city, "language": r.preferred_language, "source": r.lead_source,
            "stage_reached": r.stage_reached, "drop_reason": r.drop_reason, "score": round(float(r.score), 3),
            "next_action": RECOVERABLE[r.drop_reason], "why": m.explain(row),
        })
    return out
