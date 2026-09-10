from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.visits import Visit, VisitStatus
from app.api.dependencies import get_current_user
from app.schemas import VisitRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visits", tags=["visits"])

# ==========================================
# SCHEMAS (write / mutation only)
# ==========================================

class VisitCreate(BaseModel):
    property_id: str
    client_id: Optional[str] = None
    agent_id: Optional[str] = None
    scheduled_at: str  # ISO datetime
    duration_minutes: int = 30
    notes: Optional[str] = None

class VisitUpdate(BaseModel):
    scheduled_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    status: Optional[VisitStatus] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None
    notes: Optional[str] = None


# ==========================================
# HELPER: eager-load options for Visit queries
# ==========================================

def _visit_options():
    """joinedload set that prevents all N+1 on Visit read paths."""
    return [
        joinedload(Visit.property),
        joinedload(Visit.agent),
        joinedload(Visit.client),
    ]


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("")
def list_visits(
    agent_id: Optional[str] = Query(None),
    property_id: Optional[str] = Query(None),
    visit_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    from app.models.properties import Property as PropertyModel
    from app.models.crm import Client as ClientModel

    query = (
        db.query(Visit)
        .options(*_visit_options())
        .filter(Visit.tenant_id == current_user.tenant_id)
    )

    if current_user.role == RoleEnum.AGENT:
        query = query.filter(Visit.agent_id == current_user.id)
    elif agent_id:
        query = query.filter(Visit.agent_id == agent_id)

    if property_id:
        query = query.filter(Visit.property_id == property_id)

    if visit_status and visit_status != "ALL":
        query = query.filter(Visit.status == visit_status)

    if search:
        term = f"%{search}%"
        query = (
            query
            .outerjoin(PropertyModel, Visit.property_id == PropertyModel.id)
            .outerjoin(ClientModel, Visit.client_id == ClientModel.id)
            .filter(
                PropertyModel.title.ilike(term) |
                ClientModel.first_name.ilike(term) |
                ClientModel.last_name.ilike(term)
            )
        )

    total = query.count()
    pages = max(1, -(-total // limit))
    items = (
        query.order_by(Visit.scheduled_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "items": [VisitRead.model_validate(v) for v in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/my")
def list_my_visits(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns upcoming visits for the current agent."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    base_q = (
        db.query(Visit)
        .options(*_visit_options())
        .filter(
            Visit.tenant_id == current_user.tenant_id,
            Visit.agent_id == current_user.id,
            Visit.status == VisitStatus.SCHEDULED,
        )
    )
    total = base_q.count()
    pages = max(1, -(-total // limit))
    items = base_q.order_by(Visit.scheduled_at.asc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [VisitRead.model_validate(v) for v in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/stats")
def visit_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Visit summary stats for the dashboard."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    tid = current_user.tenant_id
    base_query = db.query(Visit).filter(Visit.tenant_id == tid)

    if current_user.role == RoleEnum.AGENT:
        base_query = base_query.filter(Visit.agent_id == current_user.id)

    total = base_query.count()
    scheduled = base_query.filter(Visit.status == VisitStatus.SCHEDULED).count()
    completed = base_query.filter(Visit.status == VisitStatus.COMPLETED).count()
    cancelled = base_query.filter(Visit.status == VisitStatus.CANCELLED).count()
    no_show = base_query.filter(Visit.status == VisitStatus.NO_SHOW).count()

    return {
        "total": total,
        "scheduled": scheduled,
        "completed": completed,
        "cancelled": cancelled,
        "no_show": no_show,
    }


@router.get("/{visit_id}", response_model=VisitRead)
def get_visit(visit_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visit = (
        db.query(Visit)
        .options(*_visit_options())
        .filter(Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id)
        .first()
    )
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == RoleEnum.AGENT and visit.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return visit


@router.post("", status_code=status.HTTP_201_CREATED)
def create_visit(data: VisitCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    effective_agent_id = data.agent_id
    if current_user.role == RoleEnum.AGENT:
        effective_agent_id = str(current_user.id)

    scheduled_dt = datetime.fromisoformat(data.scheduled_at)

    new_visit = Visit(
        tenant_id=current_user.tenant_id,
        property_id=data.property_id,
        client_id=data.client_id if data.client_id else None,
        agent_id=effective_agent_id if effective_agent_id else None,
        scheduled_at=scheduled_dt,
        duration_minutes=data.duration_minutes,
        notes=data.notes,
    )
    db.add(new_visit)
    db.commit()
    db.refresh(new_visit)

    # Notify the agent about the new visit (best-effort, only when creator ≠ agent)
    if effective_agent_id and str(effective_agent_id) != str(current_user.id):
        try:
            from app.api.notifications import push
            from app.models.properties import Property
            prop = db.query(Property).filter(Property.id == data.property_id).first()
            prop_title = prop.title if prop else "desconocida"
            push(
                db,
                user_id=effective_agent_id,
                tenant_id=current_user.tenant_id,
                type="VISIT_SCHEDULED",
                title="Nueva visita programada",
                body=f"Visita para '{prop_title}' el {scheduled_dt.strftime('%d/%m/%Y a las %H:%M')}.",
                entity_type="visit",
                entity_id=str(new_visit.id),
            )
            db.commit()
        except Exception:
            logger.warning("Failed to create visit notification", exc_info=True)

    return {"message": "Visit scheduled", "id": str(new_visit.id)}


@router.put("/{visit_id}")
def update_visit(visit_id: str, data: VisitUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visit = db.query(Visit).filter(Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    if current_user.role == RoleEnum.AGENT and visit.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "scheduled_at" and value:
            setattr(visit, key, datetime.fromisoformat(value))
        else:
            setattr(visit, key, value)

    db.commit()
    return {"message": "Visit updated"}


@router.delete("/{visit_id}")
def delete_visit(visit_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visit = db.query(Visit).filter(Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    if current_user.role == RoleEnum.AGENT and visit.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    db.delete(visit)
    db.commit()
    return {"message": "Visit deleted"}
