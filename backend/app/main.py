"""Udyam Digital API (Team 2Pointers, DTU) for Airtel SYNC 2026, Digital Track."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.data_store import get_store
from app.orders.models import engine
from app.routers import advisor, kyc, orders, partner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_store()  # load CSVs once
    engine()     # create SQLite tables
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Udyam Digital API",
    version="1.0.0",
    description="Digital-first MSME acquisition and onboarding: advisor, quote, smart KYC, tracker, partner console.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    start = time.time()
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    # Log path and timing only: never bodies, so no personal data lands in logs.
    logging.getLogger("access").info("%s %s %s %.0fms", request.method, request.url.path, resp.status_code, (time.time() - start) * 1000)
    return resp


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    return {"ai_enabled": settings.ai_enabled, "model": settings.gemini_model if settings.ai_enabled else None,
            "reference_date": settings.reference_date.isoformat(),
            "languages": {"en": "English", "hi": "हिन्दी", "ta": "தமிழ்", "te": "తెలుగు", "mr": "मराठी",
                          "bn": "বাংলা", "gu": "ગુજરાતી", "kn": "ಕನ್ನಡ", "ml": "മലയാളം", "pa": "ਪੰਜਾਬੀ"}}


app.include_router(advisor.router)
app.include_router(kyc.router)
app.include_router(orders.router)
app.include_router(partner.router)
