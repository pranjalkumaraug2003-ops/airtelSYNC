"""Orders, tracker events and consent records (SQLite via SQLModel)."""
from __future__ import annotations

import datetime as dt
import secrets

from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine

from app.config import get_settings

STAGES = [
    ("placed", "Order placed", "We have your order and one monthly price."),
    ("kyc_verified", "KYC verified", "Documents checked automatically."),
    ("scheduled", "Installation scheduled", "Engineer visit booked for your preferred slot."),
    ("installing", "Engineer on site", "Installation in progress."),
    ("activated", "All services active", "Everything is live on one bill."),
]


def _code() -> str:
    return "UD-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


class Order(SQLModel, table=True):
    id: str = Field(default_factory=_code, primary_key=True)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    business_name: str
    segment: str
    city: str | None = None
    language: str = "en"
    contact_phone_masked: str | None = None
    items: list = Field(default_factory=list, sa_column=Column(JSON))
    monthly_total: int
    one_time_setup: int
    contract_months: int
    expected_activation_days: int
    kyc_verdict: str = "pending"
    stage_index: int = 0
    channel: str = "self-serve"  # self-serve | partner-assisted | field-assisted
    partner_code: str | None = None
    preferred_slot: str | None = None


class OrderEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    order_id: str = Field(index=True)
    at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    stage: str
    message: str
    notified_via: str = "whatsapp"


class Consent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    purposes: list = Field(default_factory=list, sa_column=Column(JSON))
    notice_version: str = "v1"
    language: str = "en"
    granted_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    withdrawn_at: dt.datetime | None = None


_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().db_url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(_engine)
    return _engine


def session() -> Session:
    return Session(engine())
