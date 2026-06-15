# ThreadOS — Agent Workflow

This document defines the exact operating procedure for an AI agent working on this codebase. Follow it in order, every session. Its purpose is to eliminate the need for human coordination on routine tasks.

---

## 0. Principle

**Read before writing. Verify before claiming. Stop before guessing.**

Every section below has a decision point. At each one, either the situation is unambiguous and you continue, or it is not and you escalate. There is no middle path where you continue with a guess.

---

## 1. Startup Procedure

Run at the beginning of every session, before looking at any task.

### 1.1 Load context

Read these files in this order. Do not skip any.

```
MASTER.md                    → architecture, constraints, commands, env vars
PROJECT_STATUS.md            → current feature state, known debt, test baseline
ROADMAP.md                   → prioritised backlog, effort estimates, out-of-scope list
ESCALATION_POLICY.md         → what to escalate vs. handle autonomously
PR_WORKFLOW.md               → how to open PRs at sprint end
```

After reading, confirm:

- Current test count (from `PROJECT_STATUS.md`)
- Current known debt items (TD-xx)
- Any open demo blockers

### 1.2 Verify the working baseline

Run the test suite before touching any code:

```bash
just test
```

Expected: all tests pass, zero failures. If tests are already failing when you start:

→ **Escalate immediately.** Do not proceed with new work on top of a broken baseline. Report which tests fail and stop.

### 1.3 Confirm TypeScript compiles

```bash
cd apps/web && npm run type-check
```

Expected: 0 errors. Same rule applies — do not start new work if the baseline is broken.

---

## 2. Task Selection Procedure

### 2.1 Source of tasks (priority order)

1. **An explicit instruction in the current conversation.** If the user gives a specific task, that task takes full priority. Skip 2.2–2.4.
2. **An open GitHub issue labelled `bug` with severity Critical or High.** Fix these before any roadmap work.
3. **An open GitHub issue labelled `task`.** Pick the highest-priority one (top of the list in the issue tracker).
4. **A roadmap item from `ROADMAP.md`.** Pick the top item in the highest-priority group (Hardening → Observability → Merchant Experience → Platform Integrity).

### 2.2 Read the issue or roadmap item in full

Before writing a single line of code, confirm you can answer all of these:

- What is the exact acceptance criterion?
- What files will change?
- What tests need to be added or updated?
- Does this task depend on another unfinished task?

If any answer is "I don't know", read the relevant source files until you do know, or escalate.

### 2.3 Check dependencies

A task has unsatisfied dependencies if:

- It requires a database column that does not exist yet
- It requires a shared type that is not yet exported from `packages/shared-types/src/index.ts`
- It requires an API endpoint that is not yet implemented
- It requires a previous roadmap item to be complete and that item is not checked off in `PROJECT_STATUS.md`

If a dependency is unsatisfied → **escalate before starting.**

### 2.4 Check scope

Cross-check the task against the out-of-scope list in `ROADMAP.md` and the out-of-scope section of `MASTER.md`.

If the task asks for anything on either out-of-scope list → **escalate immediately.** Do not interpret the task charitably to make it fit.

---

## 3. Implementation Procedure

### 3.1 Understand before changing

Read every file you will modify before making any edit. For each file, identify:

- What the file currently does
- What the minimal change is to satisfy the acceptance criterion
- Whether the change could break existing behaviour elsewhere

Do not refactor, rename, or restructure code that is not directly required by the task. Do not add error handling for scenarios that cannot happen. Do not add comments explaining what code does — only comments explaining why a non-obvious decision was made.

### 3.2 Implementation order

Follow this sequence for every task that touches multiple layers:

1. **Database migration** (if schema changes) — write `upgrade()` and `downgrade()`, verify it runs cleanly
2. **SQLAlchemy model** — update or add model fields
3. **Pydantic schema** — update or add request/response schemas in `services/api/app/schemas/`
4. **Shared TypeScript types** — update `packages/shared-types/src/index.ts`
5. **Backend router** — implement the endpoint or business logic
6. **Backend tests** — happy path + at least one rejection/error case
7. **API client** — update `apps/web/lib/api-client.ts`
8. **Frontend page/component** — implement UI with loading, error, and empty states
9. **TypeScript type-check** — must pass before proceeding to completion

