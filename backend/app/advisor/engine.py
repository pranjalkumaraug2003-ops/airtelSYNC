"""Conversational advisor.

Division of labour (the core safety idea of the design):
  * Gemini understands the owner (any language, free text) and turns it into a
    structured BusinessProfile, then explains the result in plain words;
  * the deterministic rules engine picks products, quantities and prices.
The model never sees a chance to invent a price or an ineligible product: it
only receives the finished quote to explain.

If no Gemini key is set, or Gemini fails, a guided question flow with tap-to-
answer chips takes over, so the demo never breaks.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.config import get_settings
from app.data_store import get_store
from app.kyc import gstin as G
from app.rules.models import BusinessProfile, Recommendation
from app.rules.recommender import recommend

log = logging.getLogger("advisor")

LANGUAGES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "mr": "Marathi", "bn": "Bengali",
    "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi",
}

NEED_WORDS = {
    "internet": ["internet", "wifi", "wi-fi", "broadband", "fibre", "fiber", "net ", "इंटरनेट", "नेट", "upi"],
    "backup_internet": ["backup", "failover", "never down", "downtime", "बैकअप"],
    "phone_lines": ["sim", "phone line", "mobile number", "calling", "postpaid", "सिम", "फ़ोन", "फोन"],
    "whatsapp": ["whatsapp", "व्हाट्सएप"],
    "sms": ["sms", "bulk message"],
    "email": ["email", "e-mail", "mail", "gmail", "office suite", "ईमेल"],
    "cloud_backup": ["cloud backup", "data backup", "files backup", "storage"],
    "website": ["website", "domain", "google", "वेबसाइट"],
    "pos": ["pos", "billing", "invoice", "counter", "बिलिंग"],
    "endpoint_security": ["antivirus", "virus", "ransomware", "security", "सुरक्षा"],
    "firewall": ["firewall"],
    "guest_wifi": ["guest wifi", "customer wifi", "guest"],
    "cctv": ["cctv", "camera", "कैमरा", "सीसीटीवी"],
    "machine_iot": ["machine", "iot", "sensor", "मशीन"],
    "fleet": ["vehicle", "delivery van", "fleet", "truck", "गाड़ी"],
    "cloud_telephony": ["ivr", "call centre", "telephony", "sip"],
    "toll_free": ["toll free", "toll-free", "1800"],
    "static_ip": ["static ip", "fixed ip"],
}

QUESTIONS = {
    "en": {
        "business_type": ("Namaste! I'll help you pick the right internet, phones and digital tools for your business. What kind of business do you run?",
                          ["Kirana / retail shop", "Clinic", "CA / law office", "Coaching centre", "Restaurant chain", "Manufacturing unit"]),
        "employees": ("How many people work there, including you?", ["1-2", "3-5", "6-10", "11-25", "25+"]),
        "sites": ("How many locations (shops, branches, units) do you have?", ["1", "2", "3-5", "6-10"]),
        "city": ("Which city is the business in?", ["Delhi", "Mumbai", "Pune", "Jaipur", "Lucknow", "Kochi"]),
        "has_gstin": ("Is your business GST registered? You can type your GSTIN and I'll fetch the details instantly.", ["Yes", "No", "Type GSTIN"]),
        "needs": ("What do you need? Pick all that apply.", ["Internet", "Business SIMs", "WhatsApp for customers", "Email", "CCTV", "Billing / POS", "Backup internet", "Website"]),
    },
    "hi": {
        "business_type": ("नमस्ते! मैं आपके बिज़नेस के लिए सही इंटरनेट, फ़ोन और डिजिटल टूल चुनने में मदद करूँगा। आपका बिज़नेस क्या है?",
                          ["किराना / दुकान", "क्लिनिक", "CA / वकील ऑफिस", "कोचिंग सेंटर", "रेस्टोरेंट चेन", "मैन्युफैक्चरिंग यूनिट"]),
        "employees": ("आपको मिलाकर कितने लोग काम करते हैं?", ["1-2", "3-5", "6-10", "11-25", "25+"]),
        "sites": ("आपकी कितनी लोकेशन (दुकान, ब्रांच, यूनिट) हैं?", ["1", "2", "3-5", "6-10"]),
        "city": ("बिज़नेस किस शहर में है?", ["दिल्ली", "मुंबई", "पुणे", "जयपुर", "लखनऊ", "कोच्चि"]),
        "has_gstin": ("क्या आपका बिज़नेस GST रजिस्टर्ड है? GSTIN लिखें तो मैं तुरंत डिटेल निकाल दूँगा।", ["हाँ", "नहीं", "GSTIN लिखें"]),
        "needs": ("आपको क्या चाहिए? जो भी लागू हो चुनें।", ["इंटरनेट", "बिज़नेस सिम", "ग्राहकों के लिए WhatsApp", "ईमेल", "सीसीटीवी", "बिलिंग / POS", "बैकअप इंटरनेट", "वेबसाइट"]),
    },
}

HINDI_TYPES = {"किराना / दुकान": "kirana store", "क्लिनिक": "clinic", "CA / वकील ऑफिस": "CA / law office",
               "कोचिंग सेंटर": "coaching centre", "रेस्टोरेंट चेन": "restaurant chain", "मैन्युफैक्चरिंग यूनिट": "manufacturing unit",
               "Kirana / retail shop": "kirana store", "CA / law office": "CA / law office"}
HINDI_CITIES = {"दिल्ली": "Delhi", "मुंबई": "Mumbai", "पुणे": "Pune", "जयपुर": "Jaipur", "लखनऊ": "Lucknow", "कोच्चि": "Kochi"}
CHIP_NEEDS = {"internet": "internet", "इंटरनेट": "internet", "business sims": "phone_lines", "बिज़नेस सिम": "phone_lines",
              "whatsapp for customers": "whatsapp", "ग्राहकों के लिए whatsapp": "whatsapp", "email": "email", "ईमेल": "email",
              "cctv": "cctv", "सीसीटीवी": "cctv", "billing / pos": "pos", "बिलिंग / pos": "pos", "backup internet": "backup_internet",
              "बैकअप इंटरनेट": "backup_internet", "website": "website", "वेबसाइट": "website"}

REQUIRED = ["business_type", "employees", "sites", "city", "has_gstin", "needs"]


@dataclass
class AdvisorSession:
    id: str
    language: str = "en"
    profile: BusinessProfile = field(default_factory=BusinessProfile)
    history: list[dict] = field(default_factory=list)
    asked: str | None = None
    recommendation: Recommendation | None = None
    mode: str = "ai"
    gst_checked: str | None = None


_sessions: dict[str, AdvisorSession] = {}


def city_tiers() -> dict[str, int]:
    leads = get_store().leads
    return {c.lower(): int(t) for c, t in leads.groupby("city")["city_tier"].first().items()}


def missing_fields(p: BusinessProfile) -> list[str]:
    out = []
    for f in REQUIRED:
        v = getattr(p, f)
        if f == "has_gstin":
            if p.has_gstin is None and not p.gstin:
                out.append(f)
        elif f == "needs":
            if not p.needs:
                out.append(f)
        elif f == "city":
            if not p.city and p.city_tier is None:
                out.append(f)
        elif v in (None, ""):
            out.append(f)
    return out


def _apply_gstin(p: BusinessProfile, lang: str = "en") -> str | None:
    """Instant GSTIN lookup: fill name and city from the registry."""
    if not p.gstin:
        return None
    g = p.gstin.strip().upper()
    if G.format_errors(g):
        p.gstin = None
        return "That GSTIN doesn't look right (it fails the format check). Could you check it?"
    rec = get_store().gstin_record(g)
    if not rec:
        p.gstin = None
        return "I couldn't find that GSTIN in the GST registry. You can continue without it."
    p.gstin, p.has_gstin = g, rec["status"] == "Active"
    p.business_name = p.business_name or rec["trade_name"]
    if not p.city:
        m = re.search(r",\s*([A-Za-z ]+),\s*[A-Za-z ]+\s*-\s*\d{6}", rec["principal_place_of_business"])
        if m:
            p.city = m.group(1).strip()
    status = rec["status"]
    if lang == "hi":
        msg = f"{rec['trade_name']} ({rec['constitution']}) मिला, GST स्थिति: {status}।"
        if status != "Active":
            msg += " GST सक्रिय नहीं है, इसलिए GST वाले प्रोडक्ट अभी नहीं जोड़े जाएँगे।"
        return msg
    msg = f"Found {rec['trade_name']} ({rec['constitution']}), GST status: {status}."
    if status != "Active":
        msg += " Because it is not active, products that need GST will be held back until it is reactivated."
    return msg


def _normalise(p: BusinessProfile) -> None:
    if p.city and p.city_tier is None:
        p.city_tier = city_tiers().get(p.city.lower(), 2)  # unknown city: assume tier 2 (conservative)
    if p.sites is None and p.business_type and not any(k in p.business_type.lower() for k in ("chain", "branches", "outlets")):
        pass


def _first_int(text: str) -> int | None:
    m = re.search(r"\d+", text)
    if not m:
        return None
    n = int(m.group(0))
    return n


# ---------------------------------------------------------------- guided mode
def _guided_parse(s: AdvisorSession, text: str) -> None:
    p, t = s.profile, text.strip()
    low = t.lower()
    g = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", t.upper())
    if g:
        p.gstin = g.group(0)
    for need, words in NEED_WORDS.items():
        if any(w in f" {low} " for w in words) and need not in p.needs and s.asked == "needs":
            p.needs.append(need)
    for chip in [c.strip().lower() for c in re.split(r"[,;]", t)]:
        if chip in CHIP_NEEDS and CHIP_NEEDS[chip] not in p.needs:
            p.needs.append(CHIP_NEEDS[chip])
    if s.asked == "business_type":
        p.business_type = HINDI_TYPES.get(t, t)
        if any(k in low for k in ("chain", "restaurant chain", "रेस्टोरेंट चेन")):
            p.business_type = "restaurant chain"
    elif s.asked == "employees":
        n = _first_int(t)
        if n:
            p.employees = 30 if "25+" in t else n if "-" not in t else int(t.split("-")[1])
    elif s.asked == "sites":
        n = _first_int(t)
        if n:
            p.sites = int(t.split("-")[1]) if "-" in t else n
    elif s.asked == "city":
        p.city = HINDI_CITIES.get(t, t.title())
    elif s.asked == "has_gstin" and not g:
        if low in ("yes", "y", "haan", "ha", "हाँ", "हां"):
            p.has_gstin = True
        elif low in ("no", "n", "nahi", "नहीं"):
            p.has_gstin = False
    if s.asked == "needs" and not p.needs:
        p.needs = ["internet"]


# ------------------------------------------------------------------ AI mode
class ProfileUpdate(BaseModel):
    business_name: str | None = None
    business_type: str | None = None
    segment: str | None = Field(None, description="one of micro, prof, multi, mfg")
    employees: int | None = None
    sites: int | None = None
    city: str | None = None
    has_gstin: bool | None = None
    gstin: str | None = None
    current_internet: str | None = None
    current_monthly_spend: int | None = None
    fibre_available: bool | None = None
    needs: list[str] | None = None
    phone_lines: int | None = None
    email_users: int | None = None
    cameras: int | None = None
    pos_counters: int | None = None
    devices: int | None = None
    machines: int | None = None
    vehicles: int | None = None
    budget_monthly: int | None = None


class AdvisorTurn(BaseModel):
    profile_update: ProfileUpdate
    reply: str
    quick_replies: list[str] = Field(default_factory=list)
    wants_recommendation: bool = False


SYSTEM_PROMPT = """You are Udyam Saathi, a friendly onboarding advisor for Accel Business, helping Indian small business owners
(kirana shops, clinics, CA firms, coaching centres, restaurants, small factories) choose connectivity and digital tools.

