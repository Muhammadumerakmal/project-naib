"""Read/decide endpoints behind the Phase 7 dashboard. Handlers are thin
wrappers over naib.dashboard / naib.approvals / naib.agents.proposal_pipeline
— see those modules for the actual logic and its tests. Every route below
is gated by naib.dashboard_auth's per-client bearer token — see that
module's docstring for why, and its scope.

Judgment call: dependencies are applied per-route rather than at the
router level. A router-level `dependencies=[...]` also gets applied to
every route later merged in via `include_router()`, and
`/approvals/{approval_id}/decide` has no `{client_id}` in its path — it
needs `require_client_token_for_approval` instead, so a single router-wide
dependency can't cover both cases correctly.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from naib.agents.proposal_pipeline import decide_proposal_approval
from naib.approvals import Decision, get_approval
from naib.autonomy import compute_all_autonomy_status
from naib.dashboard import (
    get_client,
    get_client_metrics,
    list_approval_summaries,
    list_client_escalations,
    reject_or_decide_approval,
    set_kill_switch,
)
from naib.dashboard_auth import require_client_token, require_client_token_for_approval
from naib.schemas.approval_summary import ApprovalSummary
from naib.schemas.autonomy_status import AutonomyStatus
from naib.schemas.client_metrics import ClientMetrics
from naib.store.models import Client, Escalation

router = APIRouter()
_client_auth = Depends(require_client_token)


class ClientDetail(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    autonomy_level: str
    kill_switch: bool


class KillSwitchRequest(BaseModel):
    enabled: bool


class DecideApprovalRequest(BaseModel):
    decided_by: str
    decision: Decision
    edit_diff: str | None = None
    edited_draft_md: str | None = None


def _client_detail(client: Client) -> ClientDetail:
    return ClientDetail(
        id=client.id,
        name=client.name,
        plan=client.plan,
        autonomy_level=client.autonomy_level,
        kill_switch=client.kill_switch,
    )


@router.get("/clients/{client_id}", dependencies=[_client_auth])
async def get_client_detail(client_id: uuid.UUID) -> ClientDetail:
    client = await get_client(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="unknown client_id")
    return _client_detail(client)


@router.post("/clients/{client_id}/kill-switch", dependencies=[_client_auth])
async def toggle_kill_switch(client_id: uuid.UUID, body: KillSwitchRequest) -> ClientDetail:
    client = await set_kill_switch(client_id, enabled=body.enabled)
    return _client_detail(client)


@router.get("/clients/{client_id}/approvals", dependencies=[_client_auth])
async def list_approvals(
    client_id: uuid.UUID, entity_type: str | None = None, pending_only: bool = True
) -> list[ApprovalSummary]:
    return await list_approval_summaries(
        client_id, entity_type=entity_type, pending_only=pending_only
    )


@router.get("/clients/{client_id}/escalations", dependencies=[_client_auth])
async def list_escalations(client_id: uuid.UUID) -> list[Escalation]:
    return await list_client_escalations(client_id)


@router.get("/clients/{client_id}/metrics", dependencies=[_client_auth])
async def client_metrics(client_id: uuid.UUID) -> ClientMetrics:
    return await get_client_metrics(client_id)


@router.get("/clients/{client_id}/autonomy", dependencies=[_client_auth])
async def client_autonomy(client_id: uuid.UUID) -> list[AutonomyStatus]:
    """Where this client stands on graduated autonomy, per action (PLAN.md
    Phase 8). Read-only status — nothing here changes what needs_approval."""

    return await compute_all_autonomy_status(client_id)


@router.post(
    "/approvals/{approval_id}/decide",
    dependencies=[Depends(require_client_token_for_approval)],
)
async def decide_approval_endpoint(
    approval_id: uuid.UUID, body: DecideApprovalRequest
) -> dict[str, str]:
    """Proposals get extra persistence on decide (draft_md/version bump
    when edited) via decide_proposal_approval; every other entity type
    (currently: followups) has nothing beyond the ledger row itself."""

    approval = await get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="unknown approval_id")

    if body.decision == "edited" and body.edited_draft_md is None:
        raise HTTPException(
            status_code=400, detail="edited_draft_md is required when decision is 'edited'"
        )

    if approval.entity_type == "proposal":
        await decide_proposal_approval(
            approval_id,
            decided_by=body.decided_by,
            decision=body.decision,
            edit_diff=body.edit_diff,
            edited_draft_md=body.edited_draft_md,
        )
    else:
        await reject_or_decide_approval(
            approval_id,
            decided_by=body.decided_by,
            decision=body.decision,
            edit_diff=body.edit_diff,
        )

    return {"status": "decided"}