Do not skip steps. Do not reorder steps. If a later step reveals that an earlier step was wrong, fix the earlier step before continuing.

### 3.3 Code constraints (non-negotiable)

These are hard constraints from `MASTER.md`. Violating any one of them is a blocker, not a warning.

| Constraint | Rule |
|-----------|------|
| TypeScript strict mode | `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` — 0 errors |
| No UI libraries | Vanilla Tailwind + inline SVG only. No shadcn, radix, lucide |
| Auth guard | Every auth-required page: `auth.me().catch(() => router.push("/login"))` in `useEffect` |
| Async event handlers | `onClick={() => { void asyncFn(); }}` — never `async () =>` on event props |
| Tenant data | Always `tenant_session(brand_id)`. Never `system_session()` for tenant queries |
| No raw SQL with user input | Always parameterised queries or ORM |
| No silent API errors | Never `catch(() => null)` for errors that affect visible UI |
| `test_rls.py` | Must pass on any change touching DB models, sessions, or multi-tenancy |

### 3.4 After each logical unit of change

After each file or group of related files is changed, run:

```bash
just lint
```

Fix lint errors immediately. Do not accumulate them.

---

## 4. Verification Procedure

Run this full sequence before declaring any work complete. Every command must exit 0.

```bash
# Step 1: Python tests
just test

# Step 2: TypeScript
cd apps/web && npm run type-check

# Step 3: Linting
just lint

# Step 4: RLS isolation (always run when touching DB/auth/models)
cd services/api && uv run pytest tests/test_rls.py -v
```

### Pass criteria

| Check | Required result |
|-------|----------------|
| `just test` | 0 failures; count ≥ baseline from `PROJECT_STATUS.md` |
| `npm run type-check` | 0 errors |
| `just lint` | 0 errors |
| `test_rls.py` | All pass (if DB/auth touched) |

If any check fails, fix the failure before proceeding. Do not move to the completion procedure with a failing check.

---

## 5. Completion Procedure

### 5.1 Update PROJECT_STATUS.md

Update the following sections:

- **Overall State table** — mark newly completed features ✅
- **Test Suite** — update the test count
- **Known Issues / Technical Debt** — add any newly discovered TD items; remove any resolved ones
- **Sprint History** — add a row for the completed sprint with today's date

### 5.2 Write a sprint delivery report

Create `SPRINT_N_DELIVERY.md` using `SPRINT_TEMPLATE.md` as the base. Fill in every section. Do not leave any section blank or marked "N/A" without a reason.

The report must include:
- Objective (one sentence)
- What was in scope and what was explicitly out of scope
- Every file changed and why
- Any API or type changes
- Final test count
- Completed DoD checklist
- Any deferred issues discovered during implementation

### 5.3 Update ROADMAP.md

For each roadmap item completed this sprint:
- Move it to a "Completed" section at the bottom (or delete it if it needs no historical record)
- If new issues were discovered during implementation, add them to the appropriate group with an ID following the existing sequence

### 5.4 Open a GitHub PR

After documentation is complete, open a PR following `PR_WORKFLOW.md` exactly:

1. Confirm the working directory is a git repo with remote `origin` pointing at
   `vencyjain800-del/threados`. If not → **escalate** (do not proceed).
2. `git fetch origin main`
3. `git checkout -b auto-sprint-{N} origin/main`
4. `git add <each changed file by name — never git add .>`
5. `git commit -m "Sprint {N}: {issue title}\n\nIssue: #{number}\nTests: {old} → {new} ({delta:+d})\nFiles: {list}"`
6. `git push -u origin auto-sprint-{N}`
7. Open PR via GitHub API (title, body, labels — see `PR_WORKFLOW.md`)
8. Close the source GitHub issue via API
9. Print the PR URL as the final line of output

If a PR with label `auto-sprint` is already open when this step runs → **do not open another**.
Comment on the existing PR instead: "Sprint {N} complete. Previous PR #X is still open."
Then stop.

