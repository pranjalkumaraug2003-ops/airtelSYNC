import datetime as dt

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.kyc.validator import validate
from app.orders.models import STAGES, Order, OrderEvent, session
from app.privacy import store as vault
from app.rules.models import BusinessProfile, LineItem
from app.rules.recommender import requote

router = APIRouter(prefix="/api/orders", tags=["orders & tracker"])


class OrderIn(BaseModel):
    profile: BusinessProfile
    items: list[LineItem]
    kyc_session_id: str | None = None
    contact_phone: str | None = Field(None, description="10-digit mobile for WhatsApp updates")
    preferred_slot: str | None = None
    channel: str = "self-serve"
    partner_code: str | None = None


def _mask_phone(p: str | None) -> str | None:
    if not p:
        return None
    d = "".join(ch for ch in p if ch.isdigit())[-10:]
    return f"{d[:2]}••••••{d[-2:]}" if len(d) == 10 else None


def _event(db, order_id: str, idx: int, lang: str = "en") -> None:
    key, title, desc = STAGES[idx]
    db.add(OrderEvent(order_id=order_id, stage=key, message=f"{title}: {desc}"))


@router.post("")
def create_order(body: OrderIn):
    # Re-price on the server: the browser's numbers are never trusted.
    q = requote(body.profile, body.items, {}, {})
    selected = [i for i in q.items if i.selected]
    if not selected:
        raise HTTPException(400, "Nothing selected")
    verdict = "not_started"
    if body.kyc_session_id:
        s = vault.get(body.kyc_session_id)
        if s:
            verdict = validate(s.docs, s.declared_gstin).verdict
    o = Order(
        business_name=body.profile.business_name or body.profile.business_type or "Your business",
        segment=body.profile.segment or "micro", city=body.profile.city, language=body.profile.language,
        contact_phone_masked=_mask_phone(body.contact_phone),
        items=[i.model_dump() for i in selected], monthly_total=q.monthly_total, one_time_setup=q.one_time_setup,
        contract_months=q.contract_months, expected_activation_days=q.expected_activation_days,
        kyc_verdict=verdict, channel=body.channel, partner_code=body.partner_code, preferred_slot=body.preferred_slot,
    )
    with session() as db:
        db.add(o)
        _event(db, o.id, 0)
        if verdict == "verified":
            o.stage_index = 1
            _event(db, o.id, 1)
        db.commit()
        db.refresh(o)
        return _view(db, o)


def _view(db, o: Order) -> dict:
    created = o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=dt.timezone.utc)
    events = db.exec(select(OrderEvent).where(OrderEvent.order_id == o.id).order_by(OrderEvent.at)).all()
    eta = created + dt.timedelta(days=o.expected_activation_days)
    timeline = []
    for i, (key, title, desc) in enumerate(STAGES):
        done_ev = next((e for e in events if e.stage == key), None)
        timeline.append({"key": key, "title": title, "description": desc, "done": i <= o.stage_index,
                         "current": i == o.stage_index + 1, "at": done_ev.at.isoformat() if done_ev else None})
    lines = []
    for it in o.items:
        due = created + dt.timedelta(days=it["install_days"])
        lines.append({"product_id": it["product_id"], "name": it["name"], "quantity": it["quantity"],
                      "expected_by": due.date().isoformat(),
                      "status": "active" if o.stage_index >= 4 or (o.stage_index >= 3 and it["install_days"] <= 1) else "pending"})
    return {"id": o.id, "business_name": o.business_name, "created_at": created.isoformat(),
            "monthly_total": o.monthly_total, "one_time_setup": o.one_time_setup, "contract_months": o.contract_months,
            "expected_activation": eta.date().isoformat(), "kyc_verdict": o.kyc_verdict, "channel": o.channel,
            "contact_phone_masked": o.contact_phone_masked, "stage_index": o.stage_index, "timeline": timeline,
            "lines": lines, "notifications": [{"at": e.at.isoformat(), "via": e.notified_via, "message": e.message} for e in events]}


@router.get("/{order_id}")
def get_order(order_id: str):
    with session() as db:
        o = db.get(Order, order_id.upper())
        if not o:
            raise HTTPException(404, "Order not found. Check the code on your SMS/WhatsApp.")
        return _view(db, o)


@router.post("/{order_id}/advance")
def advance(order_id: str):
    """Demo only: move the order to the next stage (in production, fulfilment systems do this)."""
    with session() as db:
        o = db.get(Order, order_id.upper())
        if not o:
            raise HTTPException(404, "Order not found")
        if o.stage_index < len(STAGES) - 1:
            o.stage_index += 1
            _event(db, o.id, o.stage_index)
            db.add(o)
            db.commit()
            db.refresh(o)
        return _view(db, o)


@router.get("")
def list_orders(limit: int = 50):
    with session() as db:
        rows = db.exec(select(Order).order_by(Order.created_at.desc()).limit(limit)).all()  # type: ignore[attr-defined]
        return [{"id": o.id, "business_name": o.business_name, "monthly_total": o.monthly_total, "stage_index": o.stage_index,
                 "channel": o.channel, "partner_code": o.partner_code, "created_at": o.created_at.isoformat()} for o in rows]
