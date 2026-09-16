"""F0-05: exercise agency boundaries through the authenticated HTTP API."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytestmark = pytest.mark.usefixtures("sale_env")


def visit_payload(data, **changes):
    return {
        "property_id": str(data.property),
        "client_id": str(data.buyer),
        "agent_id": str(data.agent),
        "scheduled_at": "2026-09-16T10:00:00Z",
        **changes,
    }


def foreign_property(data):
    from app.models.properties import Property

    with data.env.sessions() as db:
        prop = Property(
            tenant_id=data.other_tenant,
            agent_id=data.outsider,
            title="Foreign private home",
            address="Secret address",
            price=100000,
        )
        db.add(prop)
        db.commit()
        return str(prop.id)


@pytest.mark.parametrize(
    "actor", ["admin", "manager", "agent", "colleague", "outsider", "superadmin"]
)
def test_client_and_property_read_matrix(data, actor):
    http = data.client(actor)
    visible = actor in {"admin", "manager", "agent"}
    for path in [f"/clients/{data.buyer}", f"/properties/{data.property}"]:
        response = http.get(path)
        assert response.status_code == (
            200 if visible else (403 if actor == "superadmin" else 404)
        ), response.text
    for path, expected_id in [("/clients", data.buyer), ("/properties", data.property)]:
        response = http.get(path)
        if actor == "superadmin":
            assert response.status_code == 403
        else:
            assert response.status_code == 200
            assert (
                str(expected_id) in {item["id"] for item in response.json()["items"]}
            ) == visible


@pytest.mark.parametrize("actor", ["admin", "manager", "agent"])
def test_valid_client_visit_and_interest_flow(data, actor):
    http = data.client(actor)
    response = http.post(
        "/clients",
        json={
            "first_name": "Buyer",
            "last_name": "New",
            "client_type": "Demandante",
            "agent_id": str(data.agent),
        },
    )
    assert response.status_code == 201, response.text
    buyer_id = response.json()["id"]
    response = http.post("/visits", json=visit_payload(data, client_id=buyer_id))
    assert response.status_code == 201, response.text
    visit_id = response.json()["id"]
    assert http.get(f"/visits/{visit_id}").status_code == 200
    assert (
        http.put(
            f"/visits/{visit_id}", json={"status": "COMPLETED", "rating": 4}
        ).status_code
        == 200
    )
    interest = http.post(
        f"/clients/{buyer_id}/interests", json={"property_id": str(data.property)}
    )
    assert interest.status_code == 201, interest.text
    assert (
        http.post(
            f"/clients/{buyer_id}/interests", json={"property_id": str(data.property)}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "endpoint", ["clients", "properties", "visits", "calendar/appointments"]
)
@pytest.mark.parametrize("target", ["outsider", "inactive", "missing", "superadmin"])
def test_creates_reject_invalid_assignees_without_writes(data, endpoint, target):
    from app.models.appointments import Appointment
    from app.models.auth import User
    from app.models.crm import Client
    from app.models.properties import Property
    from app.models.visits import Visit

    if target == "inactive":
        with data.env.sessions() as db:
            db.get(User, data.colleague).is_active = False
            db.commit()
        agent_id = data.colleague
    else:
        agent_id = uuid4() if target == "missing" else getattr(data, target)
    payloads = {
        "clients": {
            "first_name": "Invalid",
            "last_name": "Agent",
            "client_type": "Demandante",
        },
        "properties": {"title": "Invalid", "address": "Address", "price": 1000},
        "visits": visit_payload(data),
        "calendar/appointments": {
            "title": "Invalid",
            "start_at": "2026-09-16T10:00:00Z",
            "end_at": "2026-09-16T11:00:00Z",
        },
    }
    model = {
        "clients": Client,
        "properties": Property,
        "visits": Visit,
        "calendar/appointments": Appointment,
    }[endpoint]
    with data.env.sessions() as db:
        before = db.query(model).count()
    response = data.client().post(
        f"/{endpoint}", json={**payloads[endpoint], "agent_id": str(agent_id)}
    )
    assert response.status_code == 422, response.text
    with data.env.sessions() as db:
        assert db.query(model).count() == before


@pytest.mark.parametrize("route", ["direct", "assign", "bulk", "client"])
def test_reassignment_rejects_cross_agency(data, route):
    http = data.client()
    url = {
        "direct": f"/properties/{data.property}",
        "assign": f"/properties/{data.property}/assign",
        "bulk": "/properties/bulk-assign",
        "client": f"/clients/{data.buyer}",
    }[route]
    payload = {"agent_id": str(data.outsider)}
    if route == "bulk":
        payload["property_ids"] = [str(data.property)]
    assert http.put(url, json=payload).status_code == 422


def test_bulk_assignment_is_reachable_and_atomic(data):
    from app.models.properties import Property

    http = data.client()
    response = http.put(
        "/properties/bulk-assign",
        json={
            "property_ids": [str(data.property), foreign_property(data)],
            "agent_id": str(data.colleague),
        },
    )
    assert response.status_code == 404, response.text
    with data.env.sessions() as db:
        assert db.get(Property, data.property).agent_id == data.agent
    response = http.put(
        "/properties/bulk-assign",
        json={"property_ids": [str(data.property)], "agent_id": str(data.colleague)},
    )
    assert response.status_code == 200, response.text
    assert data.client("agent").get(f"/properties/{data.property}").status_code == 404
    assert (
        data.client("colleague").get(f"/properties/{data.property}").status_code == 200
    )


@pytest.mark.parametrize(
    "field,target",
    [
        ("client_id", "other_buyer"),
        ("client_id", "colleague_buyer"),
        ("agent_id", "colleague"),
        ("property_id", "foreign"),
    ],
)
def test_agent_cannot_forge_visit_references(data, field, target):
    value = (
        foreign_property(data) if target == "foreign" else str(getattr(data, target))
    )
    response = data.client("agent").post(
        "/visits", json=visit_payload(data, **{field: value})
    )
    assert response.status_code in (403, 404), response.text


def test_manager_cannot_assign_visit_with_inaccessible_links(data):
    response = data.client().post(
        "/visits", json=visit_payload(data, agent_id=str(data.colleague))
    )
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("kind", ["owner", "inactive"])
def test_visit_buyer_must_be_active_demandant(data, kind):
    from app.models.crm import Client, ClientType

    with data.env.sessions() as db:
        client = db.get(Client, data.buyer)
        if kind == "owner":
            client.client_type = ClientType.OWNER
        else:
            client.is_active = False
        db.commit()
    assert data.client().post("/visits", json=visit_payload(data)).status_code in (
        404,
        422,
    )


def test_interest_requires_both_accessible_references(data):
    http = data.client("agent")
    for buyer, prop in [
        (data.colleague_buyer, data.property),
        (data.other_buyer, data.property),
        (data.buyer, foreign_property(data)),
        (data.buyer, uuid4()),
    ]:
        assert (
            http.post(
                f"/clients/{buyer}/interests", json={"property_id": str(prop)}
            ).status_code
            == 404
        )
    manager = data.client()
    assert (
        manager.post(
            f"/clients/{data.colleague_buyer}/interests",
            json={"property_id": str(data.property)},
        ).status_code
        == 201
    )
    interest_id = manager.get(f"/clients/{data.colleague_buyer}").json()[
        "property_interests"
    ][0]["id"]
    assert (
        http.delete(
            f"/clients/{data.colleague_buyer}/interests/{interest_id}"
        ).status_code
        == 404
    )


@pytest.mark.parametrize("entity", ["property", "client"])
def test_reassignment_revokes_visit_calendar_export_and_mutation_access(data, entity):
    manager = data.client()
    result = manager.post("/visits", json=visit_payload(data))
    assert result.status_code == 201, result.text
    visit_id = result.json()["id"]
    agent = data.client("agent")
    params = {"start": "2026-09-01", "end": "2026-10-01"}
    assert len(agent.get("/calendar/events", params=params).json()["events"]) == 1
    url = (
        f"/properties/{data.property}/assign"
        if entity == "property"
        else f"/clients/{data.buyer}"
    )
    assert manager.put(url, json={"agent_id": str(data.colleague)}).status_code == 200
    assert agent.get("/visits").json()["total"] == 0
    assert agent.get("/visits/my").json()["total"] == 0
    assert agent.get("/visits/stats").json()["total"] == 0
    assert agent.get(f"/visits/{visit_id}").status_code == 404
    assert (
        agent.put(f"/visits/{visit_id}", json={"notes": "forbidden"}).status_code == 404
    )
    assert agent.delete(f"/visits/{visit_id}").status_code == 404
    assert agent.get("/calendar/events", params=params).json()["events"] == []
    assert "Test property" not in agent.get("/calendar/export/ical", params=params).text
    assert manager.get(f"/visits/{visit_id}").status_code == 200
    # Conflict warnings must not provide another route to hidden visit details.
    response = agent.post(
        "/calendar/appointments",
        json={
            "title": "Call",
            "start_at": "2026-09-16T10:00:00Z",
            "end_at": "2026-09-16T11:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["conflicts"] == []


def test_matching_and_nested_interests_follow_current_assignments(data):
    from app.models.crm import Client
    from app.models.properties import Property, PropertyStatus

    with data.env.sessions() as db:
        for buyer in db.query(Client).all():
            buyer.budget_max = 300000
        db.get(Property, data.property).status = PropertyStatus.PUBLICADA
        db.commit()
    manager = data.client()
    assert (
        manager.post(
            f"/clients/{data.buyer}/interests", json={"property_id": str(data.property)}
        ).status_code
        == 201
    )
    agent = data.client("agent")
    matches = agent.get(f"/properties/{data.property}/matching-buyers").json()[
        "matches"
    ]
    assert {m["id"] for m in matches} == {str(data.buyer)}
    assert (
        manager.put(
            f"/properties/{data.property}/assign",
            json={"agent_id": str(data.colleague)},
        ).status_code
        == 200
    )
    assert agent.get(f"/properties/{data.property}/matching-buyers").status_code == 404
    assert (
        agent.get(f"/clients/{data.buyer}/matching-properties").json()["matches"] == []
    )
    assert agent.get(f"/clients/{data.buyer}").json()["property_interests"] == []
    assert manager.get(f"/clients/{data.buyer}").json()["property_interests"]


def test_legacy_cross_agency_links_do_not_leak(data):
    from app.models.crm import ClientPropertyInterest
    from app.models.visits import Visit

    foreign = foreign_property(data)
    with data.env.sessions() as db:
        db.add(
            ClientPropertyInterest(
                tenant_id=data.tenant, client_id=data.buyer, property_id=foreign
            )
        )
        db.add(
            Visit(
                tenant_id=data.tenant,
                agent_id=data.agent,
                client_id=data.other_buyer,
                property_id=data.property,
                scheduled_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
            )
        )
        db.commit()
    for actor in ["manager", "agent"]:
        http = data.client(actor)
        assert http.get(f"/clients/{data.buyer}").json()["property_interests"] == []
        assert http.get("/visits").json()["total"] == 0


def test_archive_deactivation_and_reassignment_preserve_financial_history(data):
    from app.models.auth import User
    from app.models.commissions import CommissionPayment
    from app.models.crm import Client
    from app.models.transactions import Sale, SaleEvent

    http = data.client()
    response = http.post(data.url, json=data.payload)
    assert response.status_code == 200, response.text
    with data.env.sessions() as db:
        sale = db.query(Sale).one()
        before = (sale.id, sale.agent_id, sale.buyer_id, sale.agent_commission)
        payment = db.query(CommissionPayment).one()
        payment_before = (payment.id, payment.agent_id, payment.amount, payment.status)
    assert http.delete(f"/clients/{data.buyer}").status_code == 200
    assert (
        http.put(
            f"/properties/{data.property}/assign",
            json={"agent_id": str(data.colleague)},
        ).status_code
        == 200
    )
    assert http.delete(f"/auth/tenant/users/{data.agent}").status_code == 200
    assert http.delete(f"/properties/{data.property}").status_code == 409
    assert str(data.buyer) not in {
        c["id"] for c in http.get("/clients").json()["items"]
    }
    assert str(data.buyer) in {
        c["id"] for c in http.get("/clients?include_inactive=true").json()["items"]
    }
    assert data.client("agent").get("/properties").status_code in (400, 403)
    with data.env.sessions() as db:
        sale = db.query(Sale).one()
        assert (sale.id, sale.agent_id, sale.buyer_id, sale.agent_commission) == before
        payment = db.query(CommissionPayment).one()
        assert (
            payment.id,
            payment.agent_id,
            payment.amount,
            payment.status,
        ) == payment_before
        assert db.query(SaleEvent).count() == 1
        assert not db.get(Client, data.buyer).is_active
        assert not db.get(User, data.agent).is_active
    assert (
        http.put(f"/clients/{data.buyer}", json={"is_active": True}).status_code == 200
    )
    assert http.get(f"/clients/{data.buyer}").json()["is_active"] is True


@pytest.mark.parametrize("actor", ["admin", "manager"])
def test_management_cannot_create_or_promote_superadmin(data, actor):
    http = data.client(actor)
    assert (
        http.post(
            "/auth/tenant/users",
            json={
                "email": "escalation@example.com",
                "full_name": "Escalation",
                "role": "SUPER_ADMIN",
            },
        ).status_code
        == 422
    )
    for target in [data.agent, getattr(data, actor)]:
        assert (
            http.put(
                f"/auth/tenant/users/{target}", json={"role": "SUPER_ADMIN"}
            ).status_code
            == 422
        )
    assert http.get("/auth/admin/tenants").status_code == 403


def test_last_manager_and_inactive_agency(data):
    from app.models.auth import RoleEnum, Tenant, User

    http = data.client()
    assert http.delete(f"/auth/tenant/users/{data.admin}").status_code == 200
    assert http.delete(f"/auth/tenant/users/{data.manager}").status_code == 409
    assert (
        http.put(
            f"/auth/tenant/users/{data.manager}", json={"role": RoleEnum.AGENT.value}
        ).status_code
        == 409
    )
    with data.env.sessions() as db:
        assert db.get(User, data.manager).is_active
        db.get(Tenant, data.tenant).is_active = False
        db.commit()
    assert http.get("/clients").status_code == 403
    assert http.post(data.url, json=data.payload).status_code == 403


@pytest.mark.parametrize(
    "path,payload",
    [
        (
            "/clients",
            {"first_name": "Test", "last_name": "Client", "client_type": "Demandante"},
        ),
        ("/properties", {"title": "Test", "address": "Test", "price": 1}),
        (
            "/calendar/appointments",
            {
                "title": "Test",
                "start_at": "2026-09-16T10:00:00Z",
                "end_at": "2026-09-16T11:00:00Z",
            },
        ),
    ],
)
def test_operational_writes_require_csrf(data, path, payload):
    http = data.client()
    del http.headers["X-CSRF-Token"]
    assert http.post(path, json=payload).status_code == 403
    assert http.post("/visits", json=visit_payload(data)).status_code == 403


@pytest.mark.parametrize(
    "path", ["/clients/not-a-uuid", "/properties/not-a-uuid", "/visits/not-a-uuid"]
)
def test_invalid_identifiers_are_validation_errors(data, path):
    assert data.client().get(path).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [("scheduled_at", "invalid"), ("duration_minutes", 0), ("duration_minutes", -30)],
)
def test_visit_input_errors_do_not_write(data, field, value):
    assert (
        data.client()
        .post("/visits", json=visit_payload(data, **{field: value}))
        .status_code
        == 422
    )


@pytest.mark.parametrize("actor", ["agent", "colleague", "outsider", "superadmin"])
def test_unauthorized_management_writes_leave_assignments_unchanged(data, actor):
    from app.models.auth import User
    from app.models.crm import Client
    from app.models.properties import Property

    http = data.client(actor)
    denied = [
        http.put(f"/clients/{data.buyer}", json={"agent_id": str(data.colleague)}),
        http.delete(f"/clients/{data.buyer}"),
        http.put(
            f"/properties/{data.property}/assign",
            json={"agent_id": str(data.colleague)},
        ),
        http.delete(f"/properties/{data.property}"),
        http.put(f"/auth/tenant/users/{data.agent}", json={"role": "MANAGER"}),
        http.delete(f"/auth/tenant/users/{data.agent}"),
    ]
    assert all(response.status_code in (403, 404) for response in denied)
    with data.env.sessions() as db:
        assert db.get(Client, data.buyer).agent_id == data.agent
        assert db.get(Client, data.buyer).is_active
        assert db.get(Property, data.property).agent_id == data.agent
        assert db.get(User, data.agent).is_active
        assert db.get(User, data.agent).role.value == "AGENT"


def test_cross_agency_visit_detail_updates_and_deletes(data):
    manager = data.client()
    visit_id = manager.post("/visits", json=visit_payload(data)).json()["id"]
    for actor in ("outsider", "colleague"):
        http = data.client(actor)
        assert http.get(f"/visits/{visit_id}").status_code == 404
        assert (
            http.put(f"/visits/{visit_id}", json={"status": "COMPLETED"}).status_code
            == 404
        )
        assert http.delete(f"/visits/{visit_id}").status_code == 404
    assert manager.get(f"/visits/{visit_id}").json()["status"] == "SCHEDULED"


def test_property_and_client_history_cannot_be_destroyed(data):
    http = data.client()
    http.post("/visits", json=visit_payload(data)).raise_for_status()
    assert http.delete(f"/properties/{data.property}").status_code == 409
    assert (
        http.put(
            f"/clients/{data.buyer}", json={"client_type": "Propietario"}
        ).status_code
        == 409
    )
    assert (
        data.client("superadmin")
        .delete(f"/auth/admin/tenants/{data.tenant}")
        .status_code
        == 409
    )
    assert http.get("/visits").json()["total"] == 1


def test_deactivated_account_cannot_login_or_redeem_previous_invite(data):
    from urllib.parse import parse_qs, urlparse

    from app.core.security import get_password_hash
    from app.models.auth import User

    with data.env.sessions() as db:
        db.get(User, data.agent).password_hash = get_password_hash("old-password")
        db.commit()
    http = data.client()
    invite = http.post(f"/auth/tenant/users/{data.agent}/invite").json()["invite_link"]
    token = parse_qs(urlparse(invite).query)["token"][0]
    assert http.delete(f"/auth/tenant/users/{data.agent}").status_code == 200
    assert (
        http.post(
            "/auth/login",
            json={"email": "agent@example.com", "password": "old-password"},
        ).status_code
        == 403
    )
    assert (
        http.post(
            "/auth/accept-invite", json={"token": token, "new_password": "new-password"}
        ).status_code
        == 400
    )
    with data.env.sessions() as db:
        assert not db.get(User, data.agent).is_active


def test_waiting_closure_rechecks_assignment_after_agency_lock(data):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.models.auth import Tenant
    from app.models.properties import Property
    from app.models.transactions import Sale

    http = data.client("agent")
    started = Event()

    def close():
        started.set()
        return http.post(data.url, json=data.payload)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with data.env.sessions() as db:
            db.query(Tenant).filter(Tenant.id == data.tenant).with_for_update().one()
            future = pool.submit(close)
            assert started.wait(5)
            db.get(Property, data.property).agent_id = data.colleague
            db.commit()
        response = future.result(timeout=10)
    assert response.status_code == 404, response.text
    with data.env.sessions() as db:
        assert db.query(Sale).count() == 0


def test_read_only_audit_reports_legacy_cross_agency_references(data):
    from app.models.auth import User
    from app.models.crm import ClientPropertyInterest
    from scripts.audit_entity_integrity import audit_entity_integrity

    with data.env.engine.connect() as connection:
        assert not any(audit_entity_integrity(connection).values())
    foreign = foreign_property(data)
    with data.env.sessions() as db:
        db.get(User, data.agent).is_active = False
        db.add(
            ClientPropertyInterest(
                tenant_id=data.tenant, client_id=data.buyer, property_id=foreign
            )
        )
        db.commit()
    with data.env.engine.connect() as connection:
        findings = audit_entity_integrity(connection)
    assert len(findings["client_property_interests.property_id"]) == 1
    assert not findings[
        "clients.agent_id"
    ]  # Inactive assignments remain valid history.
    with data.env.sessions() as db:
        assert db.query(ClientPropertyInterest).count() == 1
