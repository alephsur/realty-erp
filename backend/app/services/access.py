"""Agency boundaries and current assignments shared by operational endpoints."""

from fastapi import HTTPException
from sqlalchemy import or_

from app.models.auth import RoleEnum, Tenant, User
from app.models.crm import Client
from app.models.properties import Property
from app.models.visits import Visit

MANAGEMENT_ROLES = (RoleEnum.ADMIN, RoleEnum.MANAGER)
AGENCY_ROLES = (*MANAGEMENT_ROLES, RoleEnum.AGENT)


def require_agency(user):
    if not user.tenant_id or user.role not in AGENCY_ROLES:
        raise HTTPException(403, "Se requiere un usuario de la agencia.")


def require_management(user):
    require_agency(user)
    if user.role not in MANAGEMENT_ROLES:
        raise HTTPException(403, "Esta operación requiere permisos de gestión.")


def lock_agency(db, user):
    """Serialize assignments, deactivations and financial writes in one order."""
    require_agency(user)
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == user.tenant_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    db.refresh(user)
    require_agency(user)
    if not tenant or not tenant.is_active or not user.is_active:
        raise HTTPException(403, "La cuenta o la agencia está inactiva.")


def assignee(db, user, agent_id, *, default_self=False):
    require_agency(user)
    if user.role == RoleEnum.AGENT:
        if agent_id and agent_id != user.id:
            raise HTTPException(403, "Solo puedes asignarte tus propios registros.")
        if default_self:
            agent_id = user.id
    if agent_id is None:
        return None
    agent = (
        db.query(User)
        .filter(
            User.id == agent_id,
            User.tenant_id == user.tenant_id,
            User.is_active.is_(True),
            User.role.in_(AGENCY_ROLES),
        )
        .first()
    )
    if not agent:
        raise HTTPException(422, "Selecciona un agente activo de tu agencia.")
    return agent


def property_query(db, user):
    require_agency(user)
    query = db.query(Property).filter(
        Property.tenant_id == user.tenant_id,
        or_(
            Property.agent_id.is_(None),
            Property.agent.has(User.tenant_id == user.tenant_id),
        ),
    )
    if user.role == RoleEnum.AGENT:
        query = query.filter(Property.agent_id == user.id)
    return query


def client_query(db, user):
    require_agency(user)
    query = db.query(Client).filter(
        Client.tenant_id == user.tenant_id,
        or_(
            Client.agent_id.is_(None),
            Client.agent.has(User.tenant_id == user.tenant_id),
        ),
    )
    if user.role == RoleEnum.AGENT:
        query = query.filter(Client.agent_id == user.id)
    return query


def visit_query(db, user):
    require_agency(user)
    query = db.query(Visit).filter(
        Visit.tenant_id == user.tenant_id,
        Visit.property.has(Property.tenant_id == user.tenant_id),
        or_(
            Visit.client_id.is_(None),
            Visit.client.has(Client.tenant_id == user.tenant_id),
        ),
        or_(
            Visit.agent_id.is_(None), Visit.agent.has(User.tenant_id == user.tenant_id)
        ),
    )
    if user.role == RoleEnum.AGENT:
        query = query.filter(
            Visit.agent_id == user.id,
            Visit.property.has(Property.agent_id == user.id),
            or_(
                Visit.client_id.is_(None), Visit.client.has(Client.agent_id == user.id)
            ),
        )
    return query


def accessible_client(db, client_id, user, *, active=False):
    query = client_query(db, user).filter(Client.id == client_id)
    if active:
        query = query.filter(Client.is_active.is_(True))
    client = query.first()
    if client is None:
        raise HTTPException(404, "Cliente no encontrado o no accesible.")
    return client


def accessible_visit(db, visit_id, user):
    visit = visit_query(db, user).filter(Visit.id == visit_id).first()
    if visit is None:
        raise HTTPException(404, "Visita no encontrada o no accesible.")
    return visit


def preserve_management(db, user, *, role, active):
    """An agency must retain an active administrator or manager."""
    if (
        user.is_active
        and user.role in MANAGEMENT_ROLES
        and (not active or role not in MANAGEMENT_ROLES)
    ):
        other = (
            db.query(User.id)
            .filter(
                User.tenant_id == user.tenant_id,
                User.id != user.id,
                User.is_active.is_(True),
                User.role.in_(MANAGEMENT_ROLES),
            )
            .first()
        )
        if not other:
            raise HTTPException(
                409,
                "La agencia debe conservar al menos un administrador o gerente activo.",
            )
