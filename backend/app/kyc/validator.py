"""Smart KYC rules: every check is explicit, explainable and testable.

Input: the fields extracted from up to four documents (plus the GSTIN the
owner typed, if any). Output: a list of checks, each pass / warn / fail with a
plain-language reason and the fix the owner should make.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import asdict, dataclass, field

from rapidfuzz import fuzz

from app.config import get_settings
from app.data_store import get_store
from app.kyc import gstin as G
from app.kyc.parsers import DOC_LABELS, DOC_TYPES

ADDRESS_PROOF_MAX_DAYS = 90
NAME_MATCH = 92  # fuzzy score (0-100) needed to call two names the same


@dataclass
class Check:
    id: str
    doc: str
    title: str
    status: str  # pass | warn | fail
    detail: str
    fix: str = ""


@dataclass
class KycReport:
    verdict: str  # verified | needs_action
    business_name: str | None
    gstin_masked: str | None
    gst_status: str | None
    checks: list[Check] = field(default_factory=list)
    blocks_gst_products: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["summary"] = {s: sum(1 for c in self.checks if c.status == s) for s in ("pass", "warn", "fail")}
        return d


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def same_name(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return fuzz.token_sort_ratio(_norm(a), _norm(b)) >= NAME_MATCH


def _state_from_address(addr: str | None) -> str | None:
    if not addr:
        return None
    flat = re.sub(r"\s", "", addr.lower())
    for state in G.STATE_CODES.values():
        if re.sub(r"\s", "", state.lower()) in flat:
            return state
    return None


def _diff(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))


def _registry_near_match(doc_gstin: str, trade_name: str | None) -> str | None:
    """Registry GSTIN for the same business that differs by 1-2 characters."""
    if not trade_name:
        return None
    reg = get_store().gstin
    same = reg[reg["trade_name"].str.lower() == trade_name.lower()]
    near = [g for g in same.index if g[:2] == doc_gstin[:2] and _diff(g, doc_gstin) <= 2]
    return near[0] if len(near) == 1 else None


def validate(docs: dict[str, dict], declared_gstin: str | None = None) -> KycReport:
    """docs maps doc_type -> {"fields": {...}, "quality": {...}} for uploaded docs."""
    store = get_store()
    today = get_settings().reference_date
    checks: list[Check] = []
    add = checks.append

    # 1. Presence and image quality -------------------------------------
    for dt_ in DOC_TYPES:
        label = DOC_LABELS[dt_]
        if dt_ not in docs:
            add(Check(f"{dt_}.present", dt_, f"{label} uploaded", "fail",
                      f"{label} is missing.", f"Upload a photo or PDF of your {label.lower()}."))
            continue
        q = docs[dt_].get("quality", {})
        if q.get("is_blurry"):
            add(Check(f"{dt_}.quality", dt_, f"{label}: photo readable", "fail",
                      f"The {label} photo is too blurred to read (sharpness {q.get('blur_score')}).",
                      "Retake the photo in good light, holding the phone steady."))
        elif abs(q.get("skew_angle", 0)) >= 1:
            add(Check(f"{dt_}.quality", dt_, f"{label}: photo readable", "pass",
                      f"Photo was tilted {abs(q['skew_angle']):.1f} degrees; straightened automatically."))
        else:
            add(Check(f"{dt_}.quality", dt_, f"{label}: photo readable", "pass", "Clear photo."))

    readable = {k: v for k, v in docs.items() if not v.get("quality", {}).get("is_blurry")}
    gst_f = readable.get("gst_certificate", {}).get("fields", {})
    udy_f = readable.get("udyam_certificate", {}).get("fields", {})
    sig_f = readable.get("signatory_id", {}).get("fields", {})
    adr_f = readable.get("address_proof", {}).get("fields", {})

    # 2. GST ---------------------------------------------------------------
    gst_rec = None
    doc_gstin = gst_f.get("gstin")
    if gst_f:
        if not doc_gstin:
            add(Check("gst.format", "gst_certificate", "GSTIN is valid", "fail",
                      "Could not find a GSTIN on the certificate.", "Upload the full first page of the GST certificate."))
        else:
            errs = G.format_errors(doc_gstin)
            if errs:
                detail = f"GSTIN {G.mask(doc_gstin)} on the certificate is not a valid number: {errs[0]}."
                near = _registry_near_match(doc_gstin, gst_f.get("trade_name"))
                if near:
                    detail += (f" The GST registry holds {G.mask(near)} for '{gst_f.get('trade_name')}'; the certificate"
                               f" differs by {_diff(near, doc_gstin)} character(s), a sign the document was edited.")
                add(Check("gst.format", "gst_certificate", "GSTIN is valid", "fail", detail,
                          "Upload the original certificate, or type your GSTIN so we can verify it directly."))
            else:
                add(Check("gst.format", "gst_certificate", "GSTIN is valid", "pass", "Format and checksum are correct."))
                gst_rec = store.gstin_record(doc_gstin)
                if not gst_rec:
                    add(Check("gst.registry", "gst_certificate", "GSTIN found in GST registry", "fail",
                              "This GSTIN is not in the GST registry.", "Type your GSTIN to look it up, or contact support."))

    # The owner may also have typed a GSTIN (instant lookup step).
    if declared_gstin:
        declared_gstin = declared_gstin.strip().upper()
        if doc_gstin and doc_gstin != declared_gstin:
            add(Check("gst.matches_declared", "gst_certificate", "Certificate matches the GSTIN you entered", "fail",
                      f"Certificate shows {G.mask(doc_gstin)} but you entered {G.mask(declared_gstin)}.",
                      "Upload the certificate for the GSTIN you entered."))
        if not gst_rec:
            gst_rec = store.gstin_record(declared_gstin)

    gst_status = None
    if gst_rec:
        gst_status = gst_rec["status"]
        if gst_status == "Active":
            add(Check("gst.status", "gst_certificate", "GST registration is active", "pass", "Registry status: Active."))
        else:
            add(Check("gst.status", "gst_certificate", "GST registration is active", "fail",
                      f"GST registry shows this registration as {gst_status}. Products that need a valid GSTIN cannot be sold.",
                      "Reactivate the GST registration, or continue with products that do not need GST."))
        if gst_f:
            if same_name(gst_f.get("legal_name"), gst_rec["legal_name"]):
                add(Check("gst.legal_name", "gst_certificate", "Legal name matches registry", "pass", "Matches GST registry."))
            else:
                add(Check("gst.legal_name", "gst_certificate", "Legal name matches registry", "fail",
                          f"Certificate says '{gst_f.get('legal_name')}', registry says '{gst_rec['legal_name']}'.",
                          "Upload an unedited copy of the certificate; details must match the registry."))
            if gst_f.get("trade_name") and not same_name(gst_f["trade_name"], gst_rec["trade_name"]):
                add(Check("gst.trade_name", "gst_certificate", "Trade name matches registry", "fail",
                          f"Certificate says '{gst_f['trade_name']}', registry says '{gst_rec['trade_name']}'.",
                          "Upload an unedited copy of the certificate."))
        state = G.STATE_CODES.get(gst_rec["gstin"][:2])
        if state and state != gst_rec.get("state"):
            add(Check("gst.state", "gst_certificate", "GSTIN state code matches address", "fail",
                      f"GSTIN state code is {state} but registered address is in {gst_rec.get('state')}.", "Contact support."))

    business = (gst_rec or {}).get("trade_name") or gst_f.get("trade_name") or udy_f.get("enterprise_name") or sig_f.get("business")

    # 3. Udyam -------------------------------------------------------------
    if udy_f:
        num = udy_f.get("udyam_number")
        if not num:
            add(Check("udyam.number", "udyam_certificate", "Udyam number present", "fail",
                      "The Udyam certificate has no registration number on it.",
                      "Download a fresh certificate from the Udyam portal, or type your Udyam number."))
        else:
            rec = get_store().udyam_record(num)
            if not rec:
                add(Check("udyam.registry", "udyam_certificate", "Udyam number found in registry", "fail",
                          f"{num} is not in the Udyam registry.", "Check the number on the Udyam portal."))
            elif not same_name(rec["enterprise_name"], business or udy_f.get("enterprise_name")):
                add(Check("udyam.registry", "udyam_certificate", "Udyam record matches business", "fail",
                          f"Udyam registry lists '{rec['enterprise_name']}', not '{business}'.", "Upload the Udyam certificate of this business."))
            else:
                add(Check("udyam.registry", "udyam_certificate", "Udyam number found in registry", "pass",
                          f"Registered as a {rec['enterprise_type']} enterprise in {rec['city']}."))

    # 4. Signatory ID ------------------------------------------------------
    if sig_f:
        vt = sig_f.get("valid_till")
        if vt and dt.date.fromisoformat(vt) < today:
            add(Check("id.validity", "signatory_id", "ID is not expired", "fail",
                      f"Signatory ID expired on {vt}.", "Upload a current ID."))
        elif vt:
            add(Check("id.validity", "signatory_id", "ID is not expired", "pass", f"Valid till {vt}."))
        if business and sig_f.get("business") and not same_name(sig_f["business"], business):
            add(Check("id.business", "signatory_id", "ID is for this business", "fail",
                      f"ID is issued for '{sig_f['business']}', not '{business}'.", "Upload the ID of a signatory of this business."))
        constitution = (gst_rec or {}).get("constitution") or gst_f.get("constitution") or ""
        legal = (gst_rec or {}).get("legal_name") or gst_f.get("legal_name") or ""
        if "propriet" in constitution.lower() and sig_f.get("name"):
            if _norm(sig_f["name"]) in _norm(legal):
                add(Check("id.proprietor", "signatory_id", "Signatory is the proprietor", "pass", f"{sig_f['name']} is the registered proprietor."))
            else:
                add(Check("id.proprietor", "signatory_id", "Signatory is the proprietor", "warn",
                          f"{sig_f['name']} is not the proprietor named on the GST registration.",
                          "Add an authorisation letter from the proprietor (e-sign supported)."))

    # 5. Address proof -----------------------------------------------------
    if adr_f:
        bd = adr_f.get("bill_date")
        if bd:
            age = (today - dt.date.fromisoformat(bd)).days
            if age > ADDRESS_PROOF_MAX_DAYS:
                add(Check("address.recent", "address_proof", "Address proof is recent", "fail",
                          f"Bill is dated {bd}, {age} days old. It must be within {ADDRESS_PROOF_MAX_DAYS} days.",
                          "Upload a bill from the last 3 months."))
            else:
                add(Check("address.recent", "address_proof", "Address proof is recent", "pass", f"Bill dated {bd} ({age} days old)."))
        if business and adr_f.get("billed_to") and not same_name(adr_f["billed_to"], business):
            add(Check("address.name", "address_proof", "Bill is in the business name", "warn",
                      f"Bill is in the name of '{adr_f['billed_to']}'.", "Upload a bill in the business name, or a rent agreement."))
        reg_addr = (gst_rec or {}).get("principal_place_of_business") or gst_f.get("address")
        reg_pin = re.findall(r"\d{6}", (reg_addr or "").replace(" ", ""))
        if adr_f.get("pin") and reg_pin:
            if adr_f["pin"] == reg_pin[-1]:
                add(Check("address.matches_gst", "address_proof", "Address matches GST registration", "pass", f"PIN {adr_f['pin']} matches."))
            else:
                add(Check("address.matches_gst", "address_proof", "Address matches GST registration", "warn",
                          f"Bill PIN {adr_f['pin']} differs from GST address PIN {reg_pin[-1]}.",
                          "If this is a second branch, add it as a separate site."))

    failed = any(c.status == "fail" for c in checks)
    return KycReport(
        verdict="needs_action" if failed else "verified",
        business_name=business,
        gstin_masked=G.mask(doc_gstin or (gst_rec or {}).get("gstin")),
        gst_status=gst_status,
        checks=checks,
        blocks_gst_products=gst_status not in (None, "Active") or not gst_rec,
    )
