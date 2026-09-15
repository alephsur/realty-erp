"""Audited corrections and reopening of agency sales."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.csrf import verify_csrf_token
from app.database import get_db
from app.models.auth import User
from app.models.commissions import CommissionPayment
from app.models.transactions import SaleEvent
from app.schemas.property import SaleRead
from app.schemas.sale import CorrectSaleRequest, ReopenSaleRequest
from app.services.sales import get_accessible_sale, revise_sale, sale_snapshot

router = APIRouter(prefix="/sales", tags=["sales"])


def serialize_event(event):
    return {
        "id": str(event.id),
        "kind": event.kind,
        "version": event.version,
        "actor_name": event.actor_name,
        "reason": event.reason,
        "created_at": event.created_at,
        "before": event.before_data,
        "after": event.after_data,
    }


@router.get("/{sale_id}")
def detail(
    sale_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    sale, prop = get_accessible_sale(db, sale_id, user)
    events = (
        db.query(SaleEvent)
        .filter(SaleEvent.sale_id == sale.id, SaleEvent.tenant_id == user.tenant_id)
        .order_by(SaleEvent.version.desc())
        .all()
    )
    entries = (
        db.query(CommissionPayment)
        .filter(
            CommissionPayment.sale_id == sale.id,
            CommissionPayment.tenant_id == user.tenant_id,
        )
        .order_by(CommissionPayment.created_at, CommissionPayment.id)
        .all()
    )
    return {
        "sale": {**SaleRead.model_validate(sale).model_dump(), **sale_snapshot(sale)},
        "property_status": prop.status.value,
        "events": [serialize_event(e) for e in events],
        "commissions": [
            {
                "id": str(c.id),
                "event_id": str(c.event_id) if c.event_id else None,
                "agent_name": c.agent.full_name if c.agent else "Sin agente",
                "amount": str(c.amount),
                "status": c.status.value,
                "kind": c.kind,
                "invoice_number": c.invoice_number,
                "payment_date": c.payment_date,
            }
            for c in entries
        ],
    }


def mutate(db, sale_id, data, user, reopen=False):
    try:
        event, replayed = revise_sale(db, sale_id, data, user, reopen=reopen)
        db.commit()
        return {"event": serialize_event(event), "replayed": replayed}
    except Exception:
        db.rollback()
        raise


@router.post("/{sale_id}/correct", dependencies=[Depends(verify_csrf_token)])
def correct(
    sale_id: UUID,
    data: CorrectSaleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(db, sale_id, data, user)


@router.post("/{sale_id}/reopen", dependencies=[Depends(verify_csrf_token)])
def reopen(
    sale_id: UUID,
    data: ReopenSaleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(db, sale_id, data, user, reopen=True)
