"""Sale rules shared by every UI entry point. The caller owns the transaction."""

import hashlib
import json
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.auth import RoleEnum, User
from app.models.commissions import CommissionPayment, CommissionStatus
from app.models.crm import Client, ClientType
from app.models.properties import Property, PropertyStatus
from app.models.transactions import Sale
from app.schemas.sale import SellPropertyRequest
from app.services.access import client_query, property_query
from app.services.access import lock_agency as lock_agency

MANAGEMENT_ROLES = (RoleEnum.ADMIN, RoleEnum.MANAGER)
SELLER_ROLES = (*MANAGEMENT_ROLES, RoleEnum.AGENT)
CENT = Decimal("0.01")


def accessible_property(db: Session, property_id: UUID, user: User, *, lock=False):
    if not user.tenant_id or user.role not in SELLER_ROLES:
        raise HTTPException(403, "No tienes permiso para cerrar ventas.")
    query = property_query(db, user).filter(Property.id == property_id)
    if user.role == RoleEnum.AGENT:
        query = query.filter(Property.agent_id == user.id)
    if lock:
        query = query.with_for_update()
    prop = query.populate_existing().first()
    if prop is None:
        raise HTTPException(404, "Propiedad no encontrada o no asignada a ti.")
    return prop


def buyer_query(db: Session, user: User):
    query = client_query(db, user).filter(
        Client.tenant_id == user.tenant_id,
        Client.client_type == ClientType.BUYER,
        Client.is_active.is_(True),
    )
    if user.role == RoleEnum.AGENT:
        query = query.filter(Client.agent_id == user.id)
    return query


def seller_query(db: Session, user: User):
    query = db.query(User).filter(
        User.tenant_id == user.tenant_id,
        User.role.in_(SELLER_ROLES),
        User.is_active.is_(True),
    )
    if user.role == RoleEnum.AGENT:
        query = query.filter(User.id == user.id)
    return query


