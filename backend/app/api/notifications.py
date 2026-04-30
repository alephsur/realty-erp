from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User, RoleEnum
from app.models.notifications import Notification
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ==========================================
# HELPER — call from other routers
# ==========================================

def push(
    db: Session,
    *,
    user_id,
    tenant_id,
    type: str,
    title: str,
    body: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> None:
    db.add(
        Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
        )
    )


def push_to_managers(
    db: Session,
    *,
    tenant_id,
    type: str,
    title: str,
    body: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> None:
    """Notify every ADMIN and MANAGER in the tenant."""
    managers = (
        db.query(User)
        .filter(
            User.tenant_id == tenant_id,
            User.role.in_([RoleEnum.ADMIN, RoleEnum.MANAGER]),
            User.is_active == True,
        )
        .all()
    )
    for m in managers:
        push(
            db,
            user_id=m.id,
            tenant_id=tenant_id,
            type=type,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
        )


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("", response_model=List[NotificationRead])
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.read_at == None)
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.read_at == None,
        )
        .count()
    )
    return {"count": count}


@router.put("/{notification_id}/read")
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Marked as read"}


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read_at == None,
    ).update({"read_at": datetime.now(timezone.utc)})
    db.commit()
    return {"message": "All notifications marked as read"}
