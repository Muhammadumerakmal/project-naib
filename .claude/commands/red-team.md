---
description: Adversarial pass over untrusted-content handling
argument-hint: [component or "all"]
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

Delegate to `@injection-red-teamer` for $1 (default: all untrusted-content paths).

Require: attack corpus extended, every finding either fixed or explicitly accepted with a
written reason, and every newly caught attack added as a permanent test case.

Report findings without softening them. A finding you talked yourself out of is the one
that ships.