Your job in each turn:
1. Read the owner's latest message and fill `profile_update` with anything new you learned (leave unknown fields null).
   Map their words to `needs` using ONLY these codes: {needs}.
   segment: micro (kirana, salon, pharmacy, small shop), prof (clinic, CA, law, coaching, agency office),
   multi (2+ outlets, restaurant chain, store chain), mfg (factory, workshop, manufacturing unit).
2. Write `reply`: at most 2 short sentences in {language}, warm and simple, no jargon. Ask for the most important
   missing detail (still missing: {missing}). Ask one thing at a time.
3. Offer 2-6 `quick_replies` the owner can tap, in {language}.
4. Set `wants_recommendation` true only when nothing important is missing or the owner asks to see a plan.
Never mention prices, product names or discounts: the system will calculate the plan. Never ask for Aadhaar, PAN,
bank or card numbers. If asked something unrelated, gently steer back.
Current profile (JSON): {profile}"""

EXPLAIN_PROMPT = """Explain this recommended plan to a small business owner in {language}, in at most 70 words, warm and plain.
Say why the main items fit their business, mention the single monthly price and the activation time exactly as given,
and if anything was held back, say why in one short clause. Use ONLY the numbers and product names in the JSON.
Plan JSON: {plan}"""


_client = None


def _gemini():
    """One shared client for the whole app. (google-genai closes a client once it
    is garbage-collected, so a throwaway client per call can fail mid-request.)"""
    global _client
    if _client is None:
        from google import genai  # imported lazily so tests run without the SDK configured
        _client = genai.Client(api_key=get_settings().gemini_api_key)
    return _client


def _contents(s: AdvisorSession, text: str):
    """Gemini wants the conversation to start with a user turn and to alternate
    roles, so drop leading model turns and merge consecutive same-role turns."""
    from google.genai import types
    turns: list[tuple[str, str]] = []
    for h in s.history[-12:] + [{"role": "user", "text": text}]:
        role = "user" if h["role"] == "user" else "model"
        if not turns and role == "model":
            continue
        if turns and turns[-1][0] == role:
            turns[-1] = (role, turns[-1][1] + "\n" + h["text"])
        else:
            turns.append((role, h["text"]))
    return [types.Content(role=r, parts=[types.Part(text=t)]) for r, t in turns]


def _ai_turn(s: AdvisorSession, text: str) -> AdvisorTurn:
    from google.genai import types
    st = get_settings()
    sys = SYSTEM_PROMPT.format(needs=", ".join(NEED_WORDS), language=LANGUAGES.get(s.language, "English"),
                               missing=", ".join(missing_fields(s.profile)) or "nothing",
                               profile=s.profile.model_dump_json(exclude_none=True))
    first_q = next((h["text"] for h in s.history if h["role"] == "model"), "")
    if first_q:
        sys += f"\nYou opened the chat by asking: {first_q}"
    contents = _contents(s, text)
    client = _gemini()
    try:
        # Preferred: Gemini enforces our JSON schema.
        resp = client.models.generate_content(
            model=st.gemini_model, contents=contents,
            config=types.GenerateContentConfig(system_instruction=sys, response_mime_type="application/json",
                                               response_schema=AdvisorTurn, temperature=0.3),
        )
    except Exception as e:  # some API versions reject parts of a Pydantic schema
        log.warning("Schema-enforced call failed (%s: %s); retrying with schema in the prompt", type(e).__name__, str(e)[:300])
        schema = json.dumps(AdvisorTurn.model_json_schema())
        resp = client.models.generate_content(
            model=st.gemini_model, contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=sys + "\nReply ONLY with a JSON object matching this JSON schema: " + schema,
                response_mime_type="application/json", temperature=0.3),
        )
    if isinstance(getattr(resp, "parsed", None), AdvisorTurn):
        return resp.parsed
    raw = (resp.text or "").strip()
    raw = raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw else raw
    return AdvisorTurn.model_validate_json(raw)


def _ai_explain(s: AdvisorSession, rec: Recommendation) -> str:
    from google.genai import types
    plan = {
        "business": rec.profile.business_name or rec.profile.business_type, "segment": rec.segment_label,
        "items": [{"name": i.name, "qty": i.quantity, "why": i.reason} for i in rec.quote.items if i.selected],
        "monthly_price_before_gst": rec.quote.monthly_total, "setup_one_time": rec.quote.one_time_setup,
        "activation_days": rec.quote.expected_activation_days, "contract_months": rec.quote.contract_months,
        "held_back": [{"name": e.name, "why": e.reason} for e in rec.quote.excluded],
    }
    resp = _gemini().models.generate_content(
        model=get_settings().gemini_model,
        contents=EXPLAIN_PROMPT.format(language=LANGUAGES.get(s.language, "English"), plan=json.dumps(plan, ensure_ascii=False)),
        config=types.GenerateContentConfig(temperature=0.4),
    )
    return (resp.text or "").strip()


def _template_explain(s: AdvisorSession, rec: Recommendation) -> str:
    q = rec.quote
    main = ", ".join(f"{i.name}{' x' + str(i.quantity) if i.quantity > 1 else ''}" for i in q.items if i.selected)
    if s.language == "hi":
        txt = f"आपके लिए प्लान: {main}। कुल ₹{q.monthly_total:,}/महीना + GST, लगभग {q.expected_activation_days} दिन में चालू।"
        if q.excluded:
            txt += " कुछ प्रोडक्ट अभी नहीं जोड़े गए: " + "; ".join(f"{e.name} ({e.reason})" for e in q.excluded) + "।"
        return txt
    txt = f"Here's your plan: {main}. One bill of Rs {q.monthly_total:,}/month + GST, live in about {q.expected_activation_days} days."
    if q.excluded:
        txt += " Held back for now: " + "; ".join(f"{e.name} ({e.reason.lower()})" for e in q.excluded) + "."
    return txt


def _merge(p: BusinessProfile, upd: ProfileUpdate) -> None:
    data = upd.model_dump(exclude_none=True)
    if "needs" in data:
        valid = [n for n in data.pop("needs") if n in NEED_WORDS]
        p.needs = list(dict.fromkeys(p.needs + valid))
    if data.get("segment") not in (None, "micro", "prof", "multi", "mfg"):
        data.pop("segment")
    for k, v in data.items():
        setattr(p, k, v)


# ------------------------------------------------------------------ public API
def start(language: str = "en") -> dict:
    s = AdvisorSession(id=uuid.uuid4().hex[:12], language=language if language in LANGUAGES else "en")
    s.mode = "ai" if get_settings().ai_enabled else "guided"
    _sessions[s.id] = s
    q, chips = QUESTIONS.get(s.language, QUESTIONS["en"])["business_type"]
    s.asked = "business_type"
    s.history.append({"role": "model", "text": q})
    return {"session_id": s.id, "mode": s.mode, "reply": q, "quick_replies": chips, "profile": s.profile, "missing": missing_fields(s.profile)}


def chat(session_id: str, text: str, show_plan: bool = False) -> dict:
    s = _sessions.get(session_id)
    if s is None:
        raise KeyError("Session expired; start again")
    notes: list[str] = []
    reply, chips, wants = "", [], show_plan
    if s.mode == "ai":
        try:
            turn = _ai_turn(s, text)
            _merge(s.profile, turn.profile_update)
            reply, chips, wants = turn.reply, turn.quick_replies, wants or turn.wants_recommendation
        except Exception as e:  # network, quota, bad JSON: fall back, never break the demo
            log.warning("Gemini turn failed, switching to guided mode: %s: %s", type(e).__name__, str(e)[:500])
            s.mode = "guided"
    if s.mode == "guided":
        _guided_parse(s, text)
    s.history.append({"role": "user", "text": text})

    if s.profile.gstin and s.profile.gstin != s.gst_checked:
        gst_msg = _apply_gstin(s.profile, s.language)
        s.gst_checked = s.profile.gstin
        if gst_msg:
            notes.append(gst_msg)
    _normalise(s.profile)
    missing = missing_fields(s.profile)

    rec = None
    if not missing or (wants and s.profile.business_type and s.profile.needs):
        rec = recommend(s.profile)
        s.recommendation = rec
        try:
            reply = _ai_explain(s, rec) if s.mode == "ai" else _template_explain(s, rec)
        except Exception as e:
            log.warning("Gemini explain failed: %s", e)
            reply = _template_explain(s, rec)
        chips = ["Customise add-ons", "Continue to KYC"] if s.language != "hi" else ["ऐड-ऑन बदलें", "KYC पर आगे बढ़ें"]
    elif s.mode == "guided" or not reply:
        s.asked = missing[0]
        q, chips = QUESTIONS.get(s.language, QUESTIONS["en"])[s.asked]
        reply = q
    if notes:
        reply = " ".join(notes) + " " + reply
    s.history.append({"role": "model", "text": reply})
    return {"session_id": s.id, "mode": s.mode, "reply": reply, "quick_replies": chips,
            "profile": s.profile, "missing": missing, "recommendation": rec}


def get_session(session_id: str) -> AdvisorSession | None:
    return _sessions.get(session_id)


def all_sessions() -> list[AdvisorSession]:
    return list(_sessions.values())
