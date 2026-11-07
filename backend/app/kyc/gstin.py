"""GSTIN structure, checksum and OCR-error repair.

GSTIN layout (15 chars):
  0-1   state code (digits)
  2-11  PAN of the business: 5 letters, 4 digits, 1 letter
          (char 5 is the PAN "entity type"; this dataset always uses X)
  12    entity number (1-9 or A-Z)
  13    always 'Z'
  14    checksum (mod-36 Luhn-style over the first 14 chars)

OCR often confuses look-alike characters (0/O, 1/I, 2/Z, 5/S, 8/B). Because we
know which positions must be letters and which digits, we can undo those slips.
We never "repair" a character that is not a look-alike, so a number someone
actually edited (for example 5 changed to 8) still fails the checksum.
"""
from __future__ import annotations

import itertools
import re

CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

TO_DIGIT = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "T": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}
TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}
AMBIGUOUS = {"0": "O", "O": "0", "1": "I", "I": "1", "2": "Z", "Z": "2", "5": "S", "S": "5", "8": "B", "B": "8"}

STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "32": "Kerala", "33": "Tamil Nadu", "36": "Telangana",
    "37": "Andhra Pradesh",
}

DIGIT_POS = {0, 1, 7, 8, 9, 10}
LETTER_POS = {2, 3, 4, 5, 6, 11}


def checksum_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = CHARSET.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return CHARSET[(36 - total % 36) % 36]


def is_valid(gstin: str) -> bool:
    gstin = (gstin or "").upper()
    if not GSTIN_RE.match(gstin):
        return False
    return checksum_char(gstin[:14]) == gstin[14]


def format_errors(gstin: str) -> list[str]:
    """Human-readable reasons a GSTIN is invalid (empty list = valid)."""
    g = (gstin or "").upper()
    errs: list[str] = []
    if len(g) != 15:
        return [f"GSTIN must be 15 characters (got {len(g)})"]
    if g[:2] not in STATE_CODES:
        errs.append(f"Unknown state code {g[:2]}")
    if not GSTIN_RE.match(g):
        errs.append("Characters are not in the GSTIN pattern")
    elif checksum_char(g[:14]) != g[14]:
        errs.append("Checksum digit does not match (number mistyped or altered)")
    return errs


def _shape(raw: str) -> str:
    """Force each position into its expected class using look-alike maps only."""
    out = []
    for i, ch in enumerate(raw):
        if i in DIGIT_POS and not ch.isdigit():
            ch = TO_DIGIT.get(ch, ch)
        elif i in LETTER_POS and ch.isdigit():
            ch = TO_LETTER.get(ch, ch)
        elif i == 13:
            ch = "Z" if ch in ("Z", "2") else ch
        out.append(ch)
    return "".join(out)


# Letters Tesseract mixes up with each other in this monospace font.
LETTER_CONFUSIONS = {"I": "JLT", "J": "I", "L": "I", "T": "I", "O": "DQ", "D": "O", "Q": "O", "V": "Y", "Y": "V", "C": "G", "G": "C"}


def repair(raw: str, exists=None) -> tuple[str, bool]:
    """Best-effort clean-up of an OCR'd GSTIN.

    Returns (gstin, repaired_ok). repaired_ok is True only when the result
    passes the checksum using look-alike substitutions alone. A letter-for-
    letter swap (I vs J) is accepted only if `exists(candidate)` confirms the
    number is in the registry, so a random checksum collision can never turn
    an edited number into a "valid" one.
    """
    fixed, ok = _repair_lookalikes(raw)
    if ok or exists is None or len(fixed) != 15:
        return fixed, ok
    for i in sorted(LETTER_POS):
        for alt in LETTER_CONFUSIONS.get(fixed[i], ""):
            cand = fixed[:i] + alt + fixed[i + 1:]
            if is_valid(cand) and exists(cand):
                return cand, True
    return fixed, False


def _repair_lookalikes(raw: str) -> tuple[str, bool]:
    s = re.sub(r"[^A-Z0-9]", "", (raw or "").upper())
    candidates = [s] if len(s) == 15 else []
    if len(s) == 16:  # one stray character picked up by OCR
        candidates = [s[:i] + s[i + 1:] for i in range(16)]
    elif len(s) > 16:
        candidates = [s[:15]]
    for cand in candidates:
        shaped = _shape(cand)
        if is_valid(shaped):
            return shaped, True
        # try flipping ambiguous characters (at most 2 at a time)
        amb = [i for i, ch in enumerate(shaped) if ch in AMBIGUOUS and i not in DIGIT_POS | LETTER_POS | {13}]
        for r in (1, 2):
            for combo in itertools.combinations(amb, r):
                t = list(shaped)
                for i in combo:
                    t[i] = AMBIGUOUS[t[i]]
                t = "".join(t)
                if is_valid(t):
                    return t, True
    best = _shape(candidates[0]) if candidates else s
    return best, False


def mask(gstin: str | None) -> str:
    """Show state code and last 3 chars only, e.g. 37XXXXXXXXXX1ZS -> 37••••••••••1ZS."""
    if not gstin or len(gstin) < 6:
        return gstin or ""
    return gstin[:2] + "•" * (len(gstin) - 5) + gstin[-3:]
