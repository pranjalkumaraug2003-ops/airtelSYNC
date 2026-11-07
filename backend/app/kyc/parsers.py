"""Turn OCR text into structured fields for each KYC document type."""
from __future__ import annotations

import re

DOC_TYPES = ("gst_certificate", "udyam_certificate", "signatory_id", "address_proof")

DOC_LABELS = {
    "gst_certificate": "GST registration certificate",
    "udyam_certificate": "Udyam registration certificate",
    "signatory_id": "Authorised signatory ID",
    "address_proof": "Address proof (utility bill)",
}


def classify(text: str) -> str | None:
    t = text.lower()
    if "gst registration" in t or "gstin" in t:
        return "gst_certificate"
    if "udyam" in t:
        return "udyam_certificate"
    if "signatory" in t or "valid till" in t:
        return "signatory_id"
    if "electricity" in t or "bill date" in t or "billed to" in t or "consumer no" in t:
        return "address_proof"
    return None


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _after(lines: list[str], label: str, next_line: bool = False) -> str:
    """Value on the same line after `label`, or on the next line."""
    lab = label.lower()
    for i, ln in enumerate(lines):
        if ln.lower().startswith(lab):
            rest = ln[len(label):].strip(" :.-")
            if rest:
                return rest
            if next_line and i + 1 < len(lines):
                return lines[i + 1].strip()
            return ""
    return ""


def _date(s: str) -> str | None:
    m = re.search(r"(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})", s or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _pin(s: str) -> str | None:
    m = re.findall(r"(?<!\d)(\d{6})(?!\d)", (s or "").replace(" ", ""))
    return m[-1] if m else None


def _address(lines: list[str], first_label: str, stop_labels: tuple[str, ...]) -> str:
    """Addresses wrap over two lines on these documents; join them back up."""
    out, grab = [], False
    for ln in lines:
        low = ln.lower()
        if low.startswith(first_label.lower()):
            grab = True
            out.append(ln[len(first_label):])
            continue
        if grab:
            if any(low.startswith(s.lower()) for s in stop_labels):
                break
            out.append(ln.replace("place of business", ""))
    joined = "".join(p.strip() if i == 0 else p.strip() for i, p in enumerate(out))
    # undo the hard wrap ("Andhra Pradesh" split as "A" / "ndhra Pradesh")
    joined = re.sub(r"\s+", " ", joined).strip(" :-")
    joined = re.sub(r"\s*-\s*-?\s*(\d)", r" - \1", joined)
    return joined


def parse_gst(text: str) -> dict:
    ls = _lines(text)
    raw_gstin = ""
    m = re.search(r"GSTIN\s*[:]?\s*([A-Z0-9 ]{13,20})", text)
    if m:
        raw_gstin = re.sub(r"\s", "", m.group(1))
    addr = _address(ls, "Address of principal", ("Date of liability", "Type of registration"))
    return {
        "gstin_raw": raw_gstin,
        "legal_name": _after(ls, "Legal name"),
        "trade_name": _after(ls, "Trade name"),
        "constitution": _after(ls, "Constitution"),
        "address": addr,
        "pin": _pin(addr),
        "date_of_liability": _date(_after(ls, "Date of liability")),
    }


def parse_udyam(text: str) -> dict:
    ls = _lines(text)
    m = re.search(r"UDYAM\s*-\s*([A-Z]{2})\s*-\s*(\d{2})\s*-\s*(\d{7})", text.upper())
    return {
        "udyam_number": f"UDYAM-{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "",
        "enterprise_name": _after(ls, "Enterprise name"),
        "major_activity": _after(ls, "Major activity"),
        "city": _after(ls, "City"),
        "state": _after(ls, "State"),
        "date_of_registration": _date(_after(ls, "Date of registration")),
    }


def parse_signatory(text: str) -> dict:
    ls = _lines(text)
    return {
        "name": _after(ls, "Name", next_line=True),
        "designation": _after(ls, "Designation", next_line=True),
        "business": _after(ls, "For business", next_line=True),
        "id_number": _after(ls, "ID no.", next_line=True),
        "valid_till": _date(_after(ls, "Valid till", next_line=True)),
    }


def parse_address(text: str) -> dict:
    ls = _lines(text)
    addr = _address(ls, "Supply address", ("Bill date", "Units consumed"))
    return {
        "billed_to": _after(ls, "Billed to"),
        "address": addr,
        "pin": _pin(addr),
        "bill_date": _date(_after(ls, "Bill date")),
        "consumer_no": _after(ls, "Consumer no."),
    }


PARSERS = {
    "gst_certificate": parse_gst,
    "udyam_certificate": parse_udyam,
    "signatory_id": parse_signatory,
    "address_proof": parse_address,
}
