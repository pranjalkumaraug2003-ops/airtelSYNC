"""Document image pipeline: quality check, deskew, OCR.

Everything runs on our own server with OpenCV + Tesseract, so KYC images
never leave the backend (a deliberate DPDP choice: data minimisation).
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract

# Tesseract uses OpenMP threads by default. On small cloud instances with a
# fraction of a CPU these threads fight each other and OCR becomes ~50x slower,
# so we pin it to one thread (inherited by the tesseract subprocess).
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

# Find the Tesseract binary: TESSERACT_CMD env var, then PATH, then the
# default Windows install folder (so local runs work even if PATH is stale).
_TESS = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
if not _TESS and os.name == "nt":
    _win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    _TESS = _win if os.path.exists(_win) else None
if _TESS:
    pytesseract.pytesseract.tesseract_cmd = _TESS

# Variance of the Laplacian below this means the photo is too blurred to trust.
# Calibrated on the 47 specimen images: sharp scans score > 900, the planted
# blurred certificate scores < 60.
BLUR_THRESHOLD = 150.0


@dataclass
class OcrResult:
    text: str
    blur_score: float
    is_blurry: bool
    skew_angle: float  # degrees the image was rotated to straighten it


def _decode(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("File is not a readable image (use PNG or JPG)")
    return img


def blur_score(gray: np.ndarray) -> float:
    """Sharpness score: variance of the Laplacian on a fixed-width copy."""
    h, w = gray.shape
    scale = 1000 / max(w, 1)
    small = cv2.resize(gray, (1000, int(h * scale)))
    return float(cv2.Laplacian(small, cv2.CV_64F).var())


def estimate_skew(gray: np.ndarray) -> float:
    """Find the rotation that makes text lines most horizontal.

    Classic projection-profile method: rotate a small binarised copy through
    candidate angles and keep the one whose row sums vary the most (sharp
    peaks = straight lines of text).
    """
    h, w = gray.shape
    scale = 800 / max(w, 1)
    small = cv2.resize(gray, (800, int(h * scale)))
    _, bw = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    best_angle, best_score = 0.0, -1.0
    center = (bw.shape[1] // 2, bw.shape[0] // 2)
    for angle in np.arange(-12, 12.01, 0.5):
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rot = cv2.warpAffine(bw, m, (bw.shape[1], bw.shape[0]), flags=cv2.INTER_NEAREST)
        profile = rot.sum(axis=1).astype(np.float64)
        score = float(np.var(profile))
        if score > best_score:
            best_angle, best_score = float(angle), score
    return best_angle


def rotate(gray: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.25:
        return gray
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w // 2
    m[1, 2] += nh / 2 - h // 2
    return cv2.warpAffine(gray, m, (nw, nh), borderValue=255)


def ocr_text(gray: np.ndarray, psm: int = 3) -> str:
    # Tested on the 47 specimens: the straightened grayscale image with
    # Tesseract's automatic layout (psm 3) reads fields most accurately.
    return pytesseract.image_to_string(gray, config=f"--psm {psm}")


def run_ocr(image_bytes: bytes) -> tuple[OcrResult, np.ndarray]:
    gray = _decode(image_bytes)
    score = blur_score(gray)
    angle = estimate_skew(gray)
    straight = rotate(gray, angle)
    text = ocr_text(straight, 3)
    result = OcrResult(text=text, blur_score=round(score, 1), is_blurry=score < BLUR_THRESHOLD, skew_angle=angle)
    return result, straight
