"""Plugin job runner — executes registered plugins via the SDK contract."""

from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.job_ops import renew_lease, transition
from app.jobs.sample import JobCancelled, JobTimedOut, _check_cancel_or_timeout
from app.logging import get_logger
from app.models import FileObject, GenerationJob
from app.states import InvalidTransitionError, JobStatus
from app.storage import put_bytes

log = get_logger("plugin-runner")


async def _load_registry_entry(
    session: AsyncSession,
    plugin_id: str,
    version: str | None,
) -> dict | None:
    """Load plugin_registry row without a full ORM model dependency."""
    from sqlalchemy import text

    if version:
        result = await session.execute(
            text(
                "SELECT plugin_id, version, source_path, entrypoint, timeout_seconds, "
                "memory_mb, network_policy, max_output_bytes, outputs, enabled, status "
                "FROM plugin_registry "
                "WHERE plugin_id = :pid AND version = :ver"
            ),
            {"pid": plugin_id, "ver": version},
        )
    else:
        result = await session.execute(
            text(
                "SELECT plugin_id, version, source_path, entrypoint, timeout_seconds, "
                "memory_mb, network_policy, max_output_bytes, outputs, enabled, status "
                "FROM plugin_registry "
                "WHERE plugin_id = :pid AND enabled = true AND status = 'active' "
                "ORDER BY string_to_array(version, '.')::int[] DESC NULLS LAST "
                "LIMIT 1"
            ),
            {"pid": plugin_id},
        )
    row = result.mappings().first()
    return dict(row) if row else None


async def run_plugin_job(
    session: AsyncSession,
    job: GenerationJob,
    *,
    worker_id: str,
) -> None:
    """Execute a registered plugin for a claimed generation job."""
    import time

    from modumesh_plugin_sdk.errors import (
        ContractError,
        PluginSecurityError,
        PluginTimeoutError,
    )
    from modumesh_plugin_sdk.manifest import load_plugin_directory
    from modumesh_plugin_sdk.runner import enforce_declared_outputs, run_plugin_subprocess

    started = time.monotonic()

    async def gate() -> None:
        await _check_cancel_or_timeout(
            session, job, worker_id=worker_id, started_monotonic=started
        )

    try:
        await gate()

        entry = await _load_registry_entry(session, job.job_type, job.plugin_version)
        if entry is None:
            raise ContractError(
                f"Plugin '{job.job_type}'"
                + (f"@{job.plugin_version}" if job.plugin_version else "")
                + " not found in registry"
            )
        if not entry.get("enabled") or entry.get("status") != "active":
            raise ContractError(
                f"Plugin '{job.job_type}@{entry.get('version')}' is disabled or inactive"
            )

        source_path = Path(entry["source_path"])
        # Prefer configured plugin_dir sibling if the stored path is missing
        # (e.g. different container mount layout).
        if not source_path.is_dir():
            alt = Path(settings.worker.plugin_dir) / job.job_type
            if alt.is_dir():
                source_path = alt

        plugin = load_plugin_directory(source_path)
        if job.plugin_version and plugin.version != job.plugin_version:
            raise ContractError(
                f"Plugin version mismatch: job={job.plugin_version} disk={plugin.version}"
            )

        job.progress_pct = 15
        job.progress_message = f"running plugin {plugin.plugin_id}@{plugin.version}"
        job.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await renew_lease(session, job, worker_id)
        await gate()

        with tempfile.TemporaryDirectory(prefix=f"modumesh-{job.id}-") as tmp:
            work_dir = Path(tmp)
            # Plugin source is read-only: we never write into source_path.
            # Execution happens in a sanitized subprocess (no DB/storage creds).
            result = run_plugin_subprocess(
                plugin,
                job_id=str(job.id),
                input_payload=dict(job.input_payload or {}),
                work_dir=work_dir,
                timeout_seconds=min(job.timeout_seconds, plugin.timeout_seconds),
            )
            enforce_declared_outputs(plugin, result.outputs)

            await gate()
            await transition(
                session,
                job,
                JobStatus.VALIDATING,
                worker_id=worker_id,
                progress_pct=60,
                progress_message="validating plugin outputs",
            )

            for output in result.outputs:
                if not output.absolute_path.is_file():
                    raise PluginSecurityError(
                        f"Missing output file {output.relative_path}"
                    )
                if not str(output.absolute_path.resolve()).startswith(
                    str(work_dir.resolve())
                ):
                    raise PluginSecurityError(
                        f"Output path escapes job directory: {output.relative_path}"
                    )

            await gate()
            await transition(
                session,
                job,
                JobStatus.UPLOADING,
                worker_id=worker_id,
                progress_pct=80,
                progress_message="uploading plugin outputs",
            )

            for output in result.outputs:
                data = output.absolute_path.read_bytes()
                stored = put_bytes(
                    project_id=job.project_id,
                    job_id=job.id,
                    filename=output.relative_path,
                    data=data,
                    content_type=output.media_type or "application/octet-stream",
                )
                session.add(
                    FileObject(
                        id=uuid.uuid4(),
                        project_id=job.project_id,
                        job_id=job.id,
                        object_key=stored.object_key,
                        filename=output.relative_path,
                        content_type=stored.content_type,
                        size_bytes=stored.size_bytes,
                        sha256=stored.sha256,
                    )
                )
            await session.flush()
            await gate()

            await transition(
                session,
                job,
                JobStatus.COMPLETED,
                worker_id=worker_id,
                progress_pct=100,
                progress_message="completed",
            )

    except JobCancelled:
        await session.refresh(job)
        if job.status not in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            try:
                await transition(
                    session,
                    job,
                    JobStatus.CANCELLED,
                    worker_id=worker_id,
                    progress_message="cancelled by request",
                )
            except InvalidTransitionError:
                pass

    except (JobTimedOut, PluginTimeoutError) as exc:
        await session.refresh(job)
        if job.status not in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            try:
                await transition(
                    session,
                    job,
                    JobStatus.FAILED,
                    worker_id=worker_id,
                    progress_message="timed out",
                    error_message=str(exc),
                )
            except InvalidTransitionError:
                pass

    except (PluginSecurityError, ContractError) as exc:
        await session.refresh(job)
        if job.status not in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            try:
                await transition(
                    session,
                    job,
                    JobStatus.FAILED,
                    worker_id=worker_id,
                    progress_message="plugin contract failure",
                    error_message=str(exc),
                )
            except InvalidTransitionError:
                pass

    except Exception as exc:
        await session.refresh(job)
        if job.status not in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            try:
                await transition(
                    session,
                    job,
                    JobStatus.FAILED,
                    worker_id=worker_id,
                    progress_message="failed",
                    error_message=str(exc),
                )
            except InvalidTransitionError:
                pass
        else:
            raise
