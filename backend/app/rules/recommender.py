"""Deterministic bundle builder.

The AI advisor only collects the profile and explains the result. Which
products are offered, at what quantity and price, is decided here by plain
rules over the catalogue, so a recommendation can never break eligibility
or invent a price.
"""
from __future__ import annotations

import re

from app.config import get_settings
from app.data_store import Product, get_store
from app.rules.eligibility import blocking_reasons, dependency_satisfied
from app.rules.models import (SEGMENT_LABELS, BusinessProfile, ExcludedItem,
                              LineItem, Quote, Recommendation)

SEGMENT_KEYWORDS = {
    "mfg": ["manufactur", "factory", "unit", "workshop", "textile", "auto part", "fabricat", "plant", "mill", "foundry", "printing press"],
    "prof": ["clinic", "dental", "doctor", "ca ", "chartered", "accountant", "coaching", "tuition", "law", "legal", "advocate",
             "consult", "architect", "physio", "diagnostic", "insurance", "agency", "office", "studio", "realty", "real estate"],
    "micro": ["kirana", "grocery", "salon", "parlour", "pharmacy", "chemist", "medical store", "bakery", "shop", "store",
              "boutique", "tailor", "cafe", "dhaba", "mobile repair", "stationery", "hardware", "sweet"],
    "multi": ["chain", "outlets", "branches", "restaurant", "franchise", "hotel"],
}

# Needs most businesses in each segment have (case Appendix A2). Offered as
# optional add-ons the owner can toggle on, never forced into the price.
SEGMENT_SUGGESTIONS = {
    "micro": ["pos", "website", "guest_wifi"],
    "prof": ["email", "cloud_backup", "endpoint_security", "backup_internet"],
    "multi": ["backup_internet", "cctv", "pos", "email"],
    "mfg": ["endpoint_security", "machine_iot", "email", "backup_internet"],
}

PRIMARY = {"P01", "P02", "P03", "P04", "P05", "P06"}
WIRED = ["P01", "P02", "P03", "P05", "P06"]


def infer_segment(p: BusinessProfile) -> str:
    if p.segment:
        return p.segment
    text = f" {(p.business_type or '').lower()} {(p.business_name or '').lower()} "
    if (p.sites or 1) >= 2 and not any(k in text for k in SEGMENT_KEYWORDS["mfg"]):
        return "multi"
    for seg in ("mfg", "multi", "prof", "micro"):
        if any(k in text for k in SEGMENT_KEYWORDS[seg]):
            return seg
    return "micro" if (p.employees or 1) <= 5 else "prof"


def gst_ok(p: BusinessProfile) -> tuple[bool, str | None]:
    """A product that needs GST can be sold only on an active registration."""
    if p.gstin:
        rec = get_store().gstin_record(p.gstin.strip().upper())
        if rec is None:
            return False, "We could not find your GSTIN in the GST registry, so GST-only products are held back."
        if rec["status"] != "Active":
            return False, f"Your GST registration shows as {rec['status']}, so GST-only products are held back."
        return True, None
    return bool(p.has_gstin), None


def _primary_choice(seg: str, p: BusinessProfile, gst: bool) -> list[str]:
    """Ordered preference list for the main connection; first eligible wins."""
    emp = p.employees or 1
    if p.fibre_available is False:
        return ["P04", "P05"] if seg == "mfg" else ["P04"]
    if seg == "mfg":
        if emp >= 25:
            return ["P06", "P05", "P03", "P02"]
        return ["P05", "P03", "P02", "P01"]
    if seg == "multi":
        return ["P02", "P01"]
    if seg == "prof":
        heavy = emp >= 15 or "static_ip" in p.needs
        return (["P03", "P02"] if heavy else []) + (["P02", "P01"] if emp >= 4 else ["P01", "P02"])
    return ["P01", "P04"]


PRIMARY_REASON = {
    "P01": "100 Mbps fibre: enough for UPI, billing and a few devices",
    "P02": "300 Mbps fibre: smooth video calls and many devices at once",
    "P03": "1 Gbps fibre for heavy data, servers and large teams",
    "P04": "5G AirFiber: installs in 2 days with no digging, works where fibre is not laid",
    "P05": "Dedicated leased line with guaranteed speed for machines and ERP",
    "P06": "100 Mbps dedicated leased line for a large plant with guaranteed uptime",
}

NEED_PRODUCT = {
    "backup_internet": "P09", "static_ip": "P11", "whatsapp": "P15", "sms": "P14", "email": "P16",
    "cloud_backup": "P17", "website": "P18", "pos": "P19", "endpoint_security": "P20", "firewall": "P21",
    "guest_wifi": "P22", "cctv": "P23", "machine_iot": "P24", "fleet": "P25", "cloud_telephony": "P12",
    "toll_free": "P13", "sdwan": "P10",
}

