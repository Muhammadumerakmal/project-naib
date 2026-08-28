"""`uv run python -m naib.cli <command>` -- see CLAUDE.md's Commands
section. Thin argparse wrapper; all real logic lives in naib.replay and
naib.onboarding so it stays unit-testable without going through argv.
"""

import argparse
import asyncio
import uuid
from pathlib import Path

from naib.defensibility_pack import generate_defensibility_pack
from naib.onboarding import (
    describe_channel_setup,
    install_playbook,
    onboard_client,
    validate_icp_config,
    validate_playbook,
)
from naib.replay import replay_lead


def _cmd_replay(args: argparse.Namespace) -> None:
    result = asyncio.run(replay_lead(uuid.UUID(args.lead_id)))
    q = result.qualification
    print(f"qualified={q.qualified} band={q.band} confidence={q.confidence:.2f}")
    print(f"reasons: {'; '.join(q.reasons)}")
    print(f"routing: {result.routing_status}")


def _cmd_onboard(args: argparse.Namespace) -> None:
    entries = validate_playbook(Path(args.playbook))
    icp = validate_icp_config(Path(args.icp))

    async def _run() -> None:
        install_playbook(entries)
        client = await onboard_client(
            name=args.name,
            plan=args.plan,
            icp_config=icp,
            playbook_version=args.playbook_version,
            price_floor=args.price_floor,
        )
        channels = describe_channel_setup(client.id, base_url=args.base_url)
        print(f"client_id={client.id}")
        print(f"Installed {len(entries)} playbook entries (version {args.playbook_version}).")
        print()
        print("Dashboard access -- naib.dashboard_auth gates every dashboard route on this")
        print("token. Hand the client this exact link (or the client_id + token pair, for")
        print("the Landing page's manual fallback); there is no other way in.")
        print(f"  {args.dashboard_url}/clients/{client.id}?token={client.dashboard_token}")
        print(f"  client_id: {client.id}")
        print(f"  token:     {client.dashboard_token}")
        print()
        print("Wire these webhook URLs up at each channel provider:")
        print(f"  email:    {channels.email_webhook}")
        print(f"  whatsapp: {channels.whatsapp_webhook}")
        print(f"  form:     {channels.form_webhook}")
        print(f"  voice:    {channels.voice_incoming_webhook}")

    asyncio.run(_run())


def _cmd_pack(args: argparse.Namespace) -> None:
    pack = asyncio.run(
        generate_defensibility_pack(uuid.UUID(args.client_id), Path(args.output_dir))
    )
    print(f"Wrote {len(pack.files)} files to {pack.output_dir}:")
    for f in pack.files:
        print(f"  {f.name}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="naib")
    subparsers = parser.add_subparsers(dest="command", required=True)

    replay_parser = subparsers.add_parser(
        "replay", help="Re-score an existing lead's stored normalized data and re-route it."
    )
    replay_parser.add_argument("lead_id")
    replay_parser.set_defaults(func=_cmd_replay)

    onboard_parser = subparsers.add_parser(
        "onboard", help="Onboard a new client (PLAN.md Phase 8)."
    )
    onboard_parser.add_argument("--name", required=True)
    onboard_parser.add_argument("--plan", default="pilot")
    onboard_parser.add_argument("--icp", required=True, help="Path to an ICPConfig JSON file.")
    onboard_parser.add_argument("--playbook", required=True, help="Path to a playbook JSON file.")
    onboard_parser.add_argument("--playbook-version", required=True)
    onboard_parser.add_argument("--price-floor", type=int, default=0)
    onboard_parser.add_argument(
        "--base-url",
        required=True,
        help="Deployed API's public origin, e.g. https://naib.example.com",
    )
    onboard_parser.add_argument(
        "--dashboard-url",
        required=True,
        help="Deployed dashboard's public origin, e.g. https://app.naib.example.com",
    )
    onboard_parser.set_defaults(func=_cmd_onboard)

    pack_parser = subparsers.add_parser(
        "pack", help="Generate a per-prospect Defensibility Pack (docs/DEPLOYABILITY.md)."
    )
    pack_parser.add_argument("client_id")
    pack_parser.add_argument("--output-dir", required=True)
    pack_parser.set_defaults(func=_cmd_pack)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
