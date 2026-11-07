"""Glue: run OCR on each upload, parse fields, repair GSTIN, then validate."""
from __future__ import annotations

from app.data_store import get_store
from app.kyc import gstin as G
from app.kyc.ocr import ocr_text, run_ocr
from app.kyc.parsers import PARSERS, classify


def _in_registry(g: str) -> bool:
    return get_store().gstin_record(g) is not None


def extract(image_bytes: bytes, hinted_type: str | None = None) -> dict:
    """OCR one document image and return its type, fields and quality.

    hinted_type is the upload slot the owner used. A blurred photo cannot be
    classified from its text, so the slot tells us which document it was.
    """
    res, straight = run_ocr(image_bytes)
    detected = classify(res.text)
    doc_type = detected or hinted_type
    quality = {"blur_score": res.blur_score, "is_blurry": res.is_blurry, "skew_angle": res.skew_angle}
    out = {"doc_type": doc_type, "detected_type": detected, "fields": {}, "quality": quality}
    if doc_type is None or res.is_blurry:
        return out

    fields = PARSERS[doc_type](res.text)
    if doc_type == "gst_certificate":
        fixed, ok = G.repair(fields.get("gstin_raw", ""), _in_registry)
        if not ok:
            # Second opinion: other Tesseract layouts read monospace IDs differently.
            for psm in (4, 6):
                alt = PARSERS[doc_type](ocr_text(straight, psm)).get("gstin_raw", "")
                f2, ok2 = G.repair(alt, _in_registry)
                if ok2:
                    fixed, ok = f2, True
                    break
        fields["gstin"] = fixed
        fields["gstin_ocr_confident"] = ok
    out["fields"] = fields
    return out
