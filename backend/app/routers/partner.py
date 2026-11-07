"""Back-office view for field sales and channel partners."""
import pandas as pd
from fastapi import APIRouter

from app.advisor import engine
from app.ml.insights import compute
from app.ml.propensity import call_list, get_model

router = APIRouter(prefix="/api", tags=["partner console & insights"])

SEG_NAME = {"micro": "Micro retail & services", "prof": "Professional offices",
            "multi": "Small multi-site businesses", "mfg": "Small manufacturers"}
LANG_NAME = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "mr": "Marathi", "bn": "Bengali",
             "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi"}


@router.get("/partner/call-list")
def partner_call_list(limit: int = 30):
    """Dropped Q2 leads most likely to convert, with the digital fix for why they dropped."""
    return {"model": get_model().summary(), "leads": call_list(limit)}


@router.get("/partner/advisor-leads")
def advisor_leads():
    """Owners who got a plan from the advisor but have not ordered yet: hand-off to a human."""
    out = []
    m = get_model()
    for s in engine.all_sessions():
        p = s.profile
        if not p.business_type:
            continue
        seg = p.segment or (s.recommendation.segment if s.recommendation else "micro")
        row = pd.DataFrame([{
            "lead_source": "Website form", "segment": SEG_NAME.get(seg, "Micro retail & services"),
            "preferred_language": LANG_NAME.get(s.language, "English"), "annual_turnover_band": "40 lakh - 1.5 cr",
            "current_internet": p.current_internet or "Mobile hotspot", "contact_role": "Owner",
            "city_tier": p.city_tier or 2, "employee_count": p.employees or 1, "num_sites": p.sites or 1,
            "has_gstin": "Y" if p.has_gstin else "N", "has_udyam": "N",
            "monthly_telecom_spend_inr": p.current_monthly_spend or 0, "products_of_interest": ";".join(p.needs) or "P01",
        }])
        out.append({
            "session_id": s.id, "business": p.business_name or p.business_type, "city": p.city,
            "language": LANG_NAME.get(s.language), "stage": "Plan shown" if s.recommendation else "Chatting",
            "monthly_value": s.recommendation.quote.monthly_total if s.recommendation else None,
            "missing": engine.missing_fields(p), "score": round(float(m.score(row)[0]), 3),
            "why": m.explain(row),
        })
    return sorted(out, key=lambda x: -x["score"])


@router.get("/insights")
def insights():
    return compute()


@router.get("/model")
def model_card():
    return get_model().summary()
