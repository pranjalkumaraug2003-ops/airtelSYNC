from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.advisor import engine
from app.data_store import get_store
from app.kyc import gstin as G
from app.rules.models import BusinessProfile, LineItem
from app.rules.recommender import recommend, requote

router = APIRouter(prefix="/api", tags=["advisor & quote"])


class StartIn(BaseModel):
    language: str = "en"


class ChatIn(BaseModel):
    session_id: str
    message: str
    show_plan: bool = False


class RequoteIn(BaseModel):
    profile: BusinessProfile
    items: list[LineItem]
    toggles: dict[str, bool] = {}
    quantities: dict[str, int] = {}


@router.post("/advisor/start")
def advisor_start(body: StartIn):
    return engine.start(body.language)


@router.post("/advisor/chat")
def advisor_chat(body: ChatIn):
    if not body.message.strip():
        raise HTTPException(400, "Empty message")
    try:
        return engine.chat(body.session_id, body.message[:1000], body.show_plan)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/quote/recommend")
def quote_recommend(profile: BusinessProfile):
    return recommend(profile)


@router.post("/quote/requote")
def quote_requote(body: RequoteIn):
    return requote(body.profile, body.items, body.toggles, body.quantities)


@router.get("/catalogue")
def catalogue():
    return [p.__dict__ for p in get_store().products.values()]


@router.get("/registry/gstin/{gstin}")
def gstin_lookup(gstin: str):
    g = gstin.strip().upper()
    errs = G.format_errors(g)
    if errs:
        return {"found": False, "valid_format": False, "errors": errs}
    rec = get_store().gstin_record(g)
    if not rec:
        return {"found": False, "valid_format": True, "errors": ["Not found in GST registry"]}
    return {"found": True, "valid_format": True, "gstin_masked": G.mask(g), "legal_name": rec["legal_name"],
            "trade_name": rec["trade_name"], "constitution": rec["constitution"], "state": rec["state"],
            "status": rec["status"], "registration_date": rec["registration_date"],
            "address": rec["principal_place_of_business"]}


@router.get("/registry/udyam/{number}")
def udyam_lookup(number: str):
    rec = get_store().udyam_record(number.strip().upper())
    if not rec:
        return {"found": False}
    return {"found": True, **{k: rec[k] for k in ("enterprise_name", "enterprise_type", "major_activity", "state", "city", "date_of_registration")}}
