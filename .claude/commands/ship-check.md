---
description: Full pre-merge gate — lint, types, tests, evals, red team, budget
allowed-tools: Bash, Read, Grep, Glob
---

## Context
- Changed files: !`git diff --name-only main...HEAD`
- Branch: !`git branch --show-current`

## Task

Run the ship gate from `docs/EVALS.md` and report a pass/fail table.

```bash
uv run ruff check .
uv run mypy src/
uv run pytest -q
uv run pytest -m eval -q
uv run pytest -m redteam -q
uv run pytest -m budget -q
```

Then verify by inspection, not assumption:
- Every new tool has a permission-tier assertion test
- Every new agent has at least one golden case exercising it
- No golden metric regressed more than 2 points versus main
- Red team failures: must be exactly zero
- No new privileged tool is reachable from an agent that reads untrusted text

For each failure, give the specific fix. Do not summarise failures as "some tests failing" —
name them. If the gate passes, state the current numbers explicitly so they can go in the
client report.
