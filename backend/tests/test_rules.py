from app.rules.eligibility import audit_bundle
from app.rules.models import BusinessProfile as B
from app.rules.recommender import recommend, requote


def ids(q, selected=True):
    return {i.product_id for i in q.items if i.selected == selected}


def test_clinic_five_staff_tier2():
    r = recommend(B(business_type="physio clinic", employees=5, city_tier=2, has_gstin=True,
                    needs=["internet", "email"], budget_monthly=3000))
    assert r.segment == "prof"
    assert ids(r.quote) == {"P02", "P16"}
    assert r.quote.monthly_total == 2124


def test_no_gstin_blocks_gst_products():
    r = recommend(B(business_type="kirana", employees=2, has_gstin=False, needs=["internet", "whatsapp"]))
    assert "P15" not in ids(r.quote)
    assert any(e.product_id == "P15" for e in r.quote.excluded)


def test_cancelled_gstin_treated_as_no_gst():
    r = recommend(B(business_type="travel agency", employees=3, gstin="37IHKXV5167L1ZS", needs=["internet", "whatsapp"]))
    assert "P15" not in ids(r.quote)
    assert any("Cancelled" in n for n in r.quote.notes)


def test_tier2_never_gets_1g_fibre():
    r = recommend(B(business_type="CA firm", employees=18, city_tier=2, has_gstin=True, needs=["internet", "static_ip"]))
    assert "P03" not in ids(r.quote)


def test_only_mobile_lines_has_no_broadband():
    r = recommend(B(business_type="salon", employees=3, needs=["phone_lines"], phone_lines=2))
    assert ids(r.quote) == {"P07"}


def test_dependency_auto_added():
    r = recommend(B(business_type="pharmacy", employees=2, fibre_available=False, needs=["cctv"]))
    assert {"P04", "P23"} <= ids(r.quote)


def test_budget_switches_off_optional_items():
    r = recommend(B(business_type="restaurant chain", employees=40, sites=4, city_tier=1, has_gstin=True,
                    needs=["internet", "backup_internet", "cctv", "pos"], budget_monthly=9000))
    assert r.quote.monthly_total <= 9000 or r.quote.over_budget_by > 0
    assert "P02" in ids(r.quote)  # core connection never removed


def test_every_recommendation_passes_catalogue_rules():
    for b in [B(business_type=t, employees=e, sites=s, city_tier=c, has_gstin=g, needs=n)
              for t in ["kirana", "dental clinic", "restaurant chain", "textile unit"]
              for e in [1, 5, 12, 30] for s in [1, 3] for c in [1, 2] for g in [True, False]
              for n in [["internet"], ["internet", "whatsapp", "cctv", "firewall", "sdwan", "machine_iot"]]]:
        q = recommend(b).quote
        assert audit_bundle(sorted(ids(q)), city_tier=b.city_tier, employees=b.employees, sites=b.sites, gst_ok=b.has_gstin) == []


def test_requote_toggle_and_quantity():
    r = recommend(B(business_type="dental clinic", employees=5, city_tier=1, has_gstin=True, needs=["internet", "email"]))
    q = requote(r.profile, r.quote.items, {"P17": True}, {"P16": 3})
    assert "P17" in ids(q)
    assert next(i for i in q.items if i.product_id == "P16").quantity == 3
