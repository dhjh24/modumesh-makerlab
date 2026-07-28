"""Initial migration: create schema_migrations tracking table."""

from __future__ import annotations

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "schema_migrations",
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("version"),
    )


def downgrade() -> None:
    op.drop_table("schema_migrations")
