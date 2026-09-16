import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_agency_user as get_current_user
from app.core.csrf import verify_csrf_token
from app.database import get_db
from app.models.auth import RoleEnum, User
from app.models.crm import Client, ClientPropertyInterest, ClientType
from app.models.transactions import Sale
from app.models.visits import Visit
from app.schemas import ClientRead
from app.services.access import (
    accessible_client,
    assignee,
    client_query,
    lock_agency,
    require_management,
)
from app.services.sales import accessible_property

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(verify_csrf_token)])

# ==========================================
# SCHEMAS (write / mutation only)
# ==========================================

class ClientCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    client_type: ClientType
    agent_id: Optional[UUID] = None
    dni: Optional[str] = None
    address: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    desired_zones: Optional[str] = None
    desired_type: Optional[str] = None
    notes: Optional[str] = None

class ClientUpdate(BaseModel):
    agent_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    client_type: Optional[ClientType] = None
    dni: Optional[str] = None
    address: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    desired_zones: Optional[str] = None
    desired_type: Optional[str] = None
    notes: Optional[str] = None

class PropertyInterestCreate(BaseModel):
    property_id: UUID
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


def _read_client(client, user):
    # Filter before serialization so hidden property names never enter the DTO.
    data = ClientRead.from_orm_object(client)
    data["property_interests"] = [
        interest for interest in client.property_interests
        if interest.tenant_id == user.tenant_id
        and interest.property and interest.property.tenant_id == user.tenant_id
        and (user.role != RoleEnum.AGENT or interest.property.agent_id == user.id)
    ]
    return ClientRead.model_validate(data)


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("")
def list_clients(
    client_type: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    agent_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    query = (
        client_query(db, current_user)
        .options(*_client_options())
    )

    if current_user.role == RoleEnum.AGENT:
        query = query.filter(Client.agent_id == current_user.id)
    elif agent_id:
        query = query.filter(Client.agent_id == agent_id)

    if not include_inactive:
        query = query.filter(Client.is_active.is_(True))

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
        "items": [_read_client(c, current_user) for c in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/{client_id}/matching-properties")
def matching_properties(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return active properties that match this buyer client's preferences."""
    client = accessible_client(db, client_id, current_user, active=True)
    if client.client_type != ClientType.BUYER:
        raise HTTPException(status_code=400, detail="Only buyer clients have property matches")

    from app.core.matching import find_matching_properties
    matches = find_matching_properties(db, client, user=current_user)
    return {"client_id": client_id, "total_matches": len(matches), "matches": matches}


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = accessible_client(db, client_id, current_user)
    return _read_client(client, current_user)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    lock_agency(db, current_user)
    agent = assignee(db, current_user, data.agent_id, default_self=True)
    effective_agent_id = agent.id if agent else None

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
            from app.api.notifications import push, push_to_managers
            from app.core.matching import find_matching_properties

            matches = find_matching_properties(db, new_client, user=agent or current_user)
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
def update_client(client_id: UUID, data: ClientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lock_agency(db, current_user)
    client = accessible_client(db, client_id, current_user)
    update_data = data.model_dump(exclude_unset=True)
    for field in ("first_name", "last_name", "client_type", "is_active"):
        if field in update_data and update_data[field] is None:
            raise HTTPException(422, "Los campos obligatorios no pueden estar vacíos.")
    if "agent_id" in update_data:
        require_management(current_user)
        if update_data["agent_id"] != client.agent_id:
            assignee(db, current_user, data.agent_id)
    if "is_active" in update_data:
        require_management(current_user)
    if data.client_type and data.client_type != client.client_type:
        referenced = (db.query(Sale.id).filter(Sale.buyer_id == client.id).first()
                      or db.query(Visit.id).filter(Visit.client_id == client.id).first()
                      or db.query(ClientPropertyInterest.id).filter(ClientPropertyInterest.client_id == client.id).first())
        if referenced:
            raise HTTPException(409, "No puedes cambiar el tipo de un cliente con historial comercial.")
    for key, value in update_data.items():
        setattr(client, key, value)

    db.commit()
    return {"message": "Client updated"}


@router.delete("/{client_id}")
def delete_client(client_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lock_agency(db, current_user)
    require_management(current_user)
    client = accessible_client(db, client_id, current_user)
    client.is_active = False
    db.commit()
    return {"message": "Client archived"}


# ==========================================
# PROPERTY INTEREST ENDPOINTS
# ==========================================

@router.post("/{client_id}/interests", status_code=status.HTTP_201_CREATED)
def add_property_interest(client_id: UUID, data: PropertyInterestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lock_agency(db, current_user)
    client = accessible_client(db, client_id, current_user, active=True)
    if client.client_type != ClientType.BUYER:
        raise HTTPException(422, "Selecciona un cliente demandante.")
    accessible_property(db, data.property_id, current_user)
    if db.query(ClientPropertyInterest.id).filter(
        ClientPropertyInterest.client_id == client_id,
        ClientPropertyInterest.property_id == data.property_id,
    ).first():
        raise HTTPException(409, "La propiedad ya está vinculada al cliente.")

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
def remove_property_interest(client_id: UUID, interest_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lock_agency(db, current_user)
    accessible_client(db, client_id, current_user)
    interest = db.query(ClientPropertyInterest).filter(
        ClientPropertyInterest.id == interest_id,
        ClientPropertyInterest.client_id == client_id,
        ClientPropertyInterest.tenant_id == current_user.tenant_id,
    ).first()
    if not interest:
        raise HTTPException(status_code=404, detail="Interest record not found")

    accessible_property(db, interest.property_id, current_user)
    db.delete(interest)
    db.commit()
    return {"message": "Property interest removed"}
