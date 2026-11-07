"""Catalogue eligibility rules, applied exactly as the product catalogue states.

A product can be sold only if:
  * the city tier is one it is sold in,
  * the business meets its minimum employees and minimum sites,
  * it has a valid, active GSTIN when the product requires one,
  * the bundle contains at least one product from its `requires_one_of` list.
"""
from __future__ import annotations

from app.data_store import Product, get_store


def blocking_reasons(p: Product, *, city_tier: int | None, employees: int | None,
                     sites: int | None, gst_ok: bool) -> list[tuple[str, str]]:
    """(reason, how to unlock) pairs; empty list means eligible (dependency checked separately)."""
    out: list[tuple[str, str]] = []
    if city_tier is not None and city_tier not in p.city_tiers:
        tiers = " and ".join(f"tier {t}" for t in p.city_tiers)
        out.append((f"Only available in {tiers} cities", "Not available in your city yet"))
    if employees is not None and employees < p.min_employees:
        out.append((f"Needs at least {p.min_employees} employees", "Available as your team grows"))
    if sites is not None and sites < p.min_sites:
        out.append((f"Needs at least {p.min_sites} sites", "Available when you add more locations"))
    if p.requires_gstin and not gst_ok:
        out.append(("Needs an active GST registration", "Add an active GSTIN to unlock this"))
    return out


def dependency_satisfied(p: Product, chosen_ids: set[str]) -> bool:
    return not p.requires_one_of or bool(set(p.requires_one_of) & chosen_ids)


def audit_bundle(product_ids: list[str], *, city_tier: int, employees: int, sites: int, gst_ok: bool) -> list[str]:
    """Return rule violations for an existing bundle (used to audit past sales)."""
    store = get_store()
    ids = set(product_ids)
    issues = []
    for pid in product_ids:
        p = store.products[pid]
        for reason, _ in blocking_reasons(p, city_tier=city_tier, employees=employees, sites=sites, gst_ok=gst_ok):
            issues.append(f"{pid}: {reason}")
        if not dependency_satisfied(p, ids):
            issues.append(f"{pid}: needs one of {', '.join(p.requires_one_of)}")
    return issues
