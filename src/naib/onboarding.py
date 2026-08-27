"""Phase 8 onboarding flow: validate and install a real playbook, validate
a client's ICP config, create the `Client` row, and hand back the exact
webhook URLs to wire up at each channel provider. See PLAN.md Phase 8
'Build': 'Onboarding flow: ICP config, playbook import, channel
connection.'

Judgment call: naib.playbook loads from one bundled file
(naib/data/playbook.json), not a per-client table -- PLAN.md Phase 9 is
explicit: 'Do not build multi-tenant abstractions before client two.'
Onboarding a second real client is exactly the trigger PLAN.md names for
revisiting that. Until then, one global playbook file *is* the correct
scope, and this module installs into it rather than inventing a table
nothing else reads yet. Channel *credentials* (a client's own Twilio
number, WhatsApp Business account) are the same story -- naib.settings
holds one set, shared by the single agency Phase 8 is built for.
"""

import json
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from naib.playbook import load_playbook
from naib.schemas.icp_config import ICPConfig
from naib.schemas.playbook_entry import PlaybookEntry
from naib.store.db import get_sessionmaker
from naib.store.models import Client


@dataclass
class ChannelSetup:
    email_webhook: str
    whatsapp_webhook: str
    form_webhook: str
    voice_incoming_webhook: str


def validate_playbook(path: Path) -> list[PlaybookEntry]:
    """Schema-checks a playbook file and refuses placeholder rows -- see
    naib.playbook's own docstring on why is_placeholder exists at all."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = [PlaybookEntry.model_validate(entry) for entry in raw]
    if not entries:
        raise ValueError(f"{path} has no playbook entries.")

    placeholder_ids = [e.id for e in entries if e.is_placeholder]
    if placeholder_ids:
        raise ValueError(
            "Refusing to onboard a real client on placeholder playbook entries: "
            f"{placeholder_ids}. Replace them with real services and pricing first "
            "(PLAN.md Phase 1 [YOU])."
        )
    return entries


def install_playbook(entries: list[PlaybookEntry]) -> None:
    dest = resources.files("naib.data").joinpath("playbook.json")
    payload = json.dumps([entry.model_dump() for entry in entries], indent=2)
    dest.write_text(payload, encoding="utf-8")  # type: ignore[attr-defined]
    load_playbook.cache_clear()


def validate_icp_config(path: Path) -> ICPConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ICPConfig.model_validate(raw)


def describe_channel_setup(client_id: uuid.UUID, *, base_url: str) -> ChannelSetup:
    """The webhook URLs a client hands to their email/WhatsApp/form/Twilio
    provider during onboarding. `base_url` is the deployed API's public
    origin -- there's no default because guessing wrong here is a silent
    failure (leads that never arrive), not a loud one."""

    return ChannelSetup(
        email_webhook=f"{base_url}/webhooks/email",
        whatsapp_webhook=f"{base_url}/webhooks/whatsapp",
        form_webhook=f"{base_url}/webhooks/form",
        voice_incoming_webhook=f"{base_url}/webhooks/voice/{client_id}/incoming",
    )


async def onboard_client(
    *,
    name: str,
    plan: str,
    icp_config: ICPConfig,
    playbook_version: str,
    price_floor: int = 0,
) -> Client:
    """Creates the Client row. Callers are expected to have already run
    validate_playbook/install_playbook and validate_icp_config -- this
    function trusts icp_config is already validated and does not touch the
    playbook file itself, so it stays testable without filesystem writes."""

    async with get_sessionmaker()() as session:
        client = Client(
            name=name,
            plan=plan,
            icp_config=icp_config.model_dump(),
            playbook_version=playbook_version,
            price_floor=price_floor,
        )
        session.add(client)
        await session.commit()
        await session.refresh(client)
        return client
