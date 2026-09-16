"""Read-only inventory of references crossing agency boundaries; never repairs data."""

import json

from sqlalchemy import text

from app.database import engine

# Identifiers are a fixed allowlist, never values supplied by the caller.
REFERENCES = (
    ("properties", "agent_id", "users"),
    ("clients", "agent_id", "users"),
    ("visits", "agent_id", "users"),
    ("visits", "property_id", "properties"),
    ("visits", "client_id", "clients"),
    ("client_property_interests", "client_id", "clients"),
    ("client_property_interests", "property_id", "properties"),
    ("sales", "property_id", "properties"),
    ("sales", "buyer_id", "clients"),
    ("sales", "agent_id", "users"),
    ("commission_payments", "sale_id", "sales"),
    ("commission_payments", "agent_id", "users"),
    ("appointments", "agent_id", "users"),
    ("appointments", "created_by_id", "users"),
    ("notifications", "user_id", "users"),
)


def audit_entity_integrity(connection):
    result = {}
    for table, column, target in REFERENCES:
        query = text(f"""
            SELECT source.id, source.tenant_id, source.{column} AS reference_id
            FROM {table} source LEFT JOIN {target} target
                ON target.id = source.{column}
            WHERE source.{column} IS NOT NULL
              AND (target.id IS NULL
                   OR source.tenant_id IS DISTINCT FROM target.tenant_id)
        """)
        result[f"{table}.{column}"] = [
            dict(row) for row in connection.execute(query).mappings()
        ]
    result["tenant_superadmins"] = [
        dict(row)
        for row in connection.execute(
            text("""
            SELECT id, tenant_id FROM users
            WHERE role = 'SUPER_ADMIN' AND tenant_id IS NOT NULL
        """)
        ).mappings()
    ]
    return result


if __name__ == "__main__":
    with engine.begin() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        findings = audit_entity_integrity(connection)
    print(json.dumps(findings, indent=2, default=str))
    raise SystemExit(1 if any(findings.values()) else 0)
