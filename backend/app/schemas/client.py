"""
Pydantic v2 read-schema for Clients (including nested PropertyInterests).
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, model_validator


class PropertyInterestRead(BaseModel):
    id: str
    property_id: str
    property_title: Optional[str] = None
    interest_level: str
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        pi = data
        return {
            "id": str(pi.id),
            "property_id": str(pi.property_id),
            "property_title": pi.property.title if pi.property else None,
            "interest_level": pi.interest_level,
            "notes": pi.notes,
        }


class ClientRead(BaseModel):
    id: str
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    client_type: Optional[str] = None
    client_type_key: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    dni: Optional[str] = None
    address: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    desired_zones: Optional[str] = None
    desired_type: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    property_interests: List[PropertyInterestRead] = []

    @model_validator(mode="before")
    @classmethod
    def from_orm_object(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        c = data
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
            "property_interests": list(c.property_interests or []),
        }
