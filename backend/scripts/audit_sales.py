"""Read-only inventory of legacy closing inconsistencies, before any migration."""

import json

from sqlalchemy import inspect, text

from app.database import engine


def audit_sales(connection):
    checks = {
        "sold_without_sale": """
            SELECT p.id AS property_id, p.tenant_id FROM properties p
            WHERE p.status = 'VENDIDA'
              AND NOT EXISTS (SELECT 1 FROM sales s WHERE s.property_id = p.id)
        """,
        "multiple_sales": """
            SELECT property_id, tenant_id, count(*) AS sales_count FROM sales
            GROUP BY property_id, tenant_id HAVING count(*) > 1
        """,
        "sale_with_open_property": """
            SELECT s.id AS sale_id, s.property_id, s.tenant_id FROM sales s
            JOIN properties p ON p.id = s.property_id WHERE p.status <> 'VENDIDA'
        """,
        "sale_without_commission": """
            SELECT s.id AS sale_id, s.property_id, s.tenant_id FROM sales s
            WHERE NOT EXISTS (
                SELECT 1 FROM commission_payments cp WHERE cp.sale_id = s.id
            )
        """,
    }
    # This inventory also works before the F0-03 migration.
    if "is_active" in {
        column["name"] for column in inspect(connection).get_columns("sales")
    }:
        checks = {
            name: query.replace(
                "FROM sales s", "FROM (SELECT * FROM sales WHERE is_active) s"
            ).replace("FROM sales\n", "FROM sales WHERE is_active\n")
            for name, query in checks.items()
        }
    return {
        name: [dict(row) for row in connection.execute(text(query)).mappings()]
        for name, query in checks.items()
    }


if __name__ == "__main__":
    with engine.connect() as connection:
        print(json.dumps(audit_sales(connection), indent=2, default=str))
