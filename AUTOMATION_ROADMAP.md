# ThreadOS — Automation Roadmap

The goal: Claude selects tasks, executes them, opens PRs, and updates documentation without
founder involvement on any routine step. The founder touches the system only to review and
merge PRs, or when a defined escalation condition is triggered.

This document lists every infrastructure change needed to reach that state, in the order
they must be implemented. Each phase is independently deployable — later phases build on
earlier ones but do not require them to be perfect.

---

## Current State (baseline)

| Capability | Status |
|---|---|
| Claude reads ROADMAP.md and selects tasks | ✅ Manual trigger required |
| Claude executes tasks to completion | ✅ Manual trigger required |
| Claude runs verification (tests, lint, type-check) | ✅ Manual trigger required |
| Claude updates PROJECT_STATUS.md and ROADMAP.md | ✅ Manual trigger required |
| Claude opens GitHub PRs | ❌ Not implemented |
| Claude assigns reviewers / labels PRs | ❌ Not implemented |
| Claude notifies founder on completion | ❌ Not implemented |
| Claude notifies founder on escalation | ❌ Not implemented |
| GitHub Actions CI runs on every PR | ❌ Not implemented |
| Founder can approve/merge from phone | ✅ GitHub mobile app works today |

---

## Phase 1 — PR Automation (implement first)

**Goal:** Claude opens a real GitHub PR at the end of every sprint instead of only updating
local files.

**Why first:** Everything downstream (CI, notifications, approvals) is useless without a PR.
This phase has zero infrastructure requirements beyond what already exists.

### 1.1 — Extend `AGENT_WORKFLOW.md` §5 with PR-open step

Add to the Completion Procedure, after writing `SPRINT_N_DELIVERY.md`:

```
5.5  Open a GitHub PR
     - Branch: auto-sprint-N  (N = sprint number, e.g. auto-sprint-13)
     - Initialise git in the working directory if not already a repo
     - Commit all changes with message: "Sprint N: <one-line summary>"
     - Push branch to origin
     - Open PR via GitHub API:
         title:  "[Auto] Sprint N — <issue title>"
         body:   contents of SPRINT_N_DELIVERY.md
         labels: ["auto-sprint"]
         draft:  false
     - Post the PR URL as the final line of output
```

### 1.2 — Add `auto-sprint` label to the GitHub repo

