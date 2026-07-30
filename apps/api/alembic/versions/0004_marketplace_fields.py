"""GM-1: Add marketplace fields to plugin_registry (author, license, capabilities, etc.)"""

from __future__ import annotations

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.add_column("plugin_registry", sa.Column("author", sa.String(length=255), nullable=True))
    op.add_column("plugin_registry", sa.Column("license_id", sa.String(length=64), nullable=True))
    op.add_column(
        "plugin_registry",
        sa.Column("license_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "plugin_registry",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "plugin_registry",
        sa.Column("maturity", sa.String(length=32), nullable=False, server_default=sa.text("'experimental'")),
    )
    op.add_column("plugin_registry", sa.Column("tags", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column(
        "plugin_registry",
        sa.Column("thumbnail", sa.String(length=255), nullable=True),
    )
    op.add_column("plugin_registry", sa.Column("capabilities", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
    # Update the status check constraint to include 'quarantined'
    op.drop_constraint("ck_plugin_registry_status", "plugin_registry")
    op.create_check_constraint(
        "ck_plugin_registry_status",
        "plugin_registry",
        sa.text("status IN ('active', 'invalid', 'incompatible', 'duplicate', 'quarantined')"),
    )
    op.create_index("ix_plugin_registry_maturity", "plugin_registry", ["maturity"])
    op.create_index("ix_plugin_registry_license", "plugin_registry", ["license_id"])


def downgrade() -> None:
    op.drop_index("ix_plugin_registry_license", table_name="plugin_registry")
    op.drop_index("ix_plugin_registry_maturity", table_name="plugin_registry")
    op.drop_constraint("ck_plugin_registry_status", "plugin_registry")
    op.create_check_constraint(
        "ck_plugin_registry_status",
        "plugin_registry",
        sa.text("status IN ('active', 'invalid', 'incompatible', 'duplicate')"),
    )
    op.drop_column("plugin_registry", "capabilities")
    op.drop_column("plugin_registry", "thumbnail")
    op.drop_column("plugin_registry", "tags")
    op.drop_column("plugin_registry", "maturity")
    op.drop_column("plugin_registry", "source_url")
    op.drop_column("plugin_registry", "license_url")
    op.drop_column("plugin_registry", "license_id")
    op.drop_column("plugin_registry", "author")
