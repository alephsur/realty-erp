"""
Commissions API
===============
Commission liquidation and payment tracking for agents.
All endpoints are MANAGER/ADMIN only and tenant-scoped.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Optional
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.commissions import CommissionPayment, CommissionStatus, CommissionSettlement
from app.models.transactions import Sale
from app.api.dependencies import get_current_user
from app.core.csrf import verify_csrf_token
from app.services.sales import lock_agency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commissions", tags=["commissions"])


# ─────────────────────────────────────────────────────────
# Guards & helpers
# ─────────────────────────────────────────────────────────

def require_manager(current_user: User) -> User:
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Acceso restringido a gestores")
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuario sin tenant asignado")
    return current_user


def _parse_period(period: str):
    """Returns (start, end) or (None, None) for 'all'."""
    if not period or period == "all":
        return None, None
    if "-Q" in period:
        year, q = period.split("-Q")
        year, q = int(year), int(q)
        m_start = (q - 1) * 3 + 1
        start = datetime(year, m_start, 1, tzinfo=timezone.utc)
        m_end = m_start + 3
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if m_end > 12 else datetime(year, m_end, 1, tzinfo=timezone.utc)
        return start, end
    if len(period) == 4:
        year = int(period)
        return datetime(year, 1, 1, tzinfo=timezone.utc), datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    # YYYY-MM
    year, month = int(period[:4]), int(period[5:7])
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _serialize(cp: CommissionPayment) -> dict:
    sale = cp.sale
    return {
        "id": str(cp.id),
        "kind": cp.kind,
        "settlement_amount": cp.settlement.amount if cp.settlement else None,
        "settlement_notes": cp.settlement.notes if cp.settlement else None,
        "settlement_id": str(cp.settlement_id) if cp.settlement_id else None,
        "sale_id": str(cp.sale_id),
        "agent_id": str(cp.agent_id) if cp.agent_id else None,
        "agent_name": cp.agent.full_name if cp.agent else "Sin agente",
        "amount": round(cp.amount, 2),
        "status": cp.status.value,
        "payment_date": cp.payment_date.isoformat() if cp.payment_date else None,
        "invoice_number": cp.invoice_number,
        "notes": cp.notes,
        "created_at": cp.created_at.isoformat() if cp.created_at else None,
        "property_title": sale.property.title if sale and sale.property else None,
        "property_reference": sale.property.reference if sale and sale.property else None,
        "sale_price": sale.sale_price if sale else None,
        "sale_date": sale.sale_date.isoformat() if sale and sale.sale_date else None,
    }


def _base_query(db: Session, tid, agent_id: Optional[str], period: Optional[str]):
    q = (
        db.query(CommissionPayment)
        .options(
            joinedload(CommissionPayment.agent),
            joinedload(CommissionPayment.settlement),
            joinedload(CommissionPayment.sale).joinedload(Sale.property),
        )
        .filter(CommissionPayment.tenant_id == tid)
    )
    if agent_id:
        q = q.filter(CommissionPayment.agent_id == agent_id)
    start, end = _parse_period(period or "all")
    if start:
        q = q.filter(CommissionPayment.created_at >= start)
    if end:
        q = q.filter(CommissionPayment.created_at < end)
    return q


# ─────────────────────────────────────────────────────────
# Schemas (write / mutation)
# ─────────────────────────────────────────────────────────

class PayRequest(BaseModel):
    payment_date: Optional[str] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None


class InvoiceRequest(BaseModel):
    invoice_number: Optional[str] = None
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────
# GET /commissions/pending
# ─────────────────────────────────────────────────────────

@router.get("/pending")
def list_pending(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pending/invoiced commissions grouped by agent."""
    user = require_manager(current_user)

    payments = (
        db.query(CommissionPayment)
        .options(
            joinedload(CommissionPayment.agent),
            joinedload(CommissionPayment.settlement),
            joinedload(CommissionPayment.sale).joinedload(Sale.property),
        )
        .filter(
            CommissionPayment.tenant_id == user.tenant_id,
            CommissionPayment.status != CommissionStatus.PAID,
        )
        .order_by(CommissionPayment.created_at.desc())
        .all()
    )

    agents: dict = {}
    for cp in payments:
        aid = str(cp.agent_id) if cp.agent_id else "unassigned"
        if aid not in agents:
            agents[aid] = {
                "agent_id": aid,
                "agent_name": cp.agent.full_name if cp.agent else "Sin agente",
                "total_pending": 0,
                "commissions": [],
            }
        agents[aid]["total_pending"] += cp.amount
        agents[aid]["commissions"].append(_serialize(cp))

    for aid, group in agents.items():
        group["total_pending"] = round(group["total_pending"], 2)
        group["balance_token"] = balance_token([cp for cp in payments if (str(cp.agent_id) if cp.agent_id else "unassigned") == aid])
    result = sorted(agents.values(), key=lambda x: x["total_pending"], reverse=True)
    return result


# ─────────────────────────────────────────────────────────
# GET /commissions/history
# ─────────────────────────────────────────────────────────

