"""
Commissions API
===============
Commission liquidation and payment tracking for agents.
All endpoints are MANAGER/ADMIN only and tenant-scoped.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.commissions import CommissionPayment, CommissionStatus
from app.models.transactions import Sale
from app.api.dependencies import get_current_user

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
                "total_pending": 0.0,
                "commissions": [],
            }
        agents[aid]["total_pending"] = round(agents[aid]["total_pending"] + cp.amount, 2)
        agents[aid]["commissions"].append(_serialize(cp))

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

@router.post("/{sale_id}/pay")
def mark_paid(
    sale_id: str,
    data: PayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = require_manager(current_user)
    cp = db.query(CommissionPayment).filter(
        CommissionPayment.sale_id == sale_id,
        CommissionPayment.tenant_id == user.tenant_id,
    ).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Comisión no encontrada")
    if cp.status == CommissionStatus.PAID:
        raise HTTPException(status_code=400, detail="La comisión ya está pagada")

    cp.status = CommissionStatus.PAID
    cp.payment_date = (
        datetime.fromisoformat(data.payment_date)
        if data.payment_date
        else datetime.now(timezone.utc)
    )
    if data.invoice_number is not None:
        cp.invoice_number = data.invoice_number
    if data.notes is not None:
        cp.notes = data.notes

    db.commit()
    return {"message": "Comisión marcada como pagada", "id": str(cp.id)}


# ─────────────────────────────────────────────────────────
# POST /commissions/{sale_id}/invoice
# ─────────────────────────────────────────────────────────

@router.post("/{sale_id}/invoice")
def mark_invoiced(
    sale_id: str,
    data: InvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = require_manager(current_user)
    cp = db.query(CommissionPayment).filter(
        CommissionPayment.sale_id == sale_id,
        CommissionPayment.tenant_id == user.tenant_id,
    ).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Comisión no encontrada")
    if cp.status == CommissionStatus.PAID:
        raise HTTPException(status_code=400, detail="La comisión ya está pagada y no se puede refacturar")

    cp.status = CommissionStatus.INVOICED
    if data.invoice_number is not None:
        cp.invoice_number = data.invoice_number
    if data.notes is not None:
        cp.notes = data.notes

    db.commit()
    return {"message": "Comisión marcada como facturada", "id": str(cp.id)}
