from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqla_func, case
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.properties import Property, PropertyStatus, PropertyType
from app.models.transactions import Sale
from app.models.crm import Client
from app.models.commissions import CommissionPayment, CommissionStatus
from app.api.dependencies import get_current_user
from app.schemas import PropertyRead, SaleRead, AgentRankingRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/properties", tags=["properties"])

# ==========================================
# SCHEMAS (write / mutation only)
# ==========================================

class PropertyCreate(BaseModel):
    title: str
    description: Optional[str] = None
    property_type: PropertyType = PropertyType.PISO
    price: float
    address: str
    city: Optional[str] = None
    postal_code: Optional[str] = None
    reference: Optional[str] = None
    bedrooms: int = 0
    bathrooms: int = 0
    sqm: float = 0.0
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    commission_rate: float = 0.0
    agent_id: Optional[str] = None
    agent_commission_rate: Optional[float] = None

class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    property_type: Optional[PropertyType] = None
    price: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    reference: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    sqm: Optional[float] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    commission_rate: Optional[float] = None
    agent_id: Optional[str] = None
    agent_commission_rate: Optional[float] = None
    status: Optional[PropertyStatus] = None

class AssignPropertyRequest(BaseModel):
    agent_id: Optional[str] = None  # null to unassign
    agent_commission_rate: Optional[float] = None

class BulkAssignRequest(BaseModel):
    property_ids: List[str]
    agent_id: Optional[str] = None
    agent_commission_rate: Optional[float] = None

class SellPropertyRequest(BaseModel):
    sale_price: float
    buyer_id: Optional[str] = None
    agent_commission_rate: Optional[float] = None  # Override agent's default rate
    agent_id: Optional[str] = None  # Override: explicitly assign the sale to this agent
    notes: Optional[str] = None


# ==========================================
# STATS ENDPOINTS
# ==========================================

@router.get("/stats/summary")
def dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    tid = current_user.tenant_id
    total_properties = db.query(Property).filter(Property.tenant_id == tid).count()
    active_properties = db.query(Property).filter(Property.tenant_id == tid, Property.status != PropertyStatus.VENDIDA, Property.status != PropertyStatus.RETIRADA).count()
    sold_properties = db.query(Property).filter(Property.tenant_id == tid, Property.status == PropertyStatus.VENDIDA).count()
    total_agents = db.query(User).filter(User.tenant_id == tid, User.role == RoleEnum.AGENT).count()

    sales = db.query(Sale).filter(Sale.tenant_id == tid).all()
    total_revenue = sum(s.total_commission for s in sales)

    unassigned_properties = db.query(Property).filter(
        Property.tenant_id == tid,
        Property.agent_id == None,
        Property.status != PropertyStatus.VENDIDA,
        Property.status != PropertyStatus.RETIRADA,
    ).count()

    return {
        "total_properties": total_properties,
        "active_properties": active_properties,
        "sold_properties": sold_properties,
        "total_agents": total_agents,
        "total_revenue": round(total_revenue, 2),
        "total_sales": len(sales),
        "unassigned_properties": unassigned_properties,
    }


@router.get("/stats/agent-summary")
def agent_summary_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """KPIs for the currently logged-in agent."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    tid = current_user.tenant_id
    uid = current_user.id

    my_properties = db.query(Property).filter(Property.tenant_id == tid, Property.agent_id == uid).count()
    my_active = db.query(Property).filter(
        Property.tenant_id == tid, Property.agent_id == uid,
        Property.status != PropertyStatus.VENDIDA, Property.status != PropertyStatus.RETIRADA
    ).count()
    my_sold = db.query(Property).filter(
        Property.tenant_id == tid, Property.agent_id == uid,
        Property.status == PropertyStatus.VENDIDA
    ).count()

    my_sales = db.query(Sale).filter(Sale.tenant_id == tid, Sale.agent_id == uid).all()
    total_commission = sum(s.agent_commission for s in my_sales)
    total_volume = sum(s.sale_price for s in my_sales)

    return {
        "total_properties": my_properties,
        "active_properties": my_active,
        "sold_properties": my_sold,
        "total_sales": len(my_sales),
        "total_commission": round(total_commission, 2),
        "total_volume": round(total_volume, 2),
    }


@router.get("/stats/agent-ranking", response_model=List[AgentRankingRead])
def agent_ranking(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns performance ranking of all agents for managers."""
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    tid = current_user.tenant_id
    agents = db.query(User).filter(User.tenant_id == tid, User.role == RoleEnum.AGENT).all()

    ranking = []
    for agent in agents:
        active_props = db.query(Property).filter(
            Property.tenant_id == tid, Property.agent_id == agent.id,
            Property.status != PropertyStatus.VENDIDA, Property.status != PropertyStatus.RETIRADA
        ).count()

        agent_sales = db.query(Sale).filter(Sale.tenant_id == tid, Sale.agent_id == agent.id).all()
        total_sales = len(agent_sales)
        total_commission = sum(s.agent_commission for s in agent_sales)
        total_volume = sum(s.sale_price for s in agent_sales)

        ranking.append({
            "id": str(agent.id),
            "full_name": agent.full_name,
            "email": agent.email,
            "active_properties": active_props,
            "total_sales": total_sales,
            "total_commission": round(total_commission, 2),
            "total_volume": round(total_volume, 2),
            "commission_rate": agent.commission_rate or 0.0,
        })

    ranking.sort(key=lambda x: (x["total_sales"], x["total_commission"]), reverse=True)
    return ranking


