from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.visits import Visit, VisitStatus
from app.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visits", tags=["visits"])

# ==========================================
# SCHEMAS
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
    client_id: Optional[str] = None
    agent_id: Optional[str] = None


# ==========================================
# HELPER
# ==========================================

def serialize_visit(v: Visit) -> dict:
    return {
        "id": str(v.id),
        "property_id": str(v.property_id),
        "property_title": v.property.title if v.property else None,
        "property_address": v.property.address if v.property else None,
        "client_id": str(v.client_id) if v.client_id else None,
        "client_name": f"{v.client.first_name} {v.client.last_name}" if v.client else None,
        "agent_id": str(v.agent_id) if v.agent_id else None,
        "agent_name": v.agent.full_name if v.agent else None,
        "scheduled_at": v.scheduled_at.isoformat() if v.scheduled_at else None,
        "duration_minutes": v.duration_minutes,
        "status": v.status.value if v.status else None,
        "status_key": v.status.name if v.status else None,
        "feedback": v.feedback,
        "rating": v.rating,
        "notes": v.notes,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("")
def list_visits(
    agent_id: Optional[str] = Query(None),
    property_id: Optional[str] = Query(None),
    visit_status: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    query = db.query(Visit).filter(Visit.tenant_id == current_user.tenant_id)
    
    # Agents only see their own visits
    if current_user.role == RoleEnum.AGENT:
        query = query.filter(Visit.agent_id == current_user.id)
    elif agent_id:
        query = query.filter(Visit.agent_id == agent_id)
    
    if property_id:
        query = query.filter(Visit.property_id == property_id)
    
    if visit_status:
        query = query.filter(Visit.status == visit_status)
    
    visits = query.order_by(Visit.scheduled_at.desc()).all()
    return [serialize_visit(v) for v in visits]


@router.get("/my")
def list_my_visits(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns upcoming visits for the current agent."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    visits = db.query(Visit).filter(
        Visit.tenant_id == current_user.tenant_id,
        Visit.agent_id == current_user.id,
        Visit.status == VisitStatus.SCHEDULED,
    ).order_by(Visit.scheduled_at.asc()).all()
    return [serialize_visit(v) for v in visits]


@router.get("/stats")
def visit_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Visit summary stats for the dashboard."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")

    tid = current_user.tenant_id
    base_query = db.query(Visit).filter(Visit.tenant_id == tid)
    
    # If agent, scope to their visits
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


@router.get("/{visit_id}")
def get_visit(visit_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visit = db.query(Visit).filter(Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    # Agents can only view their own visits
    if current_user.role == RoleEnum.AGENT and visit.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return serialize_visit(visit)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_visit(data: VisitCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User does not belong to a tenant")
    
    # If agent, auto-assign to self
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
    return {"message": "Visit scheduled", "id": str(new_visit.id)}


@router.put("/{visit_id}")
def update_visit(visit_id: str, data: VisitUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visit = db.query(Visit).filter(Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    
    # Agents can only update their own visits
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
