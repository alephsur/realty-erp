"""Matching logic: buyers ↔ properties based on budget, zone and type preferences."""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.crm import Client, ClientType
from app.models.properties import Property, PropertyStatus


def find_matching_buyers(db: Session, prop: Property, limit: int = 20) -> List[Dict[str, Any]]:
    """Return buyer clients whose preferences are compatible with *prop*."""
    buyers = (
        db.query(Client)
        .filter(
            Client.tenant_id == prop.tenant_id,
            Client.client_type == ClientType.BUYER,
            Client.is_active == True,
        )
        .all()
    )

    matches: List[Dict[str, Any]] = []
    for buyer in buyers:
        score = 0
        reasons: List[str] = []

        # Hard exclusion: property is over buyer's max budget
        if buyer.budget_max and prop.price > buyer.budget_max:
            continue

        if buyer.budget_max and prop.price <= buyer.budget_max:
            score += 3
            reasons.append("dentro del presupuesto máximo")

        if buyer.budget_min and prop.price >= buyer.budget_min:
            score += 1

        if buyer.desired_type and prop.property_type:
            if prop.property_type.value.upper() == buyer.desired_type.upper():
                score += 2
                reasons.append(f"tipo {prop.property_type.value}")

        if buyer.desired_zones and prop.city:
            zones = [z.strip().lower() for z in buyer.desired_zones.split(",")]
            if prop.city.lower() in zones:
                score += 2
                reasons.append(f"zona {prop.city}")

        if score > 0:
            matches.append(
                {
                    "id": str(buyer.id),
                    "full_name": f"{buyer.first_name} {buyer.last_name}",
                    "email": buyer.email,
                    "phone": buyer.phone,
                    "budget_min": buyer.budget_min,
                    "budget_max": buyer.budget_max,
                    "desired_zones": buyer.desired_zones,
                    "desired_type": buyer.desired_type,
                    "agent_id": str(buyer.agent_id) if buyer.agent_id else None,
                    "agent_name": buyer.agent.full_name if buyer.agent else None,
                    "match_score": score,
                    "match_reasons": reasons,
                }
            )

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:limit]


def find_matching_properties(db: Session, buyer: Client, limit: int = 20) -> List[Dict[str, Any]]:
    """Return active properties that match *buyer*'s preferences."""
    props = (
        db.query(Property)
        .filter(
            Property.tenant_id == buyer.tenant_id,
            Property.status.in_([PropertyStatus.PUBLICADA, PropertyStatus.EN_VISITAS]),
        )
        .all()
    )

    matches: List[Dict[str, Any]] = []
    for prop in props:
        score = 0
        reasons: List[str] = []

        if buyer.budget_max and prop.price > buyer.budget_max:
            continue

        if buyer.budget_max and prop.price <= buyer.budget_max:
            score += 3
            reasons.append("dentro del presupuesto máximo")

        if buyer.budget_min and prop.price >= buyer.budget_min:
            score += 1

        if buyer.desired_type and prop.property_type:
            if prop.property_type.value.upper() == buyer.desired_type.upper():
                score += 2
                reasons.append(f"tipo {prop.property_type.value}")

        if buyer.desired_zones and prop.city:
            zones = [z.strip().lower() for z in buyer.desired_zones.split(",")]
            if prop.city.lower() in zones:
                score += 2
                reasons.append(f"zona {prop.city}")

        if score > 0:
            matches.append(
                {
                    "id": str(prop.id),
                    "title": prop.title,
                    "reference": prop.reference,
                    "property_type": prop.property_type.value if prop.property_type else None,
                    "price": prop.price,
                    "city": prop.city,
                    "address": prop.address,
                    "bedrooms": prop.bedrooms,
                    "bathrooms": prop.bathrooms,
                    "sqm": prop.sqm,
                    "status": prop.status.value if prop.status else None,
                    "agent_id": str(prop.agent_id) if prop.agent_id else None,
                    "agent_name": prop.agent.full_name if prop.agent else None,
                    "match_score": score,
                    "match_reasons": reasons,
                }
            )

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:limit]
