"""Track sale revisions and signed commission adjustments.

Revision ID: f003a1b2c3d4
Revises: f002a1b2c3d4
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "f003a1b2c3d4"
down_revision = "f002a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sales",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "sales", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("sales", sa.Column("reopened_at", sa.DateTime(timezone=True)))
    op.create_table(
        "sale_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sale_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("sales.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "actor_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_data", pg.JSONB()),
        sa.Column("after_data", pg.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_sale_events_request"),
        sa.UniqueConstraint("sale_id", "version", name="uq_sale_events_version"),
    )
    op.create_index("ix_sale_events_tenant_id", "sale_events", ["tenant_id"])
    op.create_index("ix_sale_events_sale_id", "sale_events", ["sale_id"])
    op.drop_constraint(
        "commission_payments_sale_id_key", "commission_payments", type_="unique"
    )
    op.create_index(
        "ix_commission_payments_sale_id", "commission_payments", ["sale_id"]
    )
    op.add_column(
        "commission_payments",
        sa.Column(
            "event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("sale_events.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column(
        "commission_payments",
        sa.Column("kind", sa.String(16), nullable=False, server_default="EARNED"),
    )

    op.create_table(
        "commission_settlements",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "agent_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "actor_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("entry_ids", pg.JSONB(), nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invoice_number", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id", "request_id", name="uq_commission_settlement_request"
        ),
    )
    op.add_column(
        "commission_payments",
        sa.Column(
            "settlement_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("commission_settlements.id", ondelete="RESTRICT"),
        ),
    )


def downgrade():
    # Refuse to erase business history once this feature has been used.
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM sale_events) OR EXISTS (SELECT 1 FROM commission_settlements)"
            )
        )
        .scalar()
    ):
        raise RuntimeError(
            "Sale history exists; restore a reviewed backup instead of discarding revisions."
        )
    op.drop_column("commission_payments", "settlement_id")
    op.drop_table("commission_settlements")
    op.drop_column("commission_payments", "kind")
    op.drop_column("commission_payments", "event_id")
    op.drop_index("ix_commission_payments_sale_id", table_name="commission_payments")
    op.create_unique_constraint(
        "commission_payments_sale_id_key", "commission_payments", ["sale_id"]
    )
    op.drop_table("sale_events")
    for column in ("reopened_at", "version", "is_active"):
        op.drop_column("sales", column)
