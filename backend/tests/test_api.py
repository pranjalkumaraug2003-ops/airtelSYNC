"""End-to-end journey through the HTTP API, plus a mocked Gemini turn."""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["GEMINI_API_KEY"] = ""

from pathlib import Path  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
DOCS = Path(__file__).resolve().parent.parent / "data" / "kyc_documents"


def test_full_journey():
    r = client.post("/api/advisor/start", json={"language": "en"}).json()
    sid = r["session_id"]
    assert r["mode"] == "guided"
    for msg in ["Dental clinic", "3-5", "1", "Delhi", "Yes", "Internet, Email"]:
        r = client.post("/api/advisor/chat", json={"session_id": sid, "message": msg}).json()
    rec = r["recommendation"]
    assert rec and rec["quote"]["monthly_total"] > 0

    q = client.post("/api/quote/requote", json={"profile": rec["profile"], "items": rec["quote"]["items"],
                                                "toggles": {"P17": True}}).json()
    assert q["monthly_total"] == rec["quote"]["monthly_total"] + 499

    notice = client.get("/api/kyc/notice?lang=hi").json()
    assert notice["points"]
    k = client.post("/api/kyc/consent", json={"language": "en"}).json()
    ksid = k["session_id"]
    files = {"file": ("gst.png", (DOCS / "K12_gst_certificate.png").read_bytes(), "image/png")}
    up = client.post(f"/api/kyc/{ksid}/upload", data={"doc_type": "gst_certificate"}, files=files).json()
    assert "•" in up["fields"]["gstin"]  # masked before leaving the server
    client.post(f"/api/kyc/{ksid}/sample/K12")
    rep = client.get(f"/api/kyc/{ksid}/report").json()
    assert rep["verdict"] == "verified"

    o = client.post("/api/orders", json={"profile": rec["profile"], "items": q["items"], "kyc_session_id": ksid,
                                         "contact_phone": "9876543210"}).json()
    assert o["kyc_verdict"] == "verified" and o["stage_index"] == 1
    assert o["contact_phone_masked"] == "98••••••10"
    o2 = client.post(f"/api/orders/{o['id']}/advance").json()
    assert o2["stage_index"] == 2
    assert client.get(f"/api/orders/{o['id']}").json()["id"] == o["id"]

    assert client.delete(f"/api/kyc/{ksid}").json()["deleted"]
    assert client.get(f"/api/kyc/{ksid}/report").status_code == 404


def test_order_prices_are_recomputed_server_side():
    rec = client.post("/api/quote/recommend", json={"business_type": "kirana", "employees": 2, "needs": ["internet"]}).json()
    items = rec["quote"]["items"]
    items[0]["monthly"] = 1  # tampered in the browser
    o = client.post("/api/orders", json={"profile": rec["profile"], "items": items}).json()
    assert o["monthly_total"] == rec["quote"]["monthly_total"]


def test_registry_lookup_and_partner_views():
    assert client.get("/api/registry/gstin/37IHKXV5167L1ZS").json()["status"] == "Cancelled"
    assert client.get("/api/registry/gstin/ABC").json()["valid_format"] is False
    cl = client.get("/api/partner/call-list?limit=5").json()
    assert len(cl["leads"]) == 5 and cl["model"]["auc"] > 0.6
    ins = client.get("/api/insights").json()
    assert ins["headline"]["activations"] == 368
    assert isinstance(client.get("/api/partner/advisor-leads").json(), list)


def test_ai_turn_is_used_when_available(monkeypatch):
    from app.advisor import engine as E

    monkeypatch.setattr(E, "_ai_turn", lambda s, t: E.AdvisorTurn(
        profile_update=E.ProfileUpdate(business_type="CA firm", employees=6, sites=1, city="Pune", has_gstin=True,
                                       needs=["internet", "email", "not_a_real_need"]),
        reply="Got it.", quick_replies=[], wants_recommendation=True))
    monkeypatch.setattr(E, "_ai_explain", lambda s, rec: f"Plan at Rs {rec.quote.monthly_total}")
    s = E.start("en")
    E._sessions[s["session_id"]].mode = "ai"
    out = E.chat(s["session_id"], "I run a 6 person CA firm in Pune, GST registered, need internet and email")
    assert out["recommendation"] is not None
    assert "not_a_real_need" not in out["profile"].needs  # model output is validated, not trusted


def test_ai_failure_falls_back_to_guided(monkeypatch):
    from app.advisor import engine as E

    def boom(*a, **k):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(E, "_ai_turn", boom)
    s = E.start("en")
    E._sessions[s["session_id"]].mode = "ai"
    out = E.chat(s["session_id"], "Kirana store")
    assert out["mode"] == "guided" and out["reply"]
