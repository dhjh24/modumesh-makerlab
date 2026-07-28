"""Phase 2: users, projects, generation_jobs, files, audit_events."""

from __future__ import annotations

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_projects_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "job_type",
            sa.String(length=64),
            server_default=sa.text("'sample'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'created'"),
            nullable=False,
        ),
        sa.Column(
            "input_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("progress_pct", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("progress_message", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("attempt_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), server_default=sa.text("60"), nullable=False),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
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
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ("
            "'created','queued','running','validating','uploading',"
            "'completed','failed','cancelled'"
            ")",
            name="ck_generation_jobs_status",
        ),
        sa.CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100", name="ck_jobs_progress"
        ),
        sa.CheckConstraint("attempt_number >= 1", name="ck_jobs_attempt"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_job_id"], ["generation_jobs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_jobs_project_id", "generation_jobs", ["project_id"])
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])
    op.create_index(
        "ix_generation_jobs_parent_job_id", "generation_jobs", ["parent_job_id"]
    )
    op.create_index(
        "ix_generation_jobs_lease_expires_at", "generation_jobs", ["lease_expires_at"]
    )
    op.create_index(
        "uq_jobs_project_idempotency",
        "generation_jobs",
        ["project_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=128),
            server_default=sa.text("'application/octet-stream'"),
            nullable=False,
        ),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["generation_jobs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_files_project_id", "files", ["project_id"])
    op.create_index("ix_files_job_id", "files", ["job_id"])
    op.create_index("ix_files_sha256", "files", ["sha256"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"]
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    # Default local owner placeholder for Phase 2 (no auth yet).
    op.execute(
        sa.text(
            "INSERT INTO users (id, external_id, display_name) "
            "VALUES ("
            "'00000000-0000-4000-8000-000000000001'::uuid, "
            "'local-default', "
            "'Local Owner'"
            ")"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_files_sha256", table_name="files")
    op.drop_index("ix_files_job_id", table_name="files")
    op.drop_index("ix_files_project_id", table_name="files")
    op.drop_table("files")

    op.drop_index("uq_jobs_project_idempotency", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_lease_expires_at", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_parent_job_id", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_project_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")

    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")

    op.drop_table("users")
