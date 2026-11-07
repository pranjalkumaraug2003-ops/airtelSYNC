"""Short-lived, in-memory store for KYC sessions.

DPDP choices made here:
  * purpose limitation: data is kept only for the KYC purpose it was given for;
  * data minimisation: we never write images to disk, only the extracted
    fields, and those are masked before they reach the browser or the logs;
  * storage limitation: everything expires after `upload_retention_minutes`.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

from app.config import get_settings


@dataclass
class KycSession:
    session_id: str
    consent_id: int | None
    created: float = field(default_factory=time.time)
    docs: dict = field(default_factory=dict)  # doc_type -> extract() result
    declared_gstin: str | None = None


_lock = threading.Lock()
_sessions: dict[str, KycSession] = {}


def _ttl() -> int:
    return get_settings().upload_retention_minutes * 60


def purge_expired() -> int:
    now = time.time()
    with _lock:
        dead = [k for k, v in _sessions.items() if now - v.created > _ttl()]
        for k in dead:
            del _sessions[k]
    return len(dead)


def get(session_id: str) -> KycSession | None:
    purge_expired()
    return _sessions.get(session_id)


def put(s: KycSession) -> None:
    with _lock:
        _sessions[s.session_id] = s


def delete(session_id: str) -> bool:
    with _lock:
        return _sessions.pop(session_id, None) is not None


def mask_text(value: str | None, keep_start: int = 2, keep_end: int = 3) -> str:
    if not value:
        return ""
    if len(value) <= keep_start + keep_end:
        return "•" * len(value)
    return value[:keep_start] + "•" * (len(value) - keep_start - keep_end) + value[-keep_end:]


def mask_fields(fields: dict) -> dict:
    """Mask identifiers before sending extracted fields to the browser."""
    out = {}
    for k, v in fields.items():
        if not isinstance(v, str):
            out[k] = v
        elif k in ("gstin", "gstin_raw"):
            out[k] = mask_text(v)
        elif k == "udyam_number":
            out[k] = re.sub(r"(\d{3})\d{4}$", r"\1••••", v)
        elif k in ("id_number", "consumer_no"):
            out[k] = mask_text(v, 0, 4)
        else:
            out[k] = v
    return out
