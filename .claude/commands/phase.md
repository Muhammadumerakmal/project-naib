---
description: Run a build phase from PLAN.md end to end
argument-hint: [phase-number]
allowed-tools: Read, Grep, Glob, Edit, Write, Bash, WebFetch
---

## Context
- Plan: @PLAN.md
- Architecture: @docs/ARCHITECTURE.md
- Constitution: @CLAUDE.md
- Current branch: !`git branch --show-current`
- Working tree: !`git status --short`

## Task

Execute **Phase $1** from `PLAN.md` under the 10-80-10 rhythm.

**First (the 10%):** restate the phase brief in one short paragraph — goal, deliverables,
gate. If something in the phase requires data marked `[YOU]` that is not present in the
repo, say so now and propose how to proceed with a realistic stand-in that is clearly
labelled as such. Then stop for one confirmation.

**Then (the 80%):** build the entire phase without further check-ins.
- Delegate topology decisions to `@agent-architect` before writing agents or tools
- Delegate the tests to `@eval-writer`
- Delegate anything touching untrusted input to `@injection-red-teamer`
- Run `@deployability-reviewer` before you declare the phase done
- Make routine decisions yourself; log them rather than asking

**Finish (the handoff):** report what was built, every judgment call you made and why, the
gate results with actual numbers, what is now in Umer's 10%, and the single riskiest thing
in what you just built.

Do not stop mid-phase to ask whether to continue.
