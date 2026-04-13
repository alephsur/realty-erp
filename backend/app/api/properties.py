from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqla_func, case
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.properties import Property, PropertyStatus, PropertyType
from app.models.transactions import Sale
from app.models.crm import Client
from app.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/properties", tags=["properties"])

# ==========================================
# SCHEMAS
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
    agent_commission_rate: Optional[float] = None  # Override agent's default rate
    buyer_id: Optional[str] = None
    notes: Optional[str] = None


# ==========================================
# HELPER
# ==========================================

def serialize_property(p: Property) -> dict:
    return {
        "id": str(p.id),
        "title": p.title,
        "description": p.description,
        "property_type": p.property_type.value if p.property_type else None,
        "price": p.price,
        "address": p.address,
        "city": p.city,
        "postal_code": p.postal_code,
        "reference": p.reference,
        "status": p.status.value if p.status else None,
        "status_key": p.status.name if p.status else None,
        "bedrooms": p.bedrooms,
        "bathrooms": p.bathrooms,
        "sqm": p.sqm,
        "owner_name": p.owner_name,
        "owner_phone": p.owner_phone,
        "owner_email": p.owner_email,
        "commission_rate": p.commission_rate,
        "agent_commission_rate": p.agent_commission_rate,
        "agent_id": str(p.agent_id) if p.agent_id else None,
        "agent_name": p.agent.full_name if p.agent else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }

def serialize_sale(s: Sale) -> dict:
    return {
        "id": str(s.id),
        "property_id": str(s.property_id),
        "property_title": s.property.title if s.property else None,
        "property_reference": s.property.reference if s.property else None,
        "agent_id": str(s.agent_id) if s.agent_id else None,
        "agent_name": s.agent.full_name if s.agent else None,
        "buyer_id": str(s.buyer_id) if s.buyer_id else None,
        "buyer_name": f"{s.buyer.first_name} {s.buyer.last_name}" if s.buyer else None,
        "sale_price": s.sale_price,
        "total_commission": s.total_commission,
        "agent_commission": s.agent_commission,
        "agency_commission": s.agency_commission,
        "notes": s.notes,
        "sale_date": s.sale_date.isoformat() if s.sale_date else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


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
    
    # Properties without agent
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


@router.get("/stats/agent-ranking")
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
    
    # Sort by total_sales desc, then by total_commission desc
    ranking.sort(key=lambda x: (x["total_sales"], x["total_commission"]), reverse=True)
    return ranking


# ==========================================
# PROPERTY CRUD ENDPOINTS
# ==========================================

@router.get("")
def list_properties(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    properties = db.query(Property).filter(Property.tenant_id == current_user.tenant_id).order_by(Property.created_at.desc()).all()
    return [serialize_property(p) for p in properties]


@router.get("/my")
def list_my_properties(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns only properties assigned to the currently authenticated agent."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    properties = db.query(Property).filter(
        Property.tenant_id == current_user.tenant_id,
        Property.agent_id == current_user.id
    ).order_by(Property.created_at.desc()).all()
    return [serialize_property(p) for p in properties]


@router.get("/{property_id}")
def get_property(property_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    prop = db.query(Property).filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return serialize_property(prop)


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
    return {"message": "Property created", "id": str(new_prop.id)}


@router.put("/{property_id}")
def update_property(property_id: str, data: PropertyUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    prop = db.query(Property).filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    update_data = data.model_dump(exclude_unset=True)
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
    
    prop = db.query(Property).filter(Property.id == property_id, Property.tenant_id == current_user.tenant_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    if prop.status == PropertyStatus.VENDIDA:
        raise HTTPException(status_code=400, detail="Property is already sold")
    
    # Calculate commissions
    total_commission = data.sale_price * (prop.commission_rate / 100)
    
    # Determine agent commission rate: request override > property override > agent default
    agent_rate = data.agent_commission_rate
    if agent_rate is None:
        agent_rate = prop.agent_commission_rate
    if agent_rate is None and prop.agent:
        agent_rate = prop.agent.commission_rate or 0.0
    agent_rate = agent_rate or 0.0
    
    agent_commission = total_commission * (agent_rate / 100)
    agency_commission = total_commission - agent_commission
    
    sale = Sale(
        tenant_id=current_user.tenant_id,
        property_id=prop.id,
        agent_id=prop.agent_id,
        buyer_id=data.buyer_id if data.buyer_id else None,
        sale_price=data.sale_price,
        total_commission=total_commission,
        agent_commission=agent_commission,
        agency_commission=agency_commission,
        notes=data.notes,
    )
    db.add(sale)
    
    prop.status = PropertyStatus.VENDIDA
    db.commit()
    
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all sales for the tenant. Agents only see their own sales."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    query = db.query(Sale).filter(Sale.tenant_id == current_user.tenant_id)
    
    # Agents can only see their own sales
    if current_user.role == RoleEnum.AGENT:
        query = query.filter(Sale.agent_id == current_user.id)
    elif agent_id:
        query = query.filter(Sale.agent_id == agent_id)
    
    sales = query.order_by(Sale.sale_date.desc()).all()
    return [serialize_sale(s) for s in sales]
