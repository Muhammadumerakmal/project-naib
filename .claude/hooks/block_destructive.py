#!/usr/bin/env python3
"""Block destructive shell commands. Exit 2 blocks; stderr explains why."""
import json
import re
import sys

PATTERNS = [
    (r"git\s+push\s+.*--force(?!-with-lease)", "Use --force-with-lease."),
    (r"git\s+reset\s+--hard\s+origin", "Destroys local work. Do it manually if intended."),
    (r"\brm\s+-rf\s+/(?!home/|tmp/)", "Refusing rm -rf on a root-level path."),
    (r"DROP\s+(TABLE|DATABASE)", "Schema changes go through a migration, not raw SQL."),
    (r"TRUNCATE\s+agent_events", "agent_events is append-only. This is the audit trail."),
    (r"alembic\s+downgrade\s+base", "Full downgrade wipes the trust ledger."),
]

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    cmd = str(payload.get("tool_input", {}).get("command", ""))
    for pattern, reason in PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            print(f"BLOCKED: {reason}", file=sys.stderr)
            return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
