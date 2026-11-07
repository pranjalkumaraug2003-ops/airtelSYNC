import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import select

from app.config import get_settings
from app.data_store import get_store
from app.kyc.parsers import DOC_LABELS, DOC_TYPES
from app.kyc.service import extract
from app.kyc.validator import validate
from app.orders.models import Consent, session
from app.privacy import store as vault

router = APIRouter(prefix="/api/kyc", tags=["smart kyc"])

MAX_UPLOAD_BYTES = 6 * 1024 * 1024
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

PURPOSES = {
    "kyc_verification": "Check your business documents against the GST and Udyam registries",
    "service_activation": "Set up and activate the services you ordered",
    "order_updates": "Send order status updates on WhatsApp/SMS",
}

NOTICE = {
    "en": {
        "title": "Before you share documents",
        "points": [
            "We use your documents only to verify your business and activate your order.",
            "Photos are read on our own servers and deleted within {mins} minutes. They are never stored or sent to any AI service.",
            "We keep only what activation needs: business name, GSTIN, Udyam number and address. IDs are masked on screen.",
            "You can withdraw consent and delete your data at any time from this screen.",
            "Grievance officer: privacy@accelbusiness.example (Digital Personal Data Protection Act, 2023).",
        ],
    },
    "hi": {
        "title": "दस्तावेज़ देने से पहले",
        "points": [
            "हम आपके दस्तावेज़ सिर्फ़ बिज़नेस वेरिफ़िकेशन और सर्विस चालू करने के लिए इस्तेमाल करते हैं।",
            "फ़ोटो हमारे अपने सर्वर पर पढ़ी जाती हैं और {mins} मिनट में डिलीट हो जाती हैं। इन्हें किसी AI सर्विस को नहीं भेजा जाता।",
            "हम सिर्फ़ ज़रूरी जानकारी रखते हैं: बिज़नेस का नाम, GSTIN, उद्यम नंबर और पता। ID नंबर छिपे रहते हैं।",
            "आप कभी भी सहमति वापस लेकर अपना डेटा डिलीट कर सकते हैं।",
            "शिकायत अधिकारी: privacy@accelbusiness.example (डिजिटल पर्सनल डेटा प्रोटेक्शन एक्ट, 2023)।",
        ],
    },
}


class ConsentIn(BaseModel):
    language: str = "en"
    purposes: list[str] = list(PURPOSES)


class DeclareIn(BaseModel):
    gstin: str


@router.get("/notice")
def notice(lang: str = "en"):
    n = NOTICE.get(lang, NOTICE["en"])
    mins = get_settings().upload_retention_minutes
    return {"title": n["title"], "points": [p.format(mins=mins) for p in n["points"]], "purposes": PURPOSES,
            "required_documents": [{"type": t, "label": DOC_LABELS[t]} for t in DOC_TYPES]}


@router.post("/consent")
def give_consent(body: ConsentIn):
    if "kyc_verification" not in body.purposes:
        raise HTTPException(400, "KYC verification consent is required to check documents")
    sid = uuid.uuid4().hex
    with session() as db:
        c = Consent(session_id=sid, purposes=[p for p in body.purposes if p in PURPOSES], language=body.language)
        db.add(c)
        db.commit()
        db.refresh(c)
        cid = c.id
    vault.put(vault.KycSession(session_id=sid, consent_id=cid))
    return {"session_id": sid, "consent_id": cid, "expires_in_minutes": get_settings().upload_retention_minutes}


def _get(sid: str) -> vault.KycSession:
    s = vault.get(sid)
    if not s:
        raise HTTPException(404, "KYC session expired or consent withdrawn; please start again")
    return s


def _public(doc: dict) -> dict:
    return {"doc_type": doc["doc_type"], "detected_type": doc.get("detected_type"),
            "quality": doc["quality"], "fields": vault.mask_fields(doc["fields"])}


@router.post("/{sid}/upload")
async def upload(sid: str, doc_type: str = Form(...), file: UploadFile = File(...)):
    s = _get(sid)
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"doc_type must be one of {DOC_TYPES}")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Upload a PNG, JPG or WEBP photo")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 6 MB)")
    try:
        res = extract(data, doc_type)  # bytes stay in memory; never written to disk
    except ValueError as e:
        raise HTTPException(400, str(e))
    res["doc_type"] = doc_type
    s.docs[doc_type] = res
    out = _public(res)
    if res.get("detected_type") and res["detected_type"] != doc_type:
        out["warning"] = f"This looks like a {DOC_LABELS[res['detected_type']]}, not a {DOC_LABELS[doc_type]}."
    return out


@router.post("/{sid}/sample/{applicant}")
def load_sample(sid: str, applicant: str):
    """Demo helper: load a specimen applicant (K01-K12) from the case pack."""
    s = _get(sid)
    applicant = applicant.upper()
    files = sorted(get_store().kyc_dir.glob(f"{applicant}_*.png"))
    if not files:
        raise HTTPException(404, "Unknown specimen applicant")
    s.docs.clear()
    s.declared_gstin = None  # a sample is a fresh applicant
    for f in files:
        t = f.stem[4:]
        r = extract(f.read_bytes(), t)
        r["doc_type"] = t
        s.docs[t] = r
    return {"loaded": [_public(d) for d in s.docs.values()]}


@router.post("/{sid}/declare-gstin")
def declare(sid: str, body: DeclareIn):
    s = _get(sid)
    s.declared_gstin = body.gstin.strip().upper()
    return {"ok": True}


@router.get("/{sid}/report")
def report(sid: str):
    s = _get(sid)
    return validate(s.docs, s.declared_gstin).to_dict()


@router.delete("/{sid}")
def withdraw(sid: str):
    """Right to erasure: withdraw consent and delete everything for this session."""
    import datetime as dt
    deleted = vault.delete(sid)
    with session() as db:
        for c in db.exec(select(Consent).where(Consent.session_id == sid)).all():
            c.withdrawn_at = dt.datetime.now(dt.timezone.utc)
            db.add(c)
        db.commit()
    return {"deleted": deleted, "consent_withdrawn": True}
