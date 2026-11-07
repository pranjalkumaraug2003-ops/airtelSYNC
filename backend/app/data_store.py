"""Loads the case CSVs once and serves them to every module."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from app.config import get_settings


@dataclass(frozen=True)
class Product:
    product_id: str
    category: str
    name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup_fee: int
    min_contract_months: int
    city_tiers: tuple[int, ...]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple[str, ...]
    install_days: int
    target_segments: tuple[str, ...]


class DataStore:
    def __init__(self) -> None:
        d = get_settings().data_dir
        cat = pd.read_csv(d / "product_catalogue.csv")
        self.products: dict[str, Product] = {}
        for r in cat.itertuples(index=False):
            self.products[r.product_id] = Product(
                product_id=r.product_id,
                category=r.category,
                name=r.product_name,
                description=r.description,
                unit=r.unit,
                price_min=int(r.price_min_inr_per_month),
                price_max=int(r.price_max_inr_per_month),
                setup_fee=int(r.one_time_setup_inr),
                min_contract_months=int(r.min_contract_months),
                city_tiers=tuple(int(x) for x in str(r.available_city_tiers).split(";")),
                min_employees=int(r.min_employees),
                min_sites=int(r.min_sites),
                requires_gstin=str(r.requires_gstin).strip().upper() == "Y",
                requires_one_of=tuple(str(r.requires_one_of).split("|")) if isinstance(r.requires_one_of, str) else (),
                install_days=int(r.typical_install_days),
                target_segments=tuple(str(r.target_segments).split(";")),
            )
        self.gstin = pd.read_csv(d / "mock_gstin_registry.csv", dtype=str).set_index("gstin")
        self.udyam = pd.read_csv(d / "mock_udyam_registry.csv", dtype=str).set_index("udyam_number")
        self.leads = pd.read_csv(d / "smb_leads.csv")
        self.kyc_dir = d / "kyc_documents"

    def gstin_record(self, gstin: str) -> dict | None:
        if gstin in self.gstin.index:
            rec = self.gstin.loc[gstin].to_dict()
            rec["gstin"] = gstin
            return rec
        return None

    def udyam_record(self, number: str) -> dict | None:
        if number in self.udyam.index:
            rec = self.udyam.loc[number].to_dict()
            rec["udyam_number"] = number
            return rec
        return None


@lru_cache
def get_store() -> DataStore:
    return DataStore()
