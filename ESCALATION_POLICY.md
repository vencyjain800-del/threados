# ThreadOS — Escalation Policy

Defines the exact boundary between what Claude handles autonomously and what requires
the founder's decision. The goal is a high threshold: Claude escalates rarely, but
escalates without hesitation when the threshold is crossed.

---

## Core Rule

> Claude acts autonomously on anything reversible, low-blast-radius, and within defined
> scope. Claude escalates anything irreversible, ambiguous in scope, or that affects
> security, data integrity, or real user data.

When in doubt: escalate. The cost of an unnecessary escalation is one notification.
The cost of autonomous action in the wrong case can be data loss, a security incident,
or hours of debugging.

---

## Escalation Triggers (stop and escalate immediately)

### Category A — Safety / Security

| Trigger | Why |
|---------|-----|
| Any change to session cookie behaviour, CSRF handling, or login/logout flow not explicitly in the issue spec | Auth bugs can lock all users out |
| Any change that drops a table, column, or RLS policy | Irreversible data loss in production |
| Any change to `threados_migrate` or `threados_app` DB roles or their grants | Privilege escalation risk |
| A credential, API key, secret, or token needs to be added to any file | Secrets must never be in version control |
| Shopify HMAC verification logic is being modified | Disabling webhook verification is a critical vulnerability |
| KMS encryption/decryption logic is being modified | Loss of Shopify access token confidentiality |

### Category B — Scope

| Trigger | Why |
|---------|-----|
| Completing the task requires building something on the out-of-scope list in `MASTER.md` or `ROADMAP.md` | Out-of-scope work may conflict with planned future architecture |
| The issue acceptance criteria are contradictory or incomplete | Guessing produces rework |
| Two valid implementations exist and the choice affects the public API or DB schema | Reversing an API contract is painful |
| The task requires a dependency (DB column, type, endpoint) that does not exist and is not part of this task | Partial implementations leave the system in an inconsistent state |

### Category C — Unexpected State

| Trigger | Why |
|---------|-----|
| Tests were passing at session start but fail after changes and two fix attempts have failed | The bug may be in test infrastructure, not the feature code |
| `test_rls.py` fails after any change | RLS failures mean tenant data isolation may be broken |
| A file is found that appears to be in-progress work from a prior incomplete session | Continuing may overwrite uncommitted intent |
| The codebase structure does not match `MASTER.md` | MASTER.md is stale or the repo was changed outside the automation loop |
| A migration has already been applied to an environment that is not `threados_test` | Rollback requires manual intervention |

### Category D — PR Review Timeout

| Trigger | Why |
|---------|-----|
| An `auto-sprint` PR has been open for 7 days without being merged or closed | Either the founder is blocked or the PR needs changes |
| The founder closed a PR without leaving a comment | Claude cannot determine the next action without knowing the reason |

### Category E — Roadmap Exhaustion

| Trigger | Why |
|---------|-----|
| All items in all roadmap groups are either complete or in-scope for active issues | No task to select; need new direction from the founder |

---

## Autonomous Continuation (do NOT escalate)

These situations are explicitly within Claude's autonomous authority:

| Situation | Action |
|-----------|--------|
| A test Claude wrote is failing due to a bug in Claude's own new code | Fix the code or the test |
| A lint error was introduced by Claude's changes | Fix it immediately |
| A TypeScript error is in a file Claude just edited | Fix it |
| A pre-existing lint warning (not error) is found in an unrelated file | Note it in `PROJECT_STATUS.md` TD table; do not fix it in this sprint |
| A new roadmap item is discovered during implementation (gap, debt, adjacent issue) | Add it to `ROADMAP.md` in the appropriate group; continue |
| A `PROJECT_STATUS.md` entry is stale and can be verified by reading the code | Update it |
| A migration adds a new table or column without removing anything | Proceed |
| The task has only one reasonable implementation given existing codebase patterns | Proceed without asking |
| A GitHub API call fails transiently (5xx, timeout) | Retry once with 5-second delay; escalate on second failure |

---

## Escalation Procedure

### Step 1 — Create a GitHub issue

Open an issue on `vencyjain800-del/threados` with:

```
Title:  [Escalation] {one-line description of the blocker}
Label:  escalation
Assign: founder account
Body:   (see template below)
```

### Step 2 — Stop all work

Do not open a PR. Do not commit partial work. Leave the working directory in a clean
state (all tracked files unchanged, or all changes committed to a local branch named
`escalation/{sprint-N}-{slug}`).

### Step 3 — Report in terminal output

Final line of terminal output must be:

```
ESCALATION REQUIRED — GitHub issue #{number} opened. Awaiting founder decision.
```

---

## Escalation Issue Template

```markdown
## Escalation — Sprint {N}

**Task being worked on:** #{issue_number} — {issue_title}
**File / location:** {file path and line number if applicable}

### What I Was Doing

{One paragraph: the task, the specific step, what action was about to be taken}

### What I Found

{Exact description of the ambiguity, conflict, failure, or unexpected state.
Include error messages verbatim. Include file contents if relevant.}

### Options

**Option A:** {description} — {consequence}
**Option B:** {description} — {consequence}
(max 3 options)

### Decision Needed

{Specific yes/no question or explicit choice the founder must make.
No open-ended questions. One sentence.}

### Current Working Directory State

{List of files changed (if any) and whether they are committed to an escalation branch.
If nothing changed: "No files modified."}
```

---

## Escalation Severity Levels

Not all escalations are equal. Use this to set the founder's expectations:

| Level | Label suffix | When | Expected response time |
|-------|-------------|------|----------------------|
| Critical | `[Escalation][CRITICAL]` | Security issue, data loss risk, RLS failure | Same day |
| Blocking | `[Escalation]` (default) | Cannot proceed without a decision | Within 3 days |
| Advisory | `[Escalation][Advisory]` | Can proceed with a stated assumption; noting for awareness | Within 7 days |

Advisory escalations include Claude's assumed path in the issue body and proceed unless
the founder responds to the contrary within the stated window.

---

## Founder Response Protocol

When the founder responds to an escalation issue:

- **Closing the issue with a comment** = approved, proceed with the clarification
- **Closing the issue without a comment** = ambiguous; Claude re-escalates once requesting
  clarification before proceeding
- **A comment without closing** = Claude reads the guidance, applies it, and closes the issue
  when the sprint that resolves it is complete
- **No response within the expected window** = for Critical/Blocking, Claude re-pings by
  commenting on the issue; for Advisory, Claude proceeds with the stated assumption

---

## What Is Never Escalated

These questions are Claude's to answer without asking:

- Which file to edit for a given change (read the codebase)
- What the correct test name or module path is (read the test suite)
- Which roadmap item to pick when all items at the same priority level are eligible (pick the first one listed)
- Whether to add a new TD entry to `PROJECT_STATUS.md` (always add it; never suppress it)
- What commit message to use (follow the convention in `PR_WORKFLOW.md`)
