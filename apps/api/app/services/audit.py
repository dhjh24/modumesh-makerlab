"""Audit event helpers."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def record_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    event = AuditEvent(
        id=uuid.uuid4(),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        details=details or {},
    )
    session.add(event)
    await session.flush()
    return event
