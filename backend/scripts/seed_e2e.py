"""Minimal browser fixtures. Refuse existing databases and non-E2E destinations."""

import json
import os
import secrets
from pathlib import Path

from app.core.security import get_password_hash
from app.database import SessionLocal, engine
from app.models.auth import RoleEnum, Tenant, User
from app.models.properties import Property


def main():
    name = os.environ.get("E2E_DATABASE_NAME", "")
    if not name.startswith("realty_e2e_") or engine.url.database != name:
        raise RuntimeError(
            "Fixtures require the disposable database created by run_e2e.py"
        )
    output = Path(os.environ["E2E_SEED_PATH"])
    with SessionLocal.begin() as db:
        if db.query(Tenant).first() or db.query(User).first():
            raise RuntimeError("Browser fixtures require an empty database")
        agency = Tenant(name="E2E Realty")
        other = Tenant(name="E2E Other agency")
        db.add_all([agency, other])
        db.flush()
        users = {}
        accounts = {}
        for key, role, tenant, full_name in [
            ("manager", RoleEnum.MANAGER, agency, "Gerente de prueba"),
            ("agent", RoleEnum.AGENT, agency, "Agente de prueba"),
            ("outsider", RoleEnum.AGENT, other, "Agente de otra empresa"),
        ]:
            password = secrets.token_urlsafe(24)
            user = User(
                tenant_id=tenant.id,
                email=f"{key}@example.com",
                full_name=full_name,
                role=role,
                password_hash=get_password_hash(password),
                is_active=True,
                commission_rate=40,
            )
            db.add(user)
            db.flush()
            users[key] = user
            accounts[key] = {
                "id": str(user.id),
                "email": user.email,
                "password": password,
                "name": full_name,
            }
        properties = {}
        for key, title, tenant, user in [
            ("assigned", "Vivienda del agente de prueba", agency, users["agent"]),
            (
                "foreign",
                "Vivienda confidencial de otra empresa",
                other,
                users["outsider"],
            ),
        ]:
            prop = Property(
                tenant_id=tenant.id,
                agent_id=user.id,
                title=title,
                address="Calle de prueba 10",
                price=200000,
                commission_rate=3,
            )
            db.add(prop)
            db.flush()
            properties[key] = {"id": str(prop.id), "title": title}
        output.write_text(json.dumps({"accounts": accounts, "properties": properties}))
        output.chmod(0o600)


if __name__ == "__main__":
    main()
