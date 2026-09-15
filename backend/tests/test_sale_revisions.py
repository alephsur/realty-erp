"""Revision, settlement and concurrency checks against isolated PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event


def close(data):
    response = data.client().post(data.url, json=data.payload)
    assert response.status_code == 200, response.text
    return response.json()["sale_id"]


def correction(data, **changes):
    return {
        **data.payload,
        "request_id": str(uuid4()),
        "expected_version": 1,
        "sale_date": datetime.now(timezone.utc).isoformat(),
        "reason": "Correct agreed terms",
        "sale_price": "150000",
        **changes,
    }


def reopening(**changes):
    return {
        "request_id": str(uuid4()),
        "expected_version": 1,
        "target_status": "PUBLICADA",
        "reason": "Buyer withdrew",
        **changes,
    }


def seed_status(data, status):
    from app.models.commissions import CommissionPayment, CommissionStatus

    with data.env.sessions() as db:
        cp = db.query(CommissionPayment).one()
        cp.status = CommissionStatus(status)
        cp.invoice_number = "ORIGINAL-2026"
        cp.notes = "Original document"
        if status == "PAID":
            cp.payment_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.commit()
        return cp.id


def settle_payload(group, **changes):
    return {
        "request_id": str(uuid4()),
        "balance_token": group["balance_token"],
        "payment_date": "2026-09-15",
        "invoice_number": "NET-2026",
        "notes": "Net settlement",
        **changes,
    }


@pytest.mark.parametrize("status", ["PENDING", "INVOICED", "PAID"])
def test_correction_preserves_original_and_reconciles_balance(data, status):
    from app.models.commissions import CommissionPayment
    from app.models.transactions import Sale, SaleEvent

    sale_id = close(data)
    original_id = seed_status(data, status)
    client = data.client()
    payload = correction(
        data, buyer_id=str(data.colleague_buyer), notes="Changed notes"
    )
    response = client.post(f"/sales/{sale_id}/correct", json=payload)
    assert response.status_code == 200, response.text
    with data.env.sessions() as db:
        sale = db.get(Sale, UUID(sale_id))
        assert sale.version == 2 and sale.is_active
        assert sale.sale_price == 150000 and sale.agent_commission == 1800
        assert sale.buyer_id == data.colleague_buyer and sale.notes == "Changed notes"
        cp = db.get(CommissionPayment, original_id)
        assert cp.amount == 2400 and cp.status.value == status
        assert cp.invoice_number == "ORIGINAL-2026" and cp.notes == "Original document"
        assert (cp.payment_date is not None) == (status == "PAID")
        adjustment = (
            db.query(CommissionPayment)
            .filter(CommissionPayment.id != original_id)
            .one()
        )
        assert adjustment.amount == -600 and adjustment.status.value == "PENDING"
        audit = db.query(SaleEvent).filter(SaleEvent.kind == "CORRECTED").one()
        assert audit.actor_id == data.manager and audit.reason == payload["reason"]
        assert Decimal(audit.before_data["sale_price"]) == Decimal("200000.01")
        assert Decimal(audit.after_data["sale_price"]) == 150000
        assert adjustment.event_id == audit.id
    assert client.get("/commissions/pending").json()[0]["total_pending"] == (
        -600 if status == "PAID" else 1800
    )
    summary = client.get("/commissions/summary").json()
    assert summary["total"] == 1800
    assert (
        client.post(f"/sales/{sale_id}/correct", json=payload).json()["replayed"]
        is True
    )
    assert client.get(f"/sales/{sale_id}").json()["sale"]["version"] == 2


@pytest.mark.parametrize("actor", ["agent", "manager", "admin"])
@pytest.mark.parametrize(
    "target",
    [
        "CAPTADA",
        "PUBLICADA",
        "EN_VISITAS",
        "RESERVADA",
        "PENDIENTE_NOTARIA",
        "RETIRADA",
    ],
)
def test_reopen_reverses_commission_and_can_close_again(data, actor, target):
    from app.models.commissions import CommissionPayment
    from app.models.properties import Property
    from app.models.transactions import Sale
    from scripts.audit_sales import audit_sales

    sale_id = close(data)
    seed_status(data, "PAID")
    client = data.client(actor)
    payload = reopening(target_status=target)
    response = client.post(f"/sales/{sale_id}/reopen", json=payload)
    assert response.status_code == 200, response.text
    assert (
        client.post(f"/sales/{sale_id}/reopen", json=payload).json()["replayed"] is True
    )
    with data.env.sessions() as db:
        old_sale = db.get(Sale, UUID(sale_id))
        assert not old_sale.is_active and old_sale.reopened_at is not None
        assert db.get(Property, data.property).status.value == target
        assert sum(c.amount for c in db.query(CommissionPayment).all()) == 0
    assert client.get("/properties/sales/list").json()["total"] == 0
    assert client.get("/properties/sales/list?state=reopened").json()["total"] == 1
    manager = data.client()
    assert manager.get("/properties/stats/summary").json()["total_sales"] == 0
    assert manager.get("/properties/stats/summary").json()["total_revenue"] == 0
    assert manager.get("/reports/kpi-summary").json()["sales_count"] == 0
    assert manager.get("/reports/top-sales").json() == []
    assert manager.get("/commissions/pending").json()[0]["total_pending"] == -2400
    new_close = client.post(
        data.url,
        json={**data.payload, "request_id": str(uuid4()), "sale_price": "300000"},
    )
    assert new_close.status_code == 200, new_close.text
    assert new_close.json()["sale_id"] != sale_id
    assert client.get("/properties/sales/list?state=all").json()["total"] == 2
    assert manager.get("/commissions/pending").json()[0]["total_pending"] == 1200
    with data.env.engine.connect() as conn:
        assert all(not rows for rows in audit_sales(conn).values())


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("agent", 200),
        ("manager", 200),
        ("admin", 200),
        ("colleague", 404),
        ("outsider", 404),
        ("superadmin", 403),
    ],
)
def test_revision_permissions(data, actor, expected):
    sale_id = close(data)
    client = data.client(actor)
    assert client.get(f"/sales/{sale_id}").status_code == expected
    response = client.post(f"/sales/{sale_id}/correct", json=correction(data))
    assert response.status_code == expected, response.text


def test_agent_change_reverses_old_agent_and_credits_new_agent(data):
    sale_id = close(data)
    seed_status(data, "PAID")
    client = data.client()
    payload = correction(data, agent_id=str(data.colleague), agent_commission_rate="50")
    assert client.post(f"/sales/{sale_id}/correct", json=payload).status_code == 200
    groups = {g["agent_id"]: g for g in client.get("/commissions/pending").json()}
    assert groups[str(data.agent)]["total_pending"] == -2400
    assert groups[str(data.colleague)]["total_pending"] == 2250
    assert (
        client.post(
            f"/sales/{sale_id}/reopen", json=reopening(expected_version=2)
        ).status_code
        == 200
    )
    groups = {g["agent_id"]: g for g in client.get("/commissions/pending").json()}
    assert groups[str(data.colleague)]["total_pending"] == 0
    assert groups[str(data.agent)]["total_pending"] == -2400


def test_stale_conflicting_and_invalid_changes_are_rejected(data):
    sale_id = close(data)
    client = data.client()
    url = f"/sales/{sale_id}/correct"
    payload = correction(data)
    for change in (
        {"reason": " "},
        {"sale_date": "2026-01-01"},
        {"sale_price": "0"},
        {"commission_rate": "101"},
        {"buyer_id": str(data.other_buyer)},
        {"agent_id": str(data.outsider)},
    ):
        assert client.post(url, json={**payload, **change}).status_code == 422
    assert (
        client.post(
            f"/sales/{sale_id}/reopen", json=reopening(target_status="VENDIDA")
        ).status_code
        == 422
    )
    assert client.post(url, json=payload).status_code == 200
    assert client.post(url, json={**payload, "sale_price": "100000"}).status_code == 409
    assert client.post(url, json=correction(data)).status_code == 409
    assert client.post(f"/sales/{sale_id}/reopen", json=reopening()).status_code == 409
    assert (
        client.post(
            f"/sales/{sale_id}/reopen", json=reopening(expected_version=2)
        ).status_code
        == 200
    )
    assert (
        client.post(url, json=correction(data, expected_version=3)).status_code == 409
    )


def test_agent_cannot_replace_buyer_or_agent_outside_access(data):
    sale_id = close(data)
    client = data.client("agent")
    for changes in (
        {"buyer_id": str(data.colleague_buyer)},
        {"agent_id": str(data.colleague)},
    ):
        assert (
            client.post(
                f"/sales/{sale_id}/correct", json=correction(data, **changes)
            ).status_code
            == 422
        )


@pytest.mark.parametrize("action", ["correct", "reopen"])
def test_revision_csrf_is_required(data, action):
    sale_id = close(data)
    client = data.client()
    client.headers.pop("X-CSRF-Token")
    payload = correction(data) if action == "correct" else reopening()
    assert client.post(f"/sales/{sale_id}/{action}", json=payload).status_code == 403


def test_failure_rolls_back_sale_property_event_and_adjustment(data):
    from app.models.commissions import CommissionPayment
    from app.models.properties import Property
    from app.models.transactions import Sale, SaleEvent

    sale_id = close(data)

    def fail(*args):
        raise RuntimeError("Adjustment storage failed")

    event.listen(CommissionPayment, "before_insert", fail)
    try:
        response = data.client(raise_server_exceptions=False).post(
            f"/sales/{sale_id}/reopen", json=reopening()
        )
        assert response.status_code == 500
    finally:
        event.remove(CommissionPayment, "before_insert", fail)
    with data.env.sessions() as db:
        assert db.get(Sale, UUID(sale_id)).is_active
        assert db.get(Sale, UUID(sale_id)).version == 1
        assert db.get(Property, data.property).status.value == "VENDIDA"
        assert db.query(SaleEvent).count() == db.query(CommissionPayment).count() == 1


def test_concurrent_correction_and_reopen_only_apply_one(data):
    from app.models.commissions import CommissionPayment
    from app.models.transactions import Sale, SaleEvent

    sale_id = close(data)
    clients = [data.client(), data.client()]
    barrier = Barrier(2)

    def run(index):
        barrier.wait(timeout=10)
        action = "correct" if index == 0 else "reopen"
        payload = correction(data) if index == 0 else reopening()
        return (
            clients[index].post(f"/sales/{sale_id}/{action}", json=payload).status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [0, 1])) == [200, 409]
    with data.env.sessions() as db:
        sale = db.get(Sale, UUID(sale_id))
        assert sale.version == 2 and db.query(SaleEvent).count() == 2
        assert sum(c.amount for c in db.query(CommissionPayment).all()) == (
            sale.agent_commission if sale.is_active else 0
        )


@pytest.mark.parametrize("status", ["PENDING", "INVOICED", "PAID"])
def test_net_settlement_and_retries(data, status):
    from app.models.commissions import CommissionPayment, CommissionSettlement

    sale_id = close(data)
    original = seed_status(data, status)
    client = data.client()
    stale_group = client.get("/commissions/pending").json()
    assert (
        client.post(f"/sales/{sale_id}/correct", json=correction(data)).status_code
        == 200
    )
    url = f"/commissions/agents/{data.agent}/settle"
    if stale_group:
        assert client.post(url, json=settle_payload(stale_group[0])).status_code == 409
    group = client.get("/commissions/pending").json()[0]
    payload = settle_payload(group)
    response = client.post(url, json=payload)
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["amount"]) == (-600 if status == "PAID" else 1800)
    assert client.post(url, json=payload).json()["replayed"] is True
    assert client.post(url, json={**payload, "notes": "changed"}).status_code == 409
    assert client.post(url, json=settle_payload(group)).status_code == 409
    assert client.get("/commissions/pending").json() == []
    with data.env.sessions() as db:
        assert db.query(CommissionSettlement).count() == 1
        cp = db.get(CommissionPayment, original)
        assert cp.invoice_number == "ORIGINAL-2026" and cp.notes == "Original document"
        if status == "PAID":
            assert cp.payment_date == datetime(2026, 1, 1, tzinfo=timezone.utc)
            assert cp.settlement_id is None
        assert sum(c.amount for c in db.query(CommissionPayment).all()) == 1800


def test_new_sale_is_paid_net_of_previous_overpayment(data):
    sale_id = close(data)
    seed_status(data, "PAID")
    client = data.client()
    assert client.post(f"/sales/{sale_id}/reopen", json=reopening()).status_code == 200
    assert (
        client.post(
            data.url,
            json={**data.payload, "request_id": str(uuid4()), "sale_price": "300000"},
        ).status_code
        == 200
    )
    group = client.get("/commissions/pending").json()[0]
    assert group["total_pending"] == 1200
    response = client.post(
        f"/commissions/agents/{data.agent}/settle", json=settle_payload(group)
    )
    assert response.status_code == 200 and Decimal(response.json()["amount"]) == 1200
    assert client.get("/commissions/summary").json()["paid"] == 3600


def test_invoice_entry_and_settlement_authorization(data):
    sale_id = close(data)
    client = data.client()
    group = client.get("/commissions/pending").json()[0]
    entry = group["commissions"][0]
    invoice_url = f"/commissions/entries/{entry['id']}/invoice"
    assert data.client("agent").post(invoice_url, json={}).status_code == 403
    assert data.client("outsider").post(invoice_url, json={}).status_code == 404
    assert client.post(invoice_url, json={"invoice_number": "INV-1"}).status_code == 200
    assert client.post(invoice_url, json={"invoice_number": "INV-2"}).status_code == 409
    url = f"/commissions/agents/{data.agent}/settle"
    assert client.post(url, json=settle_payload(group)).status_code == 409
    group = client.get("/commissions/pending").json()[0]
    assert data.client("agent").post(url, json=settle_payload(group)).status_code == 403
    assert (
        data.client("outsider").post(url, json=settle_payload(group)).status_code == 409
    )
    assert client.post(f"/commissions/{sale_id}/pay", json={}).status_code == 409
    client.headers.pop("X-CSRF-Token")
    assert client.post(url, json=settle_payload(group)).status_code == 403


def test_concurrent_settlement_and_correction_keep_economic_identity(data):
    from app.models.commissions import CommissionPayment, CommissionStatus

    sale_id = close(data)
    clients = [data.client(), data.client()]
    group = clients[0].get("/commissions/pending").json()[0]
    barrier = Barrier(2)

    def run(index):
        barrier.wait(timeout=10)
        if index == 0:
            return (
                clients[index]
                .post(f"/sales/{sale_id}/correct", json=correction(data))
                .status_code
            )
        return (
            clients[index]
            .post(
                f"/commissions/agents/{data.agent}/settle", json=settle_payload(group)
            )
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [0, 1]))
    assert results[0] == 200 and results[1] in (200, 409)
    with data.env.sessions() as db:
        entries = db.query(CommissionPayment).all()
        assert sum(c.amount for c in entries) == 1800
        paid = sum(c.amount for c in entries if c.status == CommissionStatus.PAID)
        pending = sum(c.amount for c in entries if c.status != CommissionStatus.PAID)
        assert (paid, pending) in ((2400, -600), (0, 1800))


@pytest.mark.parametrize("action", ["correct", "reopen"])
def test_concurrent_retries_create_one_revision(data, action):
    from app.models.transactions import SaleEvent

    sale_id = close(data)
    clients = [data.client(), data.client()]
    payload = correction(data) if action == "correct" else reopening()
    barrier = Barrier(2)

    def run(index):
        barrier.wait(timeout=10)
        response = clients[index].post(f"/sales/{sale_id}/{action}", json=payload)
        assert response.status_code == 200, response.text
        return response.json()["replayed"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [0, 1])) == [False, True]
    with data.env.sessions() as db:
        assert db.query(SaleEvent).count() == 2


def test_repeated_corrections_use_current_entitlement_and_allow_zero(data):
    from app.models.commissions import CommissionPayment

    sale_id = close(data)
    client = data.client()
    for version, price, rate, expected in (
        (1, "150000", "3", 1800),
        (2, "300000", "3", 3600),
        (3, "300000", "0", 0),
    ):
        payload = correction(
            data, expected_version=version, sale_price=price, commission_rate=rate
        )
        assert client.post(f"/sales/{sale_id}/correct", json=payload).status_code == 200
        with data.env.sessions() as db:
            assert (
                sum(cp.amount for cp in db.query(CommissionPayment).all()) == expected
            )
    group = client.get("/commissions/pending").json()[0]
    assert group["total_pending"] == 0
    response = client.post(
        f"/commissions/agents/{data.agent}/settle", json=settle_payload(group)
    )
    assert response.status_code == 200 and Decimal(response.json()["amount"]) == 0


def test_legacy_missing_commission_is_reconciled_without_inventing_payment(data):
    from app.models.commissions import CommissionPayment
    from app.models.transactions import SaleEvent

    sale_id = close(data)
    with data.env.sessions() as db:
        db.query(CommissionPayment).delete()
        db.query(SaleEvent).delete()
        db.commit()
    client = data.client()
    assert (
        client.post(f"/sales/{sale_id}/correct", json=correction(data)).status_code
        == 200
    )
    with data.env.sessions() as db:
        cp = db.query(CommissionPayment).one()
        assert cp.amount == 1800 and cp.status.value == "PENDING"
        assert cp.payment_date is None
        audit = db.query(SaleEvent).one()
        assert Decimal(audit.before_data["agent_commission"]) == 2400


def test_downgrade_refuses_to_erase_sale_history(data):
    import subprocess
    import sys

    from sqlalchemy import text

    close(data)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "f002a1b2c3d4"],
        cwd=data.env.backend,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Sale history exists" in result.stderr
    with data.env.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            == "f003a1b2c3d4"
        )
        assert conn.execute(text("SELECT count(*) FROM sale_events")).scalar() == 1
