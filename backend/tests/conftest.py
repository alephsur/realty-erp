"""Real PostgreSQL checks. Opt in with RUN_POSTGRES_TESTS=1; uses its own container."""

import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="module")
def sale_env():
    if os.environ.get("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Set RUN_POSTGRES_TESTS=1 to test with disposable PostgreSQL")
    name = f"realty-sales-test-{uuid4().hex[:10]}"
    patch = pytest.MonkeyPatch()
    engine = None
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                name,
                "--env",
                "POSTGRES_PASSWORD=installation-test",
                "--env",
                "POSTGRES_DB=realty_sales_test",
                "--publish",
                "127.0.0.1::5432",
                "postgres:15-alpine",
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        port = (
            subprocess.check_output(
                [
                    "docker",
                    "port",
                    name,
                    "5432",
                ],
                text=True,
            )
            .strip()
            .split(":")[-1]
        )
        url = f"postgresql://postgres:installation-test@127.0.0.1:{port}/realty_sales_test"
        engine = create_engine(url)
        for attempt in range(50):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                if attempt == 49:
                    raise
                time.sleep(0.2)
        for key, value in {
            "DATABASE_URL": url,
            "SECRET_KEY": "sale-test-secret-with-at-least-32-characters",
            "BOOTSTRAP_SUPERADMIN_EMAIL": "",
            "COOKIE_SECURE": "False",
        }.items():
            patch.setenv(key, value)
        backend = Path(__file__).resolve().parents[1]
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend,
            check=True,
            capture_output=True,
            timeout=30,
        )
        from app.database import get_db
        from app.main import app

        sessions = sessionmaker(bind=engine)

        def test_db():
            with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        yield SimpleNamespace(
            app=app, engine=engine, sessions=sessions, url=url, backend=backend
        )
        app.dependency_overrides.pop(get_db, None)
    finally:
        if engine is not None:
            engine.dispose()
        patch.undo()
        subprocess.run(
            ["docker", "rm", "-f", "-v", name], capture_output=True, timeout=30
        )


@pytest.fixture
def data(sale_env):
    from app.auth.jwt import create_access_token
    from app.models.auth import RoleEnum, Tenant, User
    from app.models.crm import Client, ClientType
    from app.models.properties import Property, PropertyStatus

    with sale_env.engine.begin() as conn:
        conn.execute(text("TRUNCATE tenants, users CASCADE"))
    ids = {
        name: uuid4()
        for name in (
            "tenant",
            "other_tenant",
            "admin",
            "manager",
            "agent",
            "colleague",
            "outsider",
            "superadmin",
            "buyer",
            "other_buyer",
            "colleague_buyer",
            "property",
        )
    }
    users = {}
    with sale_env.sessions() as db:
        db.add_all(
            [
                Tenant(id=ids["tenant"], name="Sales test"),
                Tenant(id=ids["other_tenant"], name="Other agency"),
            ]
        )
        db.flush()
        for name, role in (
            ("admin", RoleEnum.ADMIN),
            ("manager", RoleEnum.MANAGER),
            ("agent", RoleEnum.AGENT),
            ("colleague", RoleEnum.AGENT),
            ("outsider", RoleEnum.MANAGER),
            ("superadmin", RoleEnum.SUPER_ADMIN),
        ):
            tenant_id = ids["other_tenant"] if name == "outsider" else ids["tenant"]
            if name == "superadmin":
                tenant_id = None
            db.add(
                User(
                    id=ids[name],
                    tenant_id=tenant_id,
                    email=f"{name}@example.com",
                    full_name=name,
                    password_hash="unused",
                    role=role,
                    commission_rate=40,
                    is_active=True,
                )
            )
            users[name] = (role, tenant_id)
        db.flush()
        for name, tenant, agent in (
            ("buyer", "tenant", "agent"),
            ("other_buyer", "other_tenant", "outsider"),
            ("colleague_buyer", "tenant", "colleague"),
        ):
            db.add(
                Client(
                    id=ids[name],
                    tenant_id=ids[tenant],
                    agent_id=ids[agent],
                    first_name=name,
                    last_name="Buyer",
                    client_type=ClientType.BUYER,
                )
            )
        db.add(
            Property(
                id=ids["property"],
                tenant_id=ids["tenant"],
                agent_id=ids["agent"],
                title="Test property",
                address="Test address",
                price=200000,
                status=PropertyStatus.CAPTADA,
                commission_rate=3,
            )
        )
        db.commit()

    clients = []

    def client(name="manager", **kwargs):
        role, tenant = users[name]
        token = create_access_token(
            str(ids[name]), role, str(tenant) if tenant else None
        )
        http = TestClient(
            sale_env.app,
            cookies={"access_token": token, "csrf_token": "test"},
            headers={"X-CSRF-Token": "test"},
            **kwargs,
        )
        clients.append(http)
        return http

    payload = {
        "request_id": str(uuid4()),
        "buyer_id": str(ids["buyer"]),
        "agent_id": str(ids["agent"]),
        "sale_price": "200000.01",
        "commission_rate": "3",
        "agent_commission_rate": "40",
        "notes": "Agreed terms",
    }
    yield SimpleNamespace(
        **ids,
        env=sale_env,
        client=client,
        payload=payload,
        url=f"/properties/{ids['property']}/sell",
    )
    for http in clients:
        http.close()
