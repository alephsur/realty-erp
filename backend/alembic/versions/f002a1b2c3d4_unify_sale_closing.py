"""Store exact amounts and sale-closing provenance without rewriting legacy sales.

Revision ID: f002a1b2c3d4
Revises: d1e2f3a4b5c6
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f002a1b2c3d4"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

AMOUNTS = {
    "sales": (
        "sale_price",
        "total_commission",
        "agent_commission",
        "agency_commission",
    ),
    "commission_payments": ("amount",),
}


def upgrade():
    # Unconstrained NUMERIC preserves legacy decimal representations, including
    # fractions of a cent. New closures explicitly round to cents in the service.
    for table, columns in AMOUNTS.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                type_=sa.Numeric(),
                existing_type=sa.Float(),
                postgresql_using=f"{column}::text::numeric",
            )
    op.add_column("sales", sa.Column("commission_rate", sa.Numeric(7, 4)))
    op.add_column("sales", sa.Column("agent_commission_rate", sa.Numeric(7, 4)))
    op.add_column(
        "sales", sa.Column("closing_request_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("sales", sa.Column("closing_request_hash", sa.String(64)))
    op.add_column("sales", sa.Column("closed_by_id", postgresql.UUID(as_uuid=True)))
    op.add_column("sales", sa.Column("closed_from_status", sa.String(32)))
    op.create_foreign_key(
        "fk_sales_closed_by",
        "sales",
        "users",
        ["closed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_sales_tenant_closing_request", "sales", ["tenant_id", "closing_request_id"]
    )


def downgrade():
    op.drop_constraint("uq_sales_tenant_closing_request", "sales", type_="unique")
    op.drop_constraint("fk_sales_closed_by", "sales", type_="foreignkey")
    for column in (
        "closed_from_status",
        "closed_by_id",
        "closing_request_hash",
        "closing_request_id",
        "agent_commission_rate",
        "commission_rate",
    ):
        op.drop_column("sales", column)
    for table, columns in AMOUNTS.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                type_=sa.Float(),
                existing_type=sa.Numeric(),
                postgresql_using=f"{column}::double precision",
            )
