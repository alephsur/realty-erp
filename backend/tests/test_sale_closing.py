"""Real PostgreSQL checks. Opt in with RUN_POSTGRES_TESTS=1; uses its own container."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text


@pytest.mark.parametrize(
    "state",
    [
        "CAPTADA",
        "PUBLICADA",
        "EN_VISITAS",
        "RESERVADA",
        "PENDIENTE_NOTARIA",
        "RETIRADA",
    ],
)
@pytest.mark.parametrize("actor", ["agent", "manager", "admin"])
def test_close_from_every_unsold_state(data, state, actor):
    from app.models.commissions import CommissionPayment
    from app.models.properties import Property, PropertyStatus
    from app.models.transactions import Sale

    with data.env.sessions() as db:
        prop = db.get(Property, data.property)
        prop.status = PropertyStatus[state]
        prop.status_changed_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        old_changed_at = prop.status_changed_at
        db.commit()
    response = data.client(actor).post(data.url, json=data.payload)
    assert response.status_code == 200, response.text
    assert response.json()["total_commission"] == 6000
    with data.env.sessions() as db:
        sale = db.query(Sale).one()
        payment = db.query(CommissionPayment).one()
        prop = db.get(Property, data.property)
        assert sale.closed_by_id == getattr(data, actor)
        assert sale.closed_from_status == state
        assert sale.buyer_id == data.buyer and sale.agent_id == data.agent
        assert sale.sale_price == Decimal("200000.01")
        assert sale.agent_commission == payment.amount == Decimal("2400.00")
        assert sale.total_commission == sale.agent_commission + sale.agency_commission
        assert prop.status == PropertyStatus.VENDIDA
        assert prop.status_changed_at > old_changed_at


@pytest.mark.parametrize(
    "field",
    [
        "request_id",
        "buyer_id",
        "agent_id",
        "sale_price",
        "commission_rate",
        "agent_commission_rate",
    ],
)
@pytest.mark.parametrize("missing", [True, False])
def test_required_fields(data, field, missing):
    payload = dict(data.payload)
    if missing:
        payload.pop(field)
    else:
        payload[field] = None
    assert data.client().post(data.url, json=payload).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("sale_price", "0"),
        ("sale_price", "-1"),
        ("sale_price", "1.001"),
        ("sale_price", "NaN"),
        ("sale_price", "Infinity"),
        ("sale_price", "100000000000000"),
        ("commission_rate", "-1"),
        ("commission_rate", "100.0001"),
        ("commission_rate", "1.00001"),
        ("agent_commission_rate", "101"),
        ("agent_commission_rate", "NaN"),
        ("buyer_id", "not-a-uuid"),
    ],
)
def test_invalid_inputs(data, field, value):
    response = data.client().post(data.url, json={**data.payload, field: value})
    assert response.status_code == 422, response.text


def test_retry_is_stable_and_does_not_notify_again(data):
    from app.models.notifications import Notification
    from app.models.transactions import Sale

    client = data.client()
    first = client.post(data.url, json=data.payload)
    assert first.status_code == 200
    with data.env.sessions() as db:
        notifications = db.query(Notification).count()
    retry = client.post(data.url, json={**data.payload, "commission_rate": "3.0000"})
    assert retry.status_code == 200
    assert retry.json()["replayed"] is True
    assert retry.json()["sale_id"] == first.json()["sale_id"]
    assert (
        client.post(data.url, json={**data.payload, "notes": "Changed"}).status_code
        == 409
    )
    assert (
        client.post(
            data.url, json={**data.payload, "request_id": str(uuid4())}
        ).status_code
        == 409
    )
    with data.env.sessions() as db:
        assert db.query(Sale).count() == 1
        assert db.query(Notification).count() == notifications


@pytest.mark.parametrize("same_request", [True, False])
def test_simultaneous_closures(data, same_request):
    from app.models.commissions import CommissionPayment
    from app.models.transactions import Sale

    barrier = Barrier(2)
    clients = [data.client(), data.client()]

    def submit(index):
        payload = dict(data.payload)
        if not same_request:
            payload["request_id"] = str(uuid4())
        barrier.wait(timeout=10)
        return clients[index].post(data.url, json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, [0, 1]))
    assert sorted(r.status_code for r in responses) == (
        [200, 200] if same_request else [200, 409]
    )
    with data.env.sessions() as db:
        assert db.query(Sale).count() == db.query(CommissionPayment).count() == 1


@pytest.mark.parametrize(
    "actor,status", [("colleague", 404), ("outsider", 404), ("superadmin", 403)]
)
def test_property_permissions(data, actor, status):
    client = data.client(actor)
    assert client.post(data.url, json=data.payload).status_code == status
    assert (
        client.get(f"/properties/{data.property}/closing-options").status_code == status
    )


@pytest.mark.parametrize(
    "actor,field,foreign_id",
    [
        ("manager", "buyer_id", "other_buyer"),
        ("manager", "agent_id", "outsider"),
        ("agent", "buyer_id", "colleague_buyer"),
        ("agent", "agent_id", "colleague"),
    ],
)
def test_related_entity_permissions(data, actor, field, foreign_id):
    payload = {**data.payload, field: str(getattr(data, foreign_id))}
    assert data.client(actor).post(data.url, json=payload).status_code == 422


@pytest.mark.parametrize("entity", ["buyer", "agent"])
def test_inactive_participants(data, entity):
    from app.models.auth import User
    from app.models.crm import Client

    with data.env.sessions() as db:
        obj = db.get(Client if entity == "buyer" else User, getattr(data, entity))
        obj.is_active = False
        db.commit()
    assert data.client().post(data.url, json=data.payload).status_code == 422


def test_options_respect_visibility_and_search(data):
    client = data.client("agent")
    options = client.get(f"/properties/{data.property}/closing-options").json()
    assert [a["id"] for a in options["agents"]] == [str(data.agent)]
    assert [b["id"] for b in options["buyers"]] == [str(data.buyer)]
    assert (
        client.get(
            f"/properties/{data.property}/closing-options?search=missing"
        ).json()["total"]
        == 0
    )
    assert (
        data.client("colleague").get(f"/properties/{data.property}").status_code == 404
    )


def test_generic_status_update_cannot_bypass_closure_or_reopen(data):
    client = data.client()
    url = f"/properties/{data.property}"
    assert client.put(url, json={"status": "VENDIDA"}).status_code == 409
    assert client.put(url, json={"status": None}).status_code == 422
    assert client.post(data.url, json=data.payload).status_code == 200
    assert client.put(url, json={"status": "CAPTADA"}).status_code == 409
    assert (
        client.put(url, json={"title": "Updated property details"}).status_code == 200
    )


def test_failure_rolls_back_sale_payment_and_state(data):
    from app.models.commissions import CommissionPayment
    from app.models.properties import Property, PropertyStatus
    from app.models.transactions import Sale

    def fail_payment(*args):
        raise RuntimeError("Simulated payment storage failure")

    event.listen(CommissionPayment, "before_insert", fail_payment)
    try:
        response = data.client(raise_server_exceptions=False).post(
            data.url, json=data.payload
        )
        assert response.status_code == 500
    finally:
        event.remove(CommissionPayment, "before_insert", fail_payment)
    with data.env.sessions() as db:
        assert db.query(Sale).count() == db.query(CommissionPayment).count() == 0
        assert db.get(Property, data.property).status == PropertyStatus.CAPTADA
    assert data.client().post(data.url, json=data.payload).status_code == 200


def test_zero_commission_is_explicit_and_valid(data):
    response = data.client().post(
        data.url, json={**data.payload, "commission_rate": "0"}
    )
    assert response.status_code == 200
    assert (
        response.json()["total_commission"] == response.json()["agent_commission"] == 0
    )


def test_financial_readers_work_with_decimal_amounts(data):
    client = data.client()
    assert client.post(data.url, json=data.payload).status_code == 200
    for endpoint in (
        "/properties/sales/list",
        "/properties/stats/summary",
        "/properties/stats/agent-summary",
        "/properties/stats/agent-ranking",
        "/commissions/pending",
        "/commissions/history",
        "/commissions/summary",
        "/reports/kpi-summary",
        "/reports/agent-performance",
        "/reports/top-sales",
        "/reports/sales-by-period",
        "/reports/commission-summary",
    ):
        response = client.get(endpoint)
        assert response.status_code == 200, (endpoint, response.text)
    sale = client.get("/properties/sales/list").json()["items"][0]
    assert isinstance(sale["sale_price"], (float, int))
    pending = client.get("/commissions/pending").json()[0]
    assert isinstance(pending["total_pending"], (float, int))


def test_half_cent_rounding_matches_the_preview(data):
    payload = {
        **data.payload,
        "sale_price": "100.50",
        "commission_rate": "1",
        "agent_commission_rate": "50",
    }
    response = data.client().post(data.url, json=payload)
    assert response.status_code == 200
    assert response.json()["total_commission"] == 1.01
    assert response.json()["agent_commission"] == 0.51
    assert response.json()["agency_commission"] == 0.50


def test_missing_legacy_rate_can_be_completed_in_the_closing_form(data):
    from app.models.properties import Property

    with data.env.sessions() as db:
        db.get(Property, data.property).commission_rate = None
        db.commit()
    client = data.client()
    options = client.get(f"/properties/{data.property}/closing-options")
    assert options.status_code == 200
    assert options.json()["property"]["commission_rate"] is None
    assert client.post(data.url, json=data.payload).status_code == 200


def test_request_id_cannot_be_reused_for_another_property(data):
    from app.models.properties import Property

    client = data.client()
    assert client.post(data.url, json=data.payload).status_code == 200
    with data.env.sessions() as db:
        second = Property(
            tenant_id=data.tenant,
            agent_id=data.agent,
            title="Second",
            address="Another address",
            price=100,
        )
        db.add(second)
        db.commit()
        second_id = second.id
    assert (
        client.post(f"/properties/{second_id}/sell", json=data.payload).status_code
        == 409
    )


@pytest.mark.parametrize("has_sale", [True, False])
def test_legacy_inconsistencies_require_review_instead_of_another_sale(data, has_sale):
    from app.models.properties import Property, PropertyStatus
    from app.models.transactions import Sale
    from scripts.audit_sales import audit_sales

    with data.env.sessions() as db:
        if has_sale:
            db.add(
                Sale(
                    tenant_id=data.tenant,
                    property_id=data.property,
                    sale_price=100,
                    total_commission=3,
                    agent_commission=1,
                    agency_commission=2,
                )
            )
        else:
            db.get(Property, data.property).status = PropertyStatus.VENDIDA
        db.commit()
    with data.env.engine.connect() as conn:
        before = audit_sales(conn)
    assert data.client().post(data.url, json=data.payload).status_code == 409
    with data.env.engine.connect() as conn:
        after = audit_sales(conn)
    assert before == after
    assert (
        len(after["sale_with_open_property" if has_sale else "sold_without_sale"]) == 1
    )


def test_close_requires_session_and_csrf(data):
    anonymous = TestClient(
        data.env.app, headers={"X-CSRF-Token": "test"}, cookies={"csrf_token": "test"}
    )
    with anonymous:
        assert anonymous.post(data.url, json=data.payload).status_code == 401
    authenticated = data.client()
    authenticated.headers.pop("X-CSRF-Token")
    assert authenticated.post(data.url, json=data.payload).status_code == 403


def test_migration_preserves_legacy_amounts_and_paid_commissions(sale_env):
    # A second disposable database exercises the upgrade with actual old rows.
    child_url = sale_env.url.replace("realty_sales_test", "realty_migration_test")
    with sale_env.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(text("CREATE DATABASE realty_migration_test"))
    child = create_engine(child_url)
    env = dict(os.environ, DATABASE_URL=child_url)

    def migrate(direction, revision):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", direction, revision],
            cwd=sale_env.backend,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr

    try:
        migrate("upgrade", "d1e2f3a4b5c6")
        ids = {name: uuid4() for name in ("tenant", "property", "sale", "payment")}
        with child.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO tenants(id, name, plan) VALUES (:tenant, 'Legacy', 'basic')
            """),
                ids,
            )
            conn.execute(
                text("""
                INSERT INTO properties(id, tenant_id, title, address, price,
                                       status, property_type)
                VALUES (:property, :tenant, 'Legacy', 'Address', 123.456789,
                        'VENDIDA', 'PISO')
            """),
                ids,
            )
            conn.execute(
                text("""
                INSERT INTO sales(id, tenant_id, property_id, sale_price,
                    total_commission, agent_commission, agency_commission, sale_date)
                VALUES (:sale, :tenant, :property, 123.456789,
                        10.005, 4.002, 6.003, NOW())
            """),
                ids,
            )
            conn.execute(
                text("""
                INSERT INTO commission_payments(id, tenant_id, sale_id, amount,
                                                status, invoice_number)
                VALUES (:payment, :tenant, :sale, 4.002, 'PAID', 'LEGACY-INVOICE')
            """),
                ids,
            )
        migrate("upgrade", "head")
        migrate("upgrade", "head")
        with child.connect() as conn:
            row = conn.execute(text("SELECT * FROM sales")).mappings().one()
            assert row["sale_price"] == Decimal("123.456789")
            assert row["total_commission"] == Decimal("10.005")
            assert row["agent_commission"] == Decimal("4.002")
            assert row["agency_commission"] == Decimal("6.003")
            assert row["closing_request_id"] is None and row["commission_rate"] is None
            payment = (
                conn.execute(text("SELECT * FROM commission_payments")).mappings().one()
            )
            assert payment["amount"] == Decimal("4.002")
            assert payment["status"] == "PAID"
            assert payment["invoice_number"] == "LEGACY-INVOICE"
        migrate("downgrade", "d1e2f3a4b5c6")
        migrate("upgrade", "head")
        with child.connect() as conn:
            assert conn.execute(
                text("SELECT sale_price FROM sales")
            ).scalar_one() == Decimal("123.456789")
    finally:
        child.dispose()