### 5.5 Confirm handoff state

Before ending the session, verify:

- `just test` still passes (run again after documentation edits)
- `PROJECT_STATUS.md` reflects current reality
- No uncommitted work-in-progress edits exist (no half-finished changes)
- PR URL has been printed

---

## 6. Escalation Procedure

### 6.1 Always stop and ask when

Stop immediately and ask for human input if any of the following are true. Do not attempt to resolve these autonomously.

**Scope questions:**
- The task is ambiguous about which of two different implementations is correct
- Completing the task requires building something on the out-of-scope list in `MASTER.md` or `ROADMAP.md`
- The acceptance criteria in the issue are contradictory

**Dependency questions:**
- A required database column, type, or API does not exist and is not part of the current task
- The task requires modifying a migration that has already been applied to a non-development environment

**Safety questions:**
- Any change requires credentials, API keys, or secrets to be hardcoded anywhere
- Any change would drop a table, drop a column, or remove an RLS policy
- Any change affects the `threados_migrate` or `threados_app` database roles
- Any change modifies the session cookie behaviour, CSRF token handling, or authentication flow in a way not explicitly requested

**Test failures:**
- Tests were passing at startup but are failing after your changes and you cannot identify why within two focused attempts
- `test_rls.py` fails after your changes for any reason

**Unexpected state:**
- You find a file that looks like in-progress work from a previous session (half-implemented feature, commented-out code blocks, TODO markers with specific implementation notes)
- The codebase structure does not match what `MASTER.md` describes

### 6.2 Continue autonomously when

These situations do not require human input:

- A test you wrote is failing because of a bug in your own new code — fix it
- A lint error was introduced by your changes — fix it
- A TypeScript error is in a file you just edited — fix it
- A new roadmap item needs to be added because you discovered a gap during implementation — add it and continue
- A `PROJECT_STATUS.md` entry is stale and can be verified by reading the current code — update it and continue
- A migration adds a new table or column to an existing schema without removing anything — continue
- A task has only one reasonable implementation given the existing patterns in the codebase — continue without asking

### 6.3 Escalation message format

When escalating, always provide:

1. **What you were doing** — the task, the file, the line
2. **What you found** — the exact ambiguity, conflict, or failure
3. **What the options are** — list the two or more interpretations or paths
4. **What you need** — a specific yes/no decision, a clarification, or explicit authorisation

Do not ask open-ended questions. Do not present more than three options. Do not escalate and then continue working while waiting for a response.

---

## 7. Quick Reference

### Session start checklist

```
[ ] Read MASTER.md
[ ] Read PROJECT_STATUS.md
[ ] Read ROADMAP.md
[ ] just test              → 0 failures
[ ] npm run type-check     → 0 errors
```

### Implementation checklist

```
[ ] Read all files before editing any
[ ] Migration → Model → Schema → Types → Router → Tests → Client → UI
[ ] just lint after each logical unit
[ ] No new features beyond task scope
[ ] No console.log / print() / debug statements
[ ] No catch(() => null) for visible UI
[ ] Loading + error + empty states for all new UI
```

### Completion checklist

```
[ ] just test              → 0 failures, count ≥ baseline
[ ] npm run type-check     → 0 errors
[ ] just lint              → 0 errors
[ ] test_rls.py            → all pass (if DB/auth touched)
[ ] PROJECT_STATUS.md      → updated
[ ] SPRINT_N_DELIVERY.md   → written
[ ] ROADMAP.md             → updated
[ ] just test              → 0 failures (final confirm)
[ ] PR opened (auto-sprint-N branch, PR_WORKFLOW.md)
[ ] Source GitHub issue closed
[ ] PR URL printed as final output
```

### Escalate immediately if

```
[ ] Baseline tests were already failing at session start
[ ] Task requires out-of-scope work
[ ] Required dependency does not exist
[ ] test_rls.py fails after your changes
[ ] Change touches auth, sessions, or RLS in an unspecified way
[ ] Destructive DB operation (drop table, drop column, remove policy)
[ ] Codebase does not match MASTER.md
[ ] In-progress work from a previous session found
```
