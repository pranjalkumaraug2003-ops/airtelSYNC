"""Business insights computed live from smb_leads.csv.

Every number quoted in the deck comes from this module, so the deck and the
prototype always agree.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from app.data_store import get_store
from app.rules.eligibility import audit_bundle

STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
SEG_SHORT = {"Micro retail & services": "micro", "Professional offices": "prof",
             "Small multi-site businesses": "multi", "Small manufacturers": "mfg"}


def _pct(x: float) -> float:
    return round(100 * float(x), 1)


@lru_cache
def compute() -> dict:
    store = get_store()
    d = store.leads.copy()
    d["act"] = d["outcome"] == "Activated"
    a = d[d["act"]].copy()
    a["churn"] = a["churned_within_6_months"] == "Y"

    # Funnel
    idx = {s: i for i, s in enumerate(STAGES)}
    reached = d["stage_reached"].map(idx)
    funnel = [{"stage": s, "count": int((reached >= i).sum())} for i, s in enumerate(STAGES)]

    # Drop reasons grouped by what fixes them
    drops = d.loc[~d["act"], "drop_reason"].value_counts()
    buckets = {
        "No visit / slow sales follow-up": ["Owner had no time for a visit", "Visit not scheduled by sales"],
        "Unreachable / wrong number": ["Unreachable after 3 attempts", "Wrong or invalid number"],
        "Quote slow or confusing": ["Quote took too long to arrive", "Quote too complex to understand"],
        "Paperwork / KYC friction": ["Found paperwork too long", "Missing GST or Udyam document",
                                     "Authorised signatory not available", "Document details did not match"],
        "Price / competition": ["Price too high", "Competitor offered cheaper plan", "Locked in with current provider"],
        "Install / fulfilment": ["Installation delayed beyond 21 days", "Site not feasible for fibre",
                                 "Customer cancelled before install", "First payment failed"],
        "Not a fit / undecided": ["Not interested on first call", "Only wanted a mobile plan", "Decided to wait"],
    }
    drop_groups = [{"group": g, "count": int(drops.reindex(rs).fillna(0).sum())} for g, rs in buckets.items()]

    # Segment economics
    seg = []
    for name, g in d.groupby("segment"):
        ga = a[a["segment"] == name]
        seg.append({
            "segment": name, "key": SEG_SHORT[name], "leads": int(len(g)), "share": _pct(len(g) / len(d)),
            "activation_rate": _pct(g["act"].mean()),
            "median_bundle": int(ga["monthly_bundle_value_inr"].median()) if len(ga) else 0,
            "churn_6m": _pct(ga["churn"].mean()) if len(ga) else 0,
            "cac_per_activation": int(g["acquisition_cost_inr"].sum() / max(1, g["act"].sum())),
            "payback_months": round(g["acquisition_cost_inr"].sum() / max(1, g["act"].sum()) / max(1, ga["monthly_bundle_value_inr"].median()), 1) if len(ga) else None,
        })

    # Channels
    ch = []
    for name, g in d.groupby("lead_source"):
        ga = a[a["lead_source"] == name]
        ch.append({"source": name, "leads": int(len(g)), "activation_rate": _pct(g["act"].mean()),
                   "cac_per_activation": int(g["acquisition_cost_inr"].sum() / max(1, g["act"].sum())),
                   "churn_6m": _pct(ga["churn"].mean()) if len(ga) else 0})

    # Status chasing -> churn
    a["calls_band"] = pd.cut(a["customer_follow_up_calls"], [-1, 1, 3, 99], labels=["0-1 calls", "2-3 calls", "4+ calls"])
    chase = [{"band": str(b), "customers": int(len(g)), "churn_6m": _pct(g["churn"].mean()), "nps": round(float(g["nps_score"].mean()), 1)}
             for b, g in a.groupby("calls_band", observed=True)]

    # GST status vs activation, and activations on non-active GSTINs
    reg = store.gstin["status"]
    d["gst_status"] = d["gstin"].map(reg).fillna("No GSTIN")
    gst = [{"status": s, "leads": int(len(g)), "activation_rate": _pct(g["act"].mean()), "activated": int(g["act"].sum())}
           for s, g in d.groupby("gst_status")]
    bad_gst_activated = int(d[d["act"] & d["gst_status"].isin(["Cancelled", "Suspended"])].shape[0])

    # Audit of what field sales actually sold
    violations = 0
    examples = []
    for r in a.itertuples():
        pids = [x.split("x")[0] for x in str(r.bundle_products).split(";")]
        gst_ok = r.has_gstin == "Y" and reg.get(r.gstin) == "Active"
        issues = audit_bundle(pids, city_tier=int(r.city_tier), employees=int(r.employee_count), sites=int(r.num_sites), gst_ok=gst_ok)
        if issues:
            violations += 1
            if len(examples) < 5:
                examples.append({"lead_id": r.lead_id, "issues": issues})

    # Language
    lang = [{"language": l, "leads": int(len(g)), "activation_rate": _pct(g["act"].mean())}
            for l, g in d.groupby("preferred_language")]

    total_cac = int(d["acquisition_cost_inr"].sum())
    wasted = int(d.loc[~d["act"], "acquisition_cost_inr"].sum())
    return {
        "headline": {
            "leads": int(len(d)), "activations": int(d["act"].sum()), "conversion": _pct(d["act"].mean()),
            "avg_days_to_activate": round(float(a["days_lead_to_activation"].mean()), 1),
            "avg_status_chases": round(float(a["customer_follow_up_calls"].mean()), 1),
            "cac_per_activation": int(total_cac / max(1, d["act"].sum())),
            "total_acquisition_spend": total_cac, "spend_on_dropped_leads": wasted,
            "spend_on_dropped_share": _pct(wasted / total_cac),
            "churn_6m": _pct(a["churn"].mean()), "nps": round(float(a["nps_score"].mean()), 1),
            "gstin_activation": _pct(d.loc[d["has_gstin"] == "Y", "act"].mean()),
            "no_gstin_activation": _pct(d.loc[d["has_gstin"] == "N", "act"].mean()),
        },
        "funnel": funnel, "drop_groups": drop_groups, "segments": seg, "channels": ch,
        "status_chasing": chase, "gst_status": gst, "activated_on_inactive_gstin": bad_gst_activated,
        "rule_violations_in_sold_bundles": violations, "violation_examples": examples, "languages": lang,
    }
