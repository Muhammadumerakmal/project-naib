#!/usr/bin/env python3
"""Block Claude Code from reading or writing secret files.

Hook input arrives as JSON on stdin. Exit 2 to block the tool call;
stderr is shown to Claude so it understands why.
"""
import json
import sys

BLOCKED = (".env", ".env.local", ".env.production", "credentials.json",
           "service-account.json", "id_rsa", ".pem")

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    target = str(
        payload.get("tool_input", {}).get("file_path")
        or payload.get("tool_input", {}).get("path")
        or ""
    )
    if not target:
        return 0

    if any(target.endswith(b) or f"/{b}" in target for b in BLOCKED):
        print(
            f"BLOCKED: {target} holds secrets. Read settings via "
            "pydantic-settings instead, and add any new key to .env.example.",
            file=sys.stderr,
        )
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
