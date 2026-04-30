"""
Pydantic v2 read-schema for Visits.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, model_validator


class VisitRead(BaseModel):
    id: str
    property_id: str
    property_title: Optional[str] = None
    property_address: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    scheduled_at: Optional[str] = None
    duration_minutes: int = 30
    status: Optional[str] = None
    status_key: Optional[str] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        v = data
        return {
            "id": str(v.id),
            "property_id": str(v.property_id),
            "property_title": v.property.title if v.property else None,
            "property_address": v.property.address if v.property else None,
            "client_id": str(v.client_id) if v.client_id else None,
            "client_name": (
                f"{v.client.first_name} {v.client.last_name}" if v.client else None
            ),
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
