"""The approval service — request, queue, decide, capture edit diff. This is
the trust ledger: the most commercially important table in the system. See
CLAUDE.md rule 2 (no agent sends anything, a human approves) and
docs/ARCHITECTURE.md § Data model.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlmodel import select

from naib.store.db import get_sessionmaker
from naib.store.models import Approval

Decision = Literal["approved", "rejected", "edited"]


async def request_approval(*, entity_type: str, entity_id: uuid.UUID, action: str) -> Approval:
    approval = Approval(entity_type=entity_type, entity_id=entity_id, action=action)
    async with get_sessionmaker()() as session:
        session.add(approval)
        await session.commit()
        await session.refresh(approval)
    return approval


async def get_approval(approval_id: uuid.UUID) -> Approval | None:
    async with get_sessionmaker()() as session:
        return await session.get(Approval, approval_id)


async def list_pending(entity_type: str | None = None) -> list[Approval]:
    stmt = select(Approval).where(Approval.decided_at.is_(None))  # type: ignore[union-attr]
    if entity_type is not None:
        stmt = stmt.where(Approval.entity_type == entity_type)
    async with get_sessionmaker()() as session:
        return list((await session.exec(stmt)).all())


async def decide_approval(
    approval_id: uuid.UUID,
    *,
    decided_by: str,
    decision: Decision,
    edit_diff: str | None = None,
) -> Approval:
    """Record a human decision. `edit_diff` is set when `decision` is
    'edited' — it is the training signal for prompt quality and the source
    of the edit-rate metric (docs/ARCHITECTURE.md)."""

    async with get_sessionmaker()() as session:
        approval = await session.get(Approval, approval_id)
        if approval is None:
            raise KeyError(f"No approval with id {approval_id}")
        approval.decided_at = datetime.now(UTC)
        approval.decided_by = decided_by
        approval.decision = decision
        approval.edit_diff = edit_diff
        session.add(approval)
        await session.commit()
        await session.refresh(approval)
        return approval