Create it once manually: Settings → Labels → New label → `auto-sprint` (colour: #0075ca).

### 1.3 — Initialise the repo as a proper git working tree

The monorepo root must be a git repo with a remote pointing at `vencyjain800-del/threados`.
If it already is, verify `git remote -v`. If it is not, run `git init && git remote add origin`.

**Deliverable:** After Phase 1, every sprint ends with a PR that the founder can review and
merge from GitHub without ever opening a terminal.

---

## Phase 2 — GitHub Actions CI (implement second)

**Goal:** Every PR opened by Claude is automatically validated by CI before the founder sees it.
The founder should never need to run tests locally.

### 2.1 — Create `.github/workflows/ci.yml`

Triggers: `pull_request` targeting `main`.

Jobs (run in parallel where possible):

```
api-tests:
  runs-on: ubuntu-latest
  services: postgres:15, redis:7
  steps: uv sync → alembic upgrade head → pytest services/api --tb=short -q

worker-tests:
  runs-on: ubuntu-latest
  services: postgres:15
  steps: uv sync → pytest services/worker --tb=short -q

web-typecheck:
  runs-on: ubuntu-latest
  steps: pnpm install → pnpm --filter @threados/web type-check

lint:
  runs-on: ubuntu-latest
  steps: uv run ruff check services/ → pnpm --filter @threados/web lint
```

### 2.2 — Require CI to pass before merge

Repository Settings → Branch protection on `main`:
- Require status checks: `api-tests`, `worker-tests`, `web-typecheck`, `lint`
- Require branches to be up to date before merging
- Do NOT require approvals (founder approves by merging, not by a separate approval step)

### 2.3 — Add CI badge to `README.md` (or `MASTER.md`)

Instant visual confirmation that main is green.

**Deliverable:** After Phase 2, the founder can see at a glance whether a PR is safe to merge.
No test output to read. Green CI = ready to merge.

---

## Phase 3 — Founder Notifications (implement third)

**Goal:** Founder receives a notification the moment a PR is ready for review, and a separate
notification when an escalation is triggered.

### 3.1 — GitHub email notifications (zero-config)

GitHub already sends an email to `vencyjain143@gmail.com` when:
- A PR is opened (if subscribed to the repo)
- A PR's CI passes

Verify: GitHub → Settings → Notifications → turn on "Pull Request reviews" and
"Actions — Workflow runs on repositories you watch".

This alone satisfies the PR-ready notification with no code changes.

### 3.2 — Escalation notification via GitHub issue

When Claude triggers an escalation (see `ESCALATION_POLICY.md`), it creates a GitHub issue
labelled `escalation` with:
- Title: `[Escalation] <reason in one line>`
- Body: structured report (what/found/options/needed — from AGENT_WORKFLOW.md §6.3)
- Assigned to: founder GitHub account (`vencyjain800-del` or the personal account)

GitHub emails the founder automatically when assigned to an issue. No webhook infrastructure needed.

### 3.3 — Sprint completion comment on PR

When Claude opens a PR, it also posts a comment linking to relevant files changed and the
test delta (e.g. "Tests: 137 → 139. Files changed: 3"). This gives the founder a two-line
summary without reading the full PR body.

**Deliverable:** After Phase 3, the founder is pulled in via email for every PR and every
escalation. All other work is invisible.

---

## Phase 4 — Autonomous Scheduling (implement fourth)

**Goal:** Claude starts new sprints without being manually invoked. The founder's only action
is merging PRs.

### 4.1 — Windows Task Scheduler trigger

Create a scheduled task (Windows Task Scheduler or `schtasks`) that runs:

```
claude --print "Continue using AGENT_WORKFLOW.md. ..." > logs\sprint_YYYYMMDD.log 2>&1
```

Recommended schedule: daily at 02:00, skipping if a PR from the previous sprint is still open.

The "skip if PR open" guard prevents Claude from starting Sprint N+1 before Sprint N is merged.
Implement it by querying the GitHub API for open PRs with label `auto-sprint` before proceeding.

### 4.2 — Log rotation

Keep the last 30 `logs\sprint_*.log` files. Delete older ones at the start of each run.

### 4.3 — Idle detection

If no roadmap items remain in any eligible group, Claude opens a GitHub issue titled
`[Automation] Roadmap exhausted — awaiting new items` and stops scheduling until a
new item is added.

**Deliverable:** After Phase 4, the founder's only routine action is opening GitHub once a day
to merge (or decline) a PR. If there is no PR, nothing happened.

---

## Phase 5 — Self-Healing and Guardrails (implement last)

**Goal:** Handle common failure modes without founder involvement.

### 5.1 — Retry on transient test failures

If `just test` fails and the failure is a known-transient pattern (e.g. port conflict, Redis
connection reset), Claude retries once before escalating.

Transient patterns to detect (grep in test output):
- `ConnectionRefusedError`
- `address already in use`
- `asyncpg.exceptions.TooManyConnectionsError`

### 5.2 — PR auto-close on superseded sprint

If a PR from Sprint N is open and Claude completes Sprint N+1 (should not happen given the
guard in 4.1, but defensive), Claude adds a comment to the Sprint N PR:
`"Superseded by #<N+1 PR number>. Closing."` and closes it.

### 5.3 — Weekly health report

Every Monday, Claude opens a GitHub issue titled `[Weekly] Automation health — <date>` with:
- Sprints completed last week
- PRs merged / declined
- Any escalations triggered
- Current roadmap item count per group

No action required from the founder unless they want to reprioritise.

---

## Implementation Priority Summary

| Phase | What | Effort | Founder touch-time saved |
|-------|------|--------|--------------------------|
| 1 | PR automation | 2 hours | Eliminates manual PR creation forever |
| 2 | GitHub Actions CI | 3 hours | Eliminates manual test runs before merge |
| 3 | Notifications | 1 hour | Eliminates checking for sprint completion |
| 4 | Scheduling | 2 hours | Eliminates manually starting sprints |
| 5 | Guardrails | 3 hours | Eliminates monitoring for automation failures |

**Start with Phase 1.** It delivers immediate value and the other phases have no effect
without it.
