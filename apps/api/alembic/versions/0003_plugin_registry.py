"""Phase 3: plugin registry state + job plugin_version recording."""

from __future__ import annotations

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "plugin_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sdk_version", sa.String(length=32), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("entrypoint", sa.String(length=255), nullable=False),
        sa.Column(
            "categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("memory_mb", sa.Integer(), nullable=False),
        sa.Column(
            "network_policy",
            sa.String(length=32),
            server_default=sa.text("'deny'"),
            nullable=False,
        ),
        sa.Column(
            "input_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_path", sa.String(length=512), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("diagnostics", sa.Text(), nullable=True),
        sa.Column("max_input_bytes", sa.Integer(), nullable=False, server_default=sa.text("65536")),
        sa.Column(
            "max_output_bytes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1048576"),
        ),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invalid', 'incompatible', 'duplicate')",
            name="ck_plugin_registry_status",
        ),
        sa.CheckConstraint(
            "network_policy IN ('deny', 'allow')",
            name="ck_plugin_registry_network",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "version", name="uq_plugin_registry_id_version"),
    )
    op.create_index("ix_plugin_registry_plugin_id", "plugin_registry", ["plugin_id"])
    op.create_index("ix_plugin_registry_enabled", "plugin_registry", ["enabled"])
    op.create_index("ix_plugin_registry_status", "plugin_registry", ["status"])

    op.add_column(
        "generation_jobs",
        sa.Column("plugin_version", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_generation_jobs_job_type_plugin_version",
        "generation_jobs",
        ["job_type", "plugin_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_job_type_plugin_version", table_name="generation_jobs")
    op.drop_column("generation_jobs", "plugin_version")
    op.drop_index("ix_plugin_registry_status", table_name="plugin_registry")
    op.drop_index("ix_plugin_registry_enabled", table_name="plugin_registry")
    op.drop_index("ix_plugin_registry_plugin_id", table_name="plugin_registry")
    op.drop_table("plugin_registry")