@router.get("/history")
def list_history(
    agent_id: Optional[str] = Query(None),
    period: Optional[str] = Query("all"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full commission history (all statuses), filterable by agent and period."""
    user = require_manager(current_user)
    q = _base_query(db, user.tenant_id, agent_id, period)
    total = q.count()
    pages = max(1, -(-total // limit))
    items = q.order_by(CommissionPayment.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [_serialize(cp) for cp in items], "total": total, "pages": pages, "page": page}


# ─────────────────────────────────────────────────────────
# GET /commissions/summary
# ─────────────────────────────────────────────────────────

@router.get("/summary")
def commission_summary(
    agent_id: Optional[str] = Query(None),
    period: Optional[str] = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregated totals: pending / invoiced / paid."""
    user = require_manager(current_user)
    payments = _base_query(db, user.tenant_id, agent_id, period).all()

    return {
        "total":          round(sum(cp.amount for cp in payments), 2),
        "pending":        round(sum(cp.amount for cp in payments if cp.status == CommissionStatus.PENDING), 2),
        "invoiced":       round(sum(cp.amount for cp in payments if cp.status == CommissionStatus.INVOICED), 2),
        "paid":           round(sum(cp.amount for cp in payments if cp.status == CommissionStatus.PAID), 2),
        "count_total":    len(payments),
        "count_pending":  sum(1 for cp in payments if cp.status == CommissionStatus.PENDING),
        "count_invoiced": sum(1 for cp in payments if cp.status == CommissionStatus.INVOICED),
        "count_paid":     sum(1 for cp in payments if cp.status == CommissionStatus.PAID),
    }


# ─────────────────────────────────────────────────────────
# POST /commissions/{sale_id}/pay
# ─────────────────────────────────────────────────────────

@router.post("/{sale_id}/pay", dependencies=[Depends(verify_csrf_token)])
def mark_paid(sale_id: UUID, data: PayRequest, current_user: User = Depends(get_current_user)):
    require_manager(current_user)
    raise HTTPException(409, "Liquida el saldo completo del agente para incluir las correcciones y devoluciones pendientes.")


def balance_token(entries):
    content = sorted((str(c.id), str(c.amount), c.status.value, c.invoice_number) for c in entries)
    return hashlib.sha256(json.dumps(content).encode()).hexdigest()


class SettleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    balance_token: str = Field(min_length=64, max_length=64)
    payment_date: date
    invoice_number: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=10000)


@router.post("/agents/{agent_id}/settle", dependencies=[Depends(verify_csrf_token)])
def settle(agent_id: str, data: SettleRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = require_manager(current_user)
    try:
        aid = None if agent_id == "unassigned" else UUID(agent_id)
    except ValueError:
        raise HTTPException(422, "Agente no válido")
    lock_agency(db, user)
    fingerprint = hashlib.sha256(json.dumps({"agent": agent_id, **data.model_dump(mode="json")}, sort_keys=True).encode()).hexdigest()
    previous = db.query(CommissionSettlement).filter(
        CommissionSettlement.tenant_id == user.tenant_id, CommissionSettlement.request_id == data.request_id
    ).first()
    if previous:
        if previous.request_hash != fingerprint:
            raise HTTPException(409, "Este intento ya se utilizó con otros datos.")
        return {"id": str(previous.id), "amount": str(previous.amount), "replayed": True}
    entries = db.query(CommissionPayment).filter(
        CommissionPayment.tenant_id == user.tenant_id, CommissionPayment.agent_id == aid,
        CommissionPayment.status != CommissionStatus.PAID,
    ).with_for_update().populate_existing().all()
    if not entries or balance_token(entries) != data.balance_token:
        raise HTTPException(409, "El saldo ha cambiado. Cierra el formulario y actualiza las comisiones antes de liquidar.")
    settlement = CommissionSettlement(
        tenant_id=user.tenant_id, request_id=data.request_id, request_hash=fingerprint,
        agent_id=aid, actor_id=user.id, amount=sum((c.amount for c in entries), Decimal(0)),
        entry_ids=[str(c.id) for c in entries],
        payment_date=datetime.combine(data.payment_date, datetime.min.time(), tzinfo=timezone.utc),
        invoice_number=data.invoice_number, notes=data.notes,
    )
    db.add(settlement)
    db.flush()
    for cp in entries:
        cp.status = CommissionStatus.PAID
        cp.payment_date = settlement.payment_date
        cp.settlement_id = settlement.id
        # Existing invoices and adjustment reasons remain attached to each entry.
        if not cp.invoice_number:
            cp.invoice_number = data.invoice_number
    db.commit()
    return {"id": str(settlement.id), "amount": str(settlement.amount), "replayed": False}


@router.post("/entries/{entry_id}/invoice", dependencies=[Depends(verify_csrf_token)])
def invoice_entry(entry_id: UUID, data: InvoiceRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = require_manager(current_user)
    lock_agency(db, user)
    cp = db.query(CommissionPayment).filter(
        CommissionPayment.id == entry_id, CommissionPayment.tenant_id == user.tenant_id,
    ).with_for_update().populate_existing().first()
    if cp is None:
        raise HTTPException(404, "Comisión no encontrada")
    if cp.status != CommissionStatus.PENDING:
        raise HTTPException(409, "Este movimiento ya está facturado o liquidado.")
    cp.status = CommissionStatus.INVOICED
    cp.invoice_number = data.invoice_number
    if data.notes:
        cp.notes = "\n".join(filter(None, [cp.notes, data.notes]))
    db.commit()
    return {"id": str(cp.id)}


@router.post("/{sale_id}/invoice", dependencies=[Depends(verify_csrf_token)])
def legacy_invoice(sale_id: UUID, data: InvoiceRequest, current_user: User = Depends(get_current_user)):
    require_manager(current_user)
    raise HTTPException(409, "Selecciona el movimiento concreto de comisión para registrar su factura.")
