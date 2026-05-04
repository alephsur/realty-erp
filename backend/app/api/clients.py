from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.crm import Client, ClientType, ClientPropertyInterest
from app.api.dependencies import get_current_user
from app.schemas import ClientRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])

# ==========================================
# SCHEMAS (write / mutation only)
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
# HELPER: eager-load options for Client queries
# ==========================================

def _client_options():
    """joinedload chain that prevents all N+1 on Client read paths."""
    return [
        joinedload(Client.agent),
        joinedload(Client.property_interests).joinedload(ClientPropertyInterest.property),
    ]


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("")
def list_clients(
    client_type: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    query = (
        db.query(Client)
        .options(*_client_options())
        .filter(Client.tenant_id == current_user.tenant_id)
    )

    if current_user.role == RoleEnum.AGENT:
        query = query.filter(Client.agent_id == current_user.id)
    elif agent_id:
        query = query.filter(Client.agent_id == agent_id)

    if client_type and client_type != "ALL":
        query = query.filter(Client.client_type == client_type)

    if search:
        term = f"%{search}%"
        query = query.filter(
            Client.first_name.ilike(term) |
            Client.last_name.ilike(term) |
            Client.email.ilike(term) |
            Client.phone.ilike(term)
        )

    total = query.count()
    pages = max(1, -(-total // limit))
    items = query.order_by(Client.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [ClientRead.model_validate(c) for c in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/{client_id}/matching-properties")
def matching_properties(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return active properties that match this buyer client's preferences."""
    client = (
        db.query(Client)
        .options(joinedload(Client.agent))
        .filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if current_user.role == RoleEnum.AGENT and client.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if client.client_type != ClientType.BUYER:
        raise HTTPException(status_code=400, detail="Only buyer clients have property matches")

    from app.core.matching import find_matching_properties
    matches = find_matching_properties(db, client)
    return {"client_id": client_id, "total_matches": len(matches), "matches": matches}


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = (
        db.query(Client)
        .options(*_client_options())
        .filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if current_user.role == RoleEnum.AGENT and client.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return client


@router.post("", status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

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

    # Notify about matching properties for buyer clients (best-effort)
    if data.client_type == ClientType.BUYER:
        try:
            from app.core.matching import find_matching_properties
            from app.api.notifications import push, push_to_managers

            matches = find_matching_properties(db, new_client)
            if matches:
                full_name = f"{new_client.first_name} {new_client.last_name}"
                body = f"El comprador '{full_name}' tiene {len(matches)} propiedad(es) compatible(s) en cartera."
                if effective_agent_id:
                    push(db, user_id=effective_agent_id, tenant_id=current_user.tenant_id,
                         type="MATCH_FOUND", title="Propiedades compatibles encontradas",
                         body=body, entity_type="client", entity_id=str(new_client.id))
                else:
                    push_to_managers(db, tenant_id=current_user.tenant_id,
                                     type="MATCH_FOUND", title="Propiedades compatibles encontradas",
                                     body=body, entity_type="client", entity_id=str(new_client.id))
                db.commit()
        except Exception:
            logger.warning("Failed to create match notification for new client", exc_info=True)

    return {"message": "Client created", "id": str(new_client.id)}


@router.put("/{client_id}")
def update_client(client_id: str, data: ClientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

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