def commission_amounts(price: Decimal, rate: Decimal, agent_rate: Decimal):
    total = (price * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    agent = (total * agent_rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return total, agent, total - agent


def request_hash(property_id: UUID, data: SellPropertyRequest):
    payload = {
        "property_id": str(property_id),
        "buyer_id": str(data.buyer_id),
        "agent_id": str(data.agent_id),
        "sale_price": str(data.sale_price.quantize(CENT)),
        "commission_rate": str(data.commission_rate.quantize(Decimal("0.0001"))),
        "agent_commission_rate": str(
            data.agent_commission_rate.quantize(Decimal("0.0001"))
        ),
        "notes": data.notes,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def close_sale(db: Session, property_id: UUID, data: SellPropertyRequest, user: User):
    # Serialize closures and status/assignment changes on the same property row.
    # Do not join the nullable agent relationship in this FOR UPDATE query.
    lock_agency(db, user)
    prop = accessible_property(db, property_id, user, lock=True)
    fingerprint = request_hash(property_id, data)
    previous_request = (
        db.query(Sale)
        .filter(
            Sale.tenant_id == user.tenant_id,
            Sale.closing_request_id == data.request_id,
        )
        .first()
    )
    if previous_request:
        if previous_request.closing_request_hash != fingerprint:
            raise HTTPException(
                409, "Este intento de cierre ya se usó con otros datos."
            )
        return previous_request, False

    # Legacy sales also prevent a second closure, even if their property state
    # was changed through the former generic update endpoint.
    if (
        prop.status == PropertyStatus.VENDIDA
        or db.query(Sale.id)
        .filter(Sale.property_id == prop.id, Sale.is_active.is_(True))
        .first()
    ):
        raise HTTPException(
            409, "La propiedad ya tiene un cierre. Revisa la venta antes de corregirla."
        )

    buyer = buyer_query(db, user).filter(Client.id == data.buyer_id).first()
    if buyer is None:
        raise HTTPException(422, "Selecciona un comprador activo al que tengas acceso.")
    agent = seller_query(db, user).filter(User.id == data.agent_id).first()
    if agent is None:
        raise HTTPException(
            422, "Selecciona un agente activo autorizado de tu agencia."
        )

    total, agent_amount, agency_amount = commission_amounts(
        data.sale_price, data.commission_rate, data.agent_commission_rate
    )
    sale = Sale(
        tenant_id=user.tenant_id,
        property_id=prop.id,
        buyer_id=buyer.id,
        agent_id=agent.id,
        sale_price=data.sale_price,
        commission_rate=data.commission_rate,
        agent_commission_rate=data.agent_commission_rate,
        total_commission=total,
        agent_commission=agent_amount,
        agency_commission=agency_amount,
        notes=data.notes,
        closing_request_id=data.request_id,
        closing_request_hash=fingerprint,
        closed_by_id=user.id,
        closed_from_status=prop.status.name,
    )
    db.add(sale)
    db.flush()
    event = record_event(
        db, sale, user, data.request_id, fingerprint, "CLOSED", "Cierre de venta", None
    )
    db.add(
        CommissionPayment(
            tenant_id=user.tenant_id,
            sale_id=sale.id,
            agent_id=agent.id,
            event_id=event.id,
            amount=agent_amount,
            status=CommissionStatus.PENDING,
        )
    )
    prop.status = PropertyStatus.VENDIDA
    prop.status_changed_at = datetime.now(timezone.utc)
    db.flush()
    return sale, True



def sale_snapshot(sale):
    fields = (
        "property_id",
        "buyer_id",
        "agent_id",
        "sale_price",
        "commission_rate",
        "agent_commission_rate",
        "total_commission",
        "agent_commission",
        "agency_commission",
        "sale_date",
        "notes",
        "reopened_at",
    )
    result = {}
    for field in fields:
        value = getattr(sale, field)
        result[field] = (
            value.isoformat()
            if isinstance(value, datetime)
            else str(value)
            if value is not None
            else None
        )
    result.update(
        is_active=sale.is_active,
        version=sale.version,
        buyer_name=f"{sale.buyer.first_name} {sale.buyer.last_name}"
        if sale.buyer
        else None,
        agent_name=sale.agent.full_name if sale.agent else None,
    )
    return result


def record_event(db, sale, user, request_id, fingerprint, kind, reason, before):
    from app.models.transactions import SaleEvent

    event = SaleEvent(
        tenant_id=user.tenant_id,
        sale_id=sale.id,
        request_id=request_id,
        request_hash=fingerprint,
        kind=kind,
        version=sale.version,
        actor_id=user.id,
        actor_name=user.full_name,
        reason=reason,
        before_data=before,
        after_data=sale_snapshot(sale),
    )
    db.add(event)
    db.flush()
    return event


def reconcile_commissions(db, sale, event):
    # Never mutate invoiced/paid entries. Signed adjustments preserve references
    # and offset previous overpayments, including after a change of agent.
    balances = {}
    for cp in (
        db.query(CommissionPayment)
        .filter(
            CommissionPayment.tenant_id == sale.tenant_id,
            CommissionPayment.sale_id == sale.id,
        )
        .all()
    ):
        balances[cp.agent_id] = balances.get(cp.agent_id, Decimal(0)) + cp.amount
    targets = {sale.agent_id: sale.agent_commission} if sale.is_active else {}
    for agent_id in sorted(balances.keys() | targets.keys(), key=str):
        difference = targets.get(agent_id, Decimal(0)) - balances.get(
            agent_id, Decimal(0)
        )
        if difference:
            db.add(
                CommissionPayment(
                    tenant_id=sale.tenant_id,
                    sale_id=sale.id,
                    agent_id=agent_id,
                    amount=difference,
                    status=CommissionStatus.PENDING,
                    event_id=event.id,
                    kind="ADJUSTMENT",
                    notes=event.reason,
                )
            )
    db.flush()


def get_accessible_sale(db, sale_id, user, *, lock=False):
    if not user.tenant_id or user.role not in SELLER_ROLES:
        raise HTTPException(403, "No tienes permiso para gestionar ventas.")
    sale = (
        db.query(Sale)
        .filter(Sale.id == sale_id, Sale.tenant_id == user.tenant_id)
        .first()
    )
    if sale is None:
        raise HTTPException(404, "Venta no encontrada.")
    prop = accessible_property(db, sale.property_id, user, lock=lock)
    if lock:
        db.refresh(sale, with_for_update=True)
    return sale, prop


def revise_sale(db, sale_id, data, user, *, reopen=False):
    from app.models.transactions import SaleEvent

    lock_agency(db, user)
    sale, prop = get_accessible_sale(db, sale_id, user, lock=True)
    kind = "REOPENED" if reopen else "CORRECTED"
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "sale_id": str(sale_id),
                "kind": kind,
                "data": data.model_dump(mode="json"),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    previous = (
        db.query(SaleEvent)
        .filter(
            SaleEvent.tenant_id == user.tenant_id,
            SaleEvent.request_id == data.request_id,
        )
        .first()
    )
    if previous:
        if previous.request_hash != fingerprint:
            raise HTTPException(409, "Este intento ya se utilizó con otros datos.")
        return previous, True
    if not sale.is_active:
        raise HTTPException(
            409,
            "La venta está reabierta. Registra un nuevo cierre con los datos actualizados.",
        )
    if sale.version != data.expected_version:
        raise HTTPException(
            409, "La venta ha cambiado. Cierra el formulario y vuelve a cargarla."
        )
    other = (
        db.query(Sale.id)
        .filter(
            Sale.property_id == prop.id, Sale.is_active.is_(True), Sale.id != sale.id
        )
        .first()
    )
    if other:
        raise HTTPException(
            409,
            "Hay varios cierres activos para esta propiedad. Revisa la inconsistencia histórica antes de continuar.",
        )
    before = sale_snapshot(sale)
    before["property_status"] = prop.status.value
    if reopen:
        sale.is_active = False
        sale.reopened_at = datetime.now(timezone.utc)
        prop.status = data.target_status
    else:
        buyer = buyer_query(db, user).filter(Client.id == data.buyer_id).first()
        agent = seller_query(db, user).filter(User.id == data.agent_id).first()
        if buyer is None or agent is None:
            raise HTTPException(
                422,
                "Selecciona un comprador y un agente activos a los que tengas acceso.",
            )
        sale.buyer = buyer
        sale.agent = agent
        sale.buyer_id, sale.agent_id = buyer.id, agent.id
        for field in (
            "sale_price",
            "commission_rate",
            "agent_commission_rate",
            "notes",
            "sale_date",
        ):
            setattr(sale, field, getattr(data, field))
        sale.total_commission, sale.agent_commission, sale.agency_commission = (
            commission_amounts(
                data.sale_price, data.commission_rate, data.agent_commission_rate
            )
        )
        prop.status = PropertyStatus.VENDIDA
    prop.status_changed_at = datetime.now(timezone.utc)
    sale.version += 1
    db.flush()
    event = record_event(
        db, sale, user, data.request_id, fingerprint, kind, data.reason, before
    )
    event.after_data = {**event.after_data, "property_status": prop.status.value}
    reconcile_commissions(db, sale, event)
    return event, False
