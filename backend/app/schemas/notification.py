from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, model_validator


class NotificationRead(BaseModel):
    id: str
    type: str
    title: str
    body: str
    read_at: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    created_at: Optional[str] = None
    is_read: bool = False

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        n = data
        return {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "entity_type": n.entity_type,
            "entity_id": str(n.entity_id) if n.entity_id else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "is_read": n.read_at is not None,
        }
