"""The 12 specimen applicants: every planted problem must be caught, and
clean applicants must pass with no false alarms."""
from pathlib import Path

import pytest

import hashlib
import json

from app.kyc.service import _extract as extract  # live OCR, never the cache
from app.kyc.validator import validate

DOCS = Path(__file__).resolve().parent.parent / "data" / "kyc_documents"

EXPECTED = {
    "K01": {"gst.status", "udyam.number"},          # cancelled GSTIN, blank Udyam number
    "K02": set(),                                   # tilted scan, straightened automatically
    "K03": set(),
    "K04": {"gst_certificate.quality"},             # blurred GST certificate
    "K05": {"udyam_certificate.present"},           # Udyam certificate missing
    "K06": {"gst.format"},                          # GSTIN altered on the certificate
    "K07": {"gst.legal_name"},                      # legal name does not match registry
    "K08": set(),
    "K09": set(),
    "K10": set(),
    "K11": {"address.recent"},                      # address proof older than 90 days
    "K12": set(),
}


def run(applicant: str) -> dict:
    docs = {}
    for p in sorted(DOCS.glob(f"{applicant}_*.png")):
        r = extract(p.read_bytes(), p.stem[4:])
        docs[r["doc_type"]] = r
    return validate(docs).to_dict()


@pytest.mark.parametrize("applicant,expected", sorted(EXPECTED.items()))
def test_specimen(applicant, expected):
    rep = run(applicant)
    failed = {c["id"] for c in rep["checks"] if c["status"] == "fail"}
    assert failed == expected
    assert rep["verdict"] == ("needs_action" if expected else "verified")


def test_precomputed_cache_gives_expected_verdicts():
    """data/ocr_cache.json (used to serve the specimens instantly) must lead to
    exactly the same KYC verdicts as live OCR. Raw OCR text can differ slightly
    between Tesseract versions, so we compare outcomes, not raw strings."""
    cache = json.loads((DOCS.parent / "ocr_cache.json").read_text(encoding="utf-8"))
    assert len(cache) == 47
    for applicant, expected in EXPECTED.items():
        docs = {}
        for p in sorted(DOCS.glob(f"{applicant}_*.png")):
            r = cache[hashlib.sha256(p.read_bytes()).hexdigest() + ":" + p.stem[4:]]
            docs[r["doc_type"]] = r
        rep = validate(docs).to_dict()
        assert {c["id"] for c in rep["checks"] if c["status"] == "fail"} == expected, applicant
