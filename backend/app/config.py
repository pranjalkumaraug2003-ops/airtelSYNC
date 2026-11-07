"""Settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Tiny .env loader so local runs work without extra packages."""
    env = BASE_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Settings(BaseModel):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    allowed_origins: list[str] = ["http://localhost:3000"]
    data_dir: Path = BASE_DIR / "data"
    db_url: str = f"sqlite:///{BASE_DIR / 'udyam.db'}"
    # The case says to treat 2026-07-15 as "today" for date checks.
    reference_date: dt.date = dt.date(2026, 7, 15)
    upload_retention_minutes: int = 30
    gst_rate: float = 0.18

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    _load_dotenv()
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    ref = os.getenv("REFERENCE_DATE", "2026-07-15")
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        allowed_origins=[o.strip() for o in origins.split(",") if o.strip()],
        db_url=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'udyam.db'}"),
        reference_date=dt.date.fromisoformat(ref),
    )
