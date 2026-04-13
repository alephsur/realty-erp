from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.crm import Client, ClientType, ClientPropertyInterest
from app.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])

# ==========================================
# SCHEMAS
# ==========================================

class ClientCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    client_type: ClientType
    agent_id: Optional[str] = None
    dni: Optional[str] = None
    address: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    desired_zones: Optional[str] = None
    desired_type: Optional[str] = None
    notes: Optional[str] = None

class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    client_type: Optional[ClientType] = None
    agent_id: Optional[str] = None
    dni: Optional[str] = None
    address: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    desired_zones: Optional[str] = None
    desired_type: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class PropertyInterestCreate(BaseModel):
    property_id: str
    interest_level: str = "medium"
    notes: Optional[str] = None


# ==========================================
# HELPER
# ==========================================

def serialize_client(c: Client) -> dict:
    return {
        "id": str(c.id),
        "first_name": c.first_name,
        "last_name": c.last_name,
        "full_name": f"{c.first_name} {c.last_name}",
        "email": c.email,
        "phone": c.phone,
        "client_type": c.client_type.value if c.client_type else None,
        "client_type_key": c.client_type.name if c.client_type else None,
        "agent_id": str(c.agent_id) if c.agent_id else None,
        "agent_name": c.agent.full_name if c.agent else None,
        "dni": c.dni,
        "address": c.address,
        "budget_min": c.budget_min,
        "budget_max": c.budget_max,
        "desired_zones": c.desired_zones,
        "desired_type": c.desired_type,
        "notes": c.notes,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "property_interests": [
            {
                "id": str(pi.id),
                "property_id": str(pi.property_id),
                "property_title": pi.property.title if pi.property else None,
                "interest_level": pi.interest_level,
                "notes": pi.notes,
            }
            for pi in (c.property_interests or [])
        ],
    }


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("")
def list_clients(
    client_type: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    query = db.query(Client).filter(Client.tenant_id == current_user.tenant_id)
    
    # Agents only see their own clients
    if current_user.role == RoleEnum.AGENT:
        query = query.filter(Client.agent_id == current_user.id)
    elif agent_id:
        query = query.filter(Client.agent_id == agent_id)
    
    if client_type:
        query = query.filter(Client.client_type == client_type)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Client.first_name.ilike(search_term)) |
            (Client.last_name.ilike(search_term)) |
            (Client.email.ilike(search_term)) |
            (Client.phone.ilike(search_term))
        )
    
    clients = query.order_by(Client.created_at.desc()).all()
    return [serialize_client(c) for c in clients]


@router.get("/{client_id}")
def get_client(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Agents can only view their own clients
    if current_user.role == RoleEnum.AGENT and client.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return serialize_client(client)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    # If agent, auto-assign to self
    effective_agent_id = data.agent_id
    if current_user.role == RoleEnum.AGENT:
        effective_agent_id = str(current_user.id)
    
    new_client = Client(
        tenant_id=current_user.tenant_id,
        agent_id=effective_agent_id if effective_agent_id else None,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        client_type=data.client_type,
        dni=data.dni,
        address=data.address,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        desired_zones=data.desired_zones,
        desired_type=data.desired_type,
        notes=data.notes,
    )
    db.add(new_client)
    db.commit()
    db.refresh(new_client)
    return {"message": "Client created", "id": str(new_client.id)}


@router.put("/{client_id}")
def update_client(client_id: str, data: ClientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Agents can only edit their own clients
    if current_user.role == RoleEnum.AGENT and client.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)
    
    db.commit()
    return {"message": "Client updated"}


@router.delete("/{client_id}")
def delete_client(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(client)
    db.commit()
    return {"message": "Client deleted"}


# ==========================================
# PROPERTY INTEREST ENDPOINTS
# ==========================================

@router.post("/{client_id}/interests", status_code=status.HTTP_201_CREATED)
def add_property_interest(client_id: str, data: PropertyInterestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    interest = ClientPropertyInterest(
        tenant_id=current_user.tenant_id,
        client_id=client_id,
        property_id=data.property_id,
        interest_level=data.interest_level,
        notes=data.notes,
    )
    db.add(interest)
    db.commit()
    return {"message": "Property interest added"}


@router.delete("/{client_id}/interests/{interest_id}")
def remove_property_interest(client_id: str, interest_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    interest = db.query(ClientPropertyInterest).filter(
        ClientPropertyInterest.id == interest_id,
        ClientPropertyInterest.client_id == client_id,
        ClientPropertyInterest.tenant_id == current_user.tenant_id,
    ).first()
    if not interest:
        raise HTTPException(status_code=404, detail="Interest record not found")
    
    db.delete(interest)
    db.commit()
    return {"message": "Property interest removed"}