NEED_REASON = {
    "internet": "Reliable internet for UPI, billing and daily work",
    "backup_internet": "Keeps you online if the main line goes down",
    "static_ip": "Fixed address for CCTV viewing, servers or remote access",
    "phone_lines": "Business numbers in the shop's name, separate from personal SIMs",
    "whatsapp": "Send catalogues, order updates and reminders on WhatsApp",
    "sms": "Bulk SMS for offers and appointment reminders",
    "email": "Professional email on your own domain, with documents and calendar",
    "cloud_backup": "Automatic backup of patient, client or billing files",
    "website": "Simple website and domain so customers can find you on Google",
    "pos": "Cloud billing counter with GST invoices and stock",
    "endpoint_security": "Antivirus and ransomware protection for each computer",
    "firewall": "Managed firewall protecting the office network",
    "guest_wifi": "Secure Wi-Fi with a separate network for customers",
    "cctv": "Cloud CCTV you can watch from your phone",
    "machine_iot": "Machine monitoring: downtime and energy alerts",
    "fleet": "Live location of delivery vehicles",
    "cloud_telephony": "One business number that rings across staff phones",
    "toll_free": "Toll-free number for customer calls",
    "sdwan": "Central management of all branch networks",
}


def _quantity(pid: str, seg: str, p: BusinessProfile) -> int:
    emp, sites = p.employees or 1, p.sites or 1
    prod = get_store().products[pid]
    if prod.unit == "per site":
        return sites
    return {
        "P07": p.phone_lines or 1, "P08": p.phone_lines or max(1, min(emp, 5)),
        "P16": p.email_users or emp, "P20": p.devices or max(1, emp),
        "P23": p.cameras or 4 * sites, "P19": p.pos_counters or sites,
        "P24": p.machines or 5, "P25": p.vehicles or 1, "P12": max(2, emp // 5),
    }.get(pid, 1)


def _line(prod: Product, qty: int, reason: str, *, core=False, selected=True, auto_for=None) -> LineItem:
    return LineItem(
        product_id=prod.product_id, name=prod.name, category=prod.category, unit=prod.unit,
        quantity=qty, unit_price=prod.price_min, monthly=prod.price_min * qty, setup_fee=prod.setup_fee * qty,
        min_contract_months=prod.min_contract_months, install_days=prod.install_days,
        selected=selected, core=core, reason=reason, auto_added_for=auto_for,
    )


def recommend(p: BusinessProfile) -> Recommendation:
    store = get_store()
    seg = infer_segment(p)
    gst, gst_note = gst_ok(p)
    ctx = dict(city_tier=p.city_tier, employees=p.employees or 1, sites=p.sites or 1, gst_ok=gst)
    items: list[LineItem] = []
    excluded: list[ExcludedItem] = []
    notes: list[str] = [gst_note] if gst_note else []

    def eligible(pid: str) -> bool:
        return not blocking_reasons(store.products[pid], **ctx)

    def exclude(pid: str) -> None:
        prod = store.products[pid]
        reasons = blocking_reasons(prod, **ctx)
        if reasons and pid not in {e.product_id for e in excluded}:
            excluded.append(ExcludedItem(product_id=pid, name=prod.name, reason="; ".join(r for r, _ in reasons),
                                         unlock=reasons[0][1]))

    needs = list(dict.fromkeys(p.needs))
    only_mobile = set(needs) <= {"phone_lines"} and bool(needs)

    # 1. Main connection (core) unless the owner only wants mobile lines.
    if not only_mobile:
        for pid in _primary_choice(seg, p, gst):
            if eligible(pid):
                why = PRIMARY_REASON[pid]
                items.append(_line(store.products[pid], _quantity(pid, seg, p), why, core=True))
                break
            exclude(pid)

    # 2. Phone lines.
    if "phone_lines" in needs or only_mobile:
        pid = "P07" if seg == "micro" else "P08"
        items.append(_line(store.products[pid], _quantity(pid, seg, p), NEED_REASON["phone_lines"], core=only_mobile))

    # 3. Everything else the owner asked for, then segment suggestions as optional.
    suggested = [] if only_mobile else [n for n in SEGMENT_SUGGESTIONS[seg] if n not in needs]
    if seg == "multi" and (p.sites or 1) >= 3:
        suggested.append("sdwan")
    for need, selected in [(n, True) for n in needs] + [(n, False) for n in suggested]:
        pid = NEED_PRODUCT.get(need)
        if not pid or any(i.product_id == pid for i in items):
            continue
        if not eligible(pid):
            if selected:
                exclude(pid)
            continue
        reason = NEED_REASON[need] if selected else f"Optional: most {SEGMENT_LABELS[seg].lower()} customers add this. {NEED_REASON[need]}"
        items.append(_line(store.products[pid], _quantity(pid, seg, p), reason, selected=selected))

    items = _resolve_dependencies(items, excluded, ctx)
    quote = price(items, excluded, p, notes)
    quote = _fit_budget(quote, p)
    headline = _headline(seg, quote)
    return Recommendation(profile=p.model_copy(update={"segment": seg}), segment=seg,
                          segment_label=SEGMENT_LABELS[seg], quote=quote, headline=headline)


def _resolve_dependencies(items: list[LineItem], excluded: list[ExcludedItem], ctx: dict) -> list[LineItem]:
    """Make every selected product's `requires_one_of` true, or drop it with a reason."""
    store = get_store()
    changed = True
    while changed:
        changed = False
        chosen = {i.product_id for i in items if i.selected}
        for it in list(items):
            prod = store.products[it.product_id]
            if not it.selected or dependency_satisfied(prod, chosen):
                continue
            # cheapest eligible product that satisfies the dependency
            options = sorted((store.products[x] for x in prod.requires_one_of
                              if not blocking_reasons(store.products[x], **ctx)), key=lambda x: x.price_min)
            if options:
                dep = options[0]
                items.append(_line(dep, ctx["sites"] if dep.unit == "per site" else 1,
                                   f"Needed for {prod.name}", core=True, auto_for=prod.product_id))
            else:
                items.remove(it)
                excluded.append(ExcludedItem(product_id=prod.product_id, name=prod.name,
                                             reason=f"Needs one of: {', '.join(store.products[x].name for x in prod.requires_one_of)}",
                                             unlock="Add a compatible connection"))
            changed = True
            break
    return items


def price(items: list[LineItem], excluded: list[ExcludedItem], p: BusinessProfile, notes: list[str] | None = None) -> Quote:
    sel = [i for i in items if i.selected]
    monthly = sum(i.monthly for i in sel)
    gst_amt = round(monthly * get_settings().gst_rate)
    contract = max([i.min_contract_months for i in sel] or [1])
    activation = max([i.install_days for i in sel] or [0])
    notes = list(notes or [])
    if p.current_monthly_spend:
        diff = monthly - p.current_monthly_spend
        if diff <= 0:
            notes.append(f"Rs {abs(diff):,} a month less than you spend today, on one bill.")
        else:
            notes.append(f"Rs {diff:,} a month more than today's Rs {p.current_monthly_spend:,}, for one bill and one support number.")
    return Quote(
        items=items, excluded=excluded, monthly_total=monthly, gst_amount=gst_amt,
        monthly_total_with_gst=monthly + gst_amt, one_time_setup=sum(i.setup_fee for i in sel),
        contract_months=contract, expected_activation_days=activation,
        current_monthly_spend=p.current_monthly_spend, budget_monthly=p.budget_monthly, notes=notes,
    )


def _fit_budget(q: Quote, p: BusinessProfile) -> Quote:
    if not p.budget_monthly or q.monthly_total <= p.budget_monthly:
        return q
    items = [i.model_copy() for i in q.items]
    # switch off the most expensive optional (non-core) items first
    for it in sorted((i for i in items if i.selected and not i.core), key=lambda i: -i.monthly):
        if sum(i.monthly for i in items if i.selected) <= p.budget_monthly:
            break
        it.selected = False
        it.reason = f"Switched off to stay within your Rs {p.budget_monthly:,} budget. {it.reason}"
    nq = price(items, q.excluded, p, [n for n in q.notes if not n.startswith("Rs ")])
    nq.over_budget_by = max(0, nq.monthly_total - p.budget_monthly)
    if nq.over_budget_by:
        nq.notes.append(f"The essentials alone are Rs {nq.over_budget_by:,} over your budget; consider 5G AirFiber or fewer lines.")
    return nq


def requote(profile: BusinessProfile, items: list[LineItem], toggles: dict[str, bool], quantities: dict[str, int]) -> Quote:
    """Recompute after the owner toggles add-ons or edits quantities."""
    store = get_store()
    gst, note = gst_ok(profile)
    ctx = dict(city_tier=profile.city_tier, employees=profile.employees or 1, sites=profile.sites or 1, gst_ok=gst)
    new: list[LineItem] = []
    excluded: list[ExcludedItem] = []
    for it in items:
        prod = store.products.get(it.product_id)
        if prod is None:
            continue
        reasons = blocking_reasons(prod, **ctx)
        if reasons:  # never sell an ineligible product, whatever the browser sent
            excluded.append(ExcludedItem(product_id=prod.product_id, name=prod.name,
                                         reason="; ".join(r for r, _ in reasons), unlock=reasons[0][1]))
            continue
        qty = int(quantities.get(it.product_id, it.quantity))
        qty = max(1, min(qty, 500))
        selected = toggles.get(it.product_id, it.selected) if not it.core else True
        # Prices always come from the catalogue, never from the request.
        new.append(it.model_copy(update=dict(
            name=prod.name, category=prod.category, unit=prod.unit, quantity=qty, unit_price=prod.price_min,
            monthly=prod.price_min * qty, setup_fee=prod.setup_fee * qty, min_contract_months=prod.min_contract_months,
            install_days=prod.install_days, selected=selected)))
    new = _resolve_dependencies(new, excluded, ctx)
    return price(new, excluded, profile, [note] if note else [])


def _headline(seg: str, q: Quote) -> str:
    core = [i.name for i in q.items if i.selected][:3]
    return (f"{', '.join(core)} for Rs {q.monthly_total:,}/month + GST, "
            f"active in about {q.expected_activation_days} days")


def parse_rupees(text: str) -> int | None:
    m = re.search(r"(\d[\d,]*)", text or "")
    return int(m.group(1).replace(",", "")) if m else None