# ==========================================
# PROPERTY CRUD ENDPOINTS
# ==========================================

@router.get("")
def list_properties(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    base_q = (
        db.query(Property)
        .options(joinedload(Property.agent))
        .filter(Property.tenant_id == current_user.tenant_id)
    )
    if current_user.role == RoleEnum.AGENT:
        base_q = base_q.filter(Property.agent_id == current_user.id)

    if search:
        term = f"%{search}%"
        base_q = base_q.filter(
            Property.title.ilike(term) |
            Property.address.ilike(term) |
            Property.city.ilike(term) |
            Property.reference.ilike(term) |
            Property.owner_name.ilike(term)
        )

    if status_filter and status_filter != "ALL":
        base_q = base_q.filter(Property.status == status_filter)

    total = base_q.count()
    pages = max(1, -(-total // limit))  # ceiling division
    items = (
        base_q.order_by(Property.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "items": [PropertyRead.model_validate(p) for p in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/my")
def list_my_properties(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns only properties assigned to the currently authenticated agent."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    base_q = (
        db.query(Property)
        .options(joinedload(Property.agent))
        .filter(
            Property.tenant_id == current_user.tenant_id,
            Property.agent_id == current_user.id,
        )
    )
    total = base_q.count()
    pages = max(1, -(-total // limit))
    items = base_q.order_by(Property.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [PropertyRead.model_validate(p) for p in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/{property_id}/matching-buyers")
def matching_buyers(
    property_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return buyer clients whose preferences match this property."""
    prop = (
        db.query(Property)
        .options(joinedload(Property.agent))
        .filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id)
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    from app.core.matching import find_matching_buyers
    matches = find_matching_buyers(db, prop)
    return {"property_id": property_id, "total_matches": len(matches), "matches": matches}


@router.get("/{property_id}", response_model=PropertyRead)
def get_property(property_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    prop = (
        db.query(Property)
        .options(joinedload(Property.agent))
        .filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id)
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.post("", status_code=status.HTTP_201_CREATED)
def create_property(data: PropertyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    new_prop = Property(
        tenant_id=current_user.tenant_id,
        title=data.title,
        description=data.description,
        property_type=data.property_type,
        price=data.price,
        address=data.address,
        city=data.city,
        postal_code=data.postal_code,
        reference=data.reference,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        sqm=data.sqm,
        owner_name=data.owner_name,
        owner_phone=data.owner_phone,
        owner_email=data.owner_email,
        commission_rate=data.commission_rate,
        agent_id=data.agent_id if data.agent_id else None,
        agent_commission_rate=data.agent_commission_rate,
    )
    db.add(new_prop)
    db.commit()
    db.refresh(new_prop)

    # Notify about matching buyers (best-effort)
    try:
        from app.core.matching import find_matching_buyers
        from app.api.notifications import push, push_to_managers
        db.refresh(new_prop)
        if new_prop.agent:
            db.refresh(new_prop.agent)

        matches = find_matching_buyers(db, new_prop)
        if matches:
            body = f"La propiedad '{new_prop.title}' tiene {len(matches)} comprador(es) potencial(es) en el CRM."
            if new_prop.agent_id:
                push(db, user_id=new_prop.agent_id, tenant_id=current_user.tenant_id,
                     type="MATCH_FOUND", title="Compradores potenciales encontrados",
                     body=body, entity_type="property", entity_id=str(new_prop.id))
            else:
                push_to_managers(db, tenant_id=current_user.tenant_id,
                                 type="MATCH_FOUND", title="Compradores potenciales encontrados",
                                 body=body, entity_type="property", entity_id=str(new_prop.id))
            db.commit()
    except Exception:
        logger.warning("Failed to create match notification for new property", exc_info=True)

    return {"message": "Property created", "id": str(new_prop.id)}


@router.put("/{property_id}")
def update_property(property_id: str, data: PropertyUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    prop = db.query(Property).filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] != prop.status:
        from datetime import datetime, timezone
        update_data["status_changed_at"] = datetime.now(timezone.utc)
    for key, value in update_data.items():
        setattr(prop, key, value)

    db.commit()
    return {"message": "Property updated"}


@router.delete("/{property_id}")
def delete_property(property_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    prop = db.query(Property).filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    db.delete(prop)
    db.commit()
    return {"message": "Property deleted"}


# ==========================================
# ASSIGNMENT ENDPOINTS
# ==========================================

@router.put("/{property_id}/assign")
def assign_property(property_id: str, data: AssignPropertyRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Assign or unassign an agent to a property, optionally setting a per-property commission rate."""
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    prop = db.query(Property).filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if data.agent_id:
        agent = db.query(User).filter(User.id == data.agent_id, User.tenant_id == current_user.tenant_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        prop.agent_id = agent.id
    else:
        prop.agent_id = None

    if data.agent_commission_rate is not None:
        prop.agent_commission_rate = data.agent_commission_rate

    db.commit()
    return {"message": "Property assignment updated"}


@router.put("/bulk-assign", status_code=status.HTTP_200_OK)
def bulk_assign_properties(data: BulkAssignRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Bulk reassign multiple properties to an agent."""
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if data.agent_id:
        agent = db.query(User).filter(User.id == data.agent_id, User.tenant_id == current_user.tenant_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

    updated = 0
    for pid in data.property_ids:
        prop = db.query(Property).filter(Property.id == pid, Property.tenant_id == current_user.tenant_id).first()
        if prop:
            prop.agent_id = data.agent_id if data.agent_id else None
            if data.agent_commission_rate is not None:
                prop.agent_commission_rate = data.agent_commission_rate
            updated += 1

    db.commit()
    return {"message": f"{updated} properties updated"}


# ==========================================
# SELL + SALES ENDPOINTS
# ==========================================

@router.post("/{property_id}/sell")
def sell_property(property_id: str, data: SellPropertyRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    prop = (
        db.query(Property)
        .options(joinedload(Property.agent))
        .filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id)
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if prop.status == PropertyStatus.VENDIDA:
        raise HTTPException(status_code=400, detail="Property is already sold")

    total_commission = data.sale_price * (prop.commission_rate / 100)

    agent_rate = data.agent_commission_rate
    if agent_rate is None:
        agent_rate = prop.agent_commission_rate
    if agent_rate is None and prop.agent:
        agent_rate = prop.agent.commission_rate or 0.0
    agent_rate = agent_rate or 0.0

    agent_commission = total_commission * (agent_rate / 100)
    agency_commission = total_commission - agent_commission

    sale_agent_id = data.agent_id or prop.agent_id or current_user.id

    sale = Sale(
        tenant_id=current_user.tenant_id,
        property_id=prop.id,
        agent_id=sale_agent_id,
        buyer_id=data.buyer_id if data.buyer_id else None,
        sale_price=data.sale_price,
        total_commission=total_commission,
        agent_commission=agent_commission,
        agency_commission=agency_commission,
        notes=data.notes,
    )
    db.add(sale)
    db.flush()  # get sale.id before creating the payment

    commission_payment = CommissionPayment(
        tenant_id=current_user.tenant_id,
        sale_id=sale.id,
        agent_id=sale_agent_id,
        amount=agent_commission,
        status=CommissionStatus.PENDING,
    )
    db.add(commission_payment)
    prop.status = PropertyStatus.VENDIDA
    db.commit()

    # Notify managers about the new sale (best-effort)
    try:
        from app.api.notifications import push_to_managers
        agent_name = prop.agent.full_name if prop.agent else "Sin agente"
        push_to_managers(
            db,
            tenant_id=current_user.tenant_id,
            type="SALE_REGISTERED",
            title="Nueva venta registrada",
            body=f"'{prop.title}' vendida por {data.sale_price:,.0f} € — comisión total {total_commission:,.0f} €. Agente: {agent_name}.",
            entity_type="property",
            entity_id=str(prop.id),
        )
        db.commit()
    except Exception:
        logger.warning("Failed to send sale notification", exc_info=True)

    return {
        "message": "Sale registered",
        "sale_price": data.sale_price,
        "total_commission": round(total_commission, 2),
        "agent_commission": round(agent_commission, 2),
        "agency_commission": round(agency_commission, 2),
    }


@router.get("/sales/list")
def list_sales(
    agent_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sales for the tenant. Agents only see their own sales."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    query = (
        db.query(Sale)
        .options(
            joinedload(Sale.property),
            joinedload(Sale.agent),
            joinedload(Sale.buyer),
        )
        .filter(Sale.tenant_id == current_user.tenant_id)
    )

    if current_user.role == RoleEnum.AGENT:
        query = query.filter(Sale.agent_id == current_user.id)
    elif agent_id:
        query = query.filter(Sale.agent_id == agent_id)

    total = query.count()
    pages = max(1, -(-total // limit))
    items = query.order_by(Sale.sale_date.desc()).offset((page - 1) * limit).limit(limit).all()

    from app.schemas import SaleRead
    return {
        "items": [SaleRead.model_validate(s) for s in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }
