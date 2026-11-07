"""Precompute OCR results for the specimen images into data/ocr_cache.json.

Run from the backend folder:  python scripts/build_ocr_cache.py
Re-run whenever the OCR pipeline or parsers change.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.kyc.service import _extract  # noqa: E402

docs = Path(__file__).resolve().parent.parent / "data" / "kyc_documents"
out = {}
for p in sorted(docs.glob("*.png")):
    data = p.read_bytes()
    hinted = p.stem[4:]
    out[hashlib.sha256(data).hexdigest() + ":" + hinted] = _extract(data, hinted)
    print("ok", p.name)
(docs.parent / "ocr_cache.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
print(len(out), "entries written")
