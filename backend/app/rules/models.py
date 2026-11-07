"""Shared request/response shapes for the advisor, quote and orders."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Segment = Literal["micro", "prof", "multi", "mfg"]

SEGMENT_LABELS = {
    "micro": "Micro retail & services",
    "prof": "Professional office",
    "multi": "Small multi-site business",
    "mfg": "Small manufacturer",
}

# Everything a small business might need. The advisor maps the owner's words
# onto these; the recommender maps these onto catalogue products.
Need = Literal[
    "internet", "backup_internet", "static_ip", "phone_lines", "whatsapp", "sms",
    "email", "cloud_backup", "website", "pos", "endpoint_security", "firewall",
    "guest_wifi", "cctv", "machine_iot", "fleet", "cloud_telephony", "toll_free", "sdwan",
]


class BusinessProfile(BaseModel):
    business_name: str | None = None
    business_type: str | None = Field(None, description="e.g. kirana, dental clinic, CA firm, restaurant chain")
    segment: Segment | None = None
    employees: int | None = Field(None, ge=1)
    sites: int | None = Field(None, ge=1)
    city: str | None = None
    city_tier: Literal[1, 2] | None = None
    has_gstin: bool | None = None
    gstin: str | None = None
    current_internet: str | None = None
    current_monthly_spend: int | None = None
    fibre_available: bool | None = None
    needs: list[Need] = Field(default_factory=list)
    phone_lines: int | None = None
    email_users: int | None = None
    cameras: int | None = None
    pos_counters: int | None = None
    devices: int | None = None
    machines: int | None = None
    vehicles: int | None = None
    budget_monthly: int | None = None
    language: str = "en"


class LineItem(BaseModel):
    product_id: str
    name: str
    category: str
    unit: str
    quantity: int
    unit_price: int
    monthly: int
    setup_fee: int
    min_contract_months: int
    install_days: int
    selected: bool = True
    core: bool = False  # core items cannot be toggled off (e.g. the primary connection)
    reason: str = ""
    auto_added_for: str | None = None  # product that required this one


class ExcludedItem(BaseModel):
    product_id: str
    name: str
    reason: str
    unlock: str = ""  # what the owner can do to get it


class Quote(BaseModel):
    items: list[LineItem]
    excluded: list[ExcludedItem] = Field(default_factory=list)
    monthly_total: int
    gst_amount: int
    monthly_total_with_gst: int
    one_time_setup: int
    contract_months: int
    expected_activation_days: int
    current_monthly_spend: int | None = None
    budget_monthly: int | None = None
    over_budget_by: int = 0
    notes: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    profile: BusinessProfile
    segment: Segment
    segment_label: str
    quote: Quote
    headline: str
