"""Per-client dashboard bearer-token auth. Naib has no user-account system
yet -- onboarding (naib.onboarding) is operator-run, no self-serve signup --
so this is the minimum real access control the security one-pager can
honestly claim: a random per-client secret (Client.dashboard_token), issued
at onboarding and checked on every dashboard/API route that touches that
client's data, instead of "anyone who has the client_id can see and act on
everything." Not a general auth system; scoped precisely to what exists
today. Swap for real SSO/user accounts whenever Phase 9's second client
makes that worth building.
"""

import secrets
import uuid

from fastapi import Header, HTTPException
from sqlmodel import select

from naib.store.db import get_sessionmaker
from naib.store.models import Approval, Client, FollowUp, Lead, Proposal


def _extract_bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="missing or malformed Authorization header"
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401, detail="missing or malformed Authorization header"
        )
    return token


def _check_token(token: str, client: Client | None) -> None:
    if client is None:
        raise HTTPException(status_code=404, detail="unknown client_id")
    if not secrets.compare_digest(token, client.dashboard_token):
        raise HTTPException(status_code=401, detail="invalid dashboard token")


async def require_client_token(
    client_id: uuid.UUID, authorization: str | None = Header(default=None)
) -> None:
    """Dependency for routes with a `{client_id}` path param."""

    token = _extract_bearer_token(authorization)
    async with get_sessionmaker()() as session:
        client = (await session.exec(select(Client).where(Client.id == client_id))).first()
    _check_token(token, client)


async def require_client_token_for_lead(
    lead_id: uuid.UUID, authorization: str | None = Header(default=None)
) -> None:
    """Dependency for routes with a `{lead_id}` path param (the trace
    endpoint) -- resolves the lead's client first, then checks the token
    the same way."""

    token = _extract_bearer_token(authorization)
    async with get_sessionmaker()() as session:
        lead = (await session.exec(select(Lead).where(Lead.id == lead_id))).first()
        if lead is None:
            raise HTTPException(status_code=404, detail="unknown lead_id")
        client = (await session.exec(select(Client).where(Client.id == lead.client_id))).first()
    _check_token(token, client)


async def require_client_token_for_approval(
    approval_id: uuid.UUID, authorization: str | None = Header(default=None)
) -> None:
    """Dependency for `/approvals/{approval_id}/decide` -- an approval has
    no client_id of its own, so this walks entity_type/entity_id down to
    the proposal (or the followup's proposal) to find the owning lead,
    then the client."""

    token = _extract_bearer_token(authorization)
    async with get_sessionmaker()() as session:
        approval = await session.get(Approval, approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="unknown approval_id")

        lead_id: uuid.UUID | None = None
        if approval.entity_type == "proposal":
            proposal = await session.get(Proposal, approval.entity_id)
            lead_id = proposal.lead_id if proposal else None
        elif approval.entity_type == "followup":
            followup = await session.get(FollowUp, approval.entity_id)
            if followup is not None:
                proposal = await session.get(Proposal, followup.proposal_id)
                lead_id = proposal.lead_id if proposal else None

        if lead_id is None:
            raise HTTPException(
                status_code=404, detail="could not resolve approval to a client"
            )
        lead = await session.get(Lead, lead_id)
        client = await session.get(Client, lead.client_id) if lead is not None else None
    _check_token(token, client)
