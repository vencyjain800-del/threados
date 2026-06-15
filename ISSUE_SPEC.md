# ThreadOS — Issue Specification Contract

Every issue that an agent will execute autonomously **must** contain all fields defined in this document, filled in exactly as specified. An issue that omits a required field, leaves a field as its placeholder value, or provides a non-runnable Verification Command is **not valid for autonomous execution** and must be returned to the author.

The contract exists for one reason: to make task completion objectively verifiable without human interpretation. Every field either eliminates a class of ambiguity or enables a mechanical check.

---

## Schema

All fields are required. Permitted values and format rules are given for each.

---

### Field 1 — Problem Statement

**What it is:** A description of the current broken or missing behaviour. Describes reality as it stands today, not the desired future state.

**Format rules:**
- Maximum three sentences.
- Must describe observable behaviour, not internal state. "The server crashes" is observable. "The variable is null" is not.
- Must not contain the solution.

**Valid:** `When the worker job fails, the RQ queue silently discards it. There is no log entry, no failed-job record, and no way for an operator to know the job did not complete. This means forecast and recommendation failures are invisible until a merchant notices stale data.`

**Invalid:** `We need to add a dead-letter queue to the worker.` ← This is the solution, not the problem.

---

### Field 2 — Success State

**What it is:** A single sentence that describes the world after the task is complete. Written in present tense as if the work is already done.

**Format rules:**
- Exactly one sentence.
- Must describe an externally observable condition, not an internal implementation detail.
- Must be falsifiable: a reader must be able to determine from it whether the task is done or not.

**Valid:** `When a worker job raises an unhandled exception, the job is moved to a failed-jobs queue and a structured log entry at ERROR level is written with the job name, exception type, and traceback.`

**Invalid:** `The dead-letter queue is implemented.` ← Not falsifiable. Implemented how? To what standard?

**Invalid:** `The code is cleaner and handles errors better.` ← Not observable.

---

### Field 3 — Verification Command

**What it is:** A shell command (or ordered sequence of commands) that an agent runs after implementation to confirm the Success State has been achieved. Must be runnable in the standard dev environment without manual steps.

**Format rules:**
- Must be a literal, copy-pasteable shell command.
- Must not require human observation to interpret (no "run the app and check the browser").
- Must not depend on external services that are not part of the standard dev stack (Postgres, Redis, the API, and the worker are in-scope; Shopify, AWS, and ngrok are not).
- If the verification requires the API to be running, include the startup command in the sequence.
- If the verification requires a specific test, name the exact test function.

**Valid:**
```bash
cd services/api && uv run pytest tests/test_worker.py::test_failed_job_goes_to_dead_letter -v
```

**Valid (sequence):**
```bash
# 1. Confirm no deprecation warnings in target files
cd services/api && uv run python -W error::DeprecationWarning -c "from app.models import tenancy, shopify, recommendations, inventory, audit"
# 2. Confirm tests still pass
just test
```

**Invalid:** `Run the app and trigger a failing job, then check the logs.` ← Requires human observation.

**Invalid:** `Check that no DeprecationWarning appears.` ← Not a command.

---

### Field 4 — Expected Verification Result

**What it is:** The exact output or exit condition that the Verification Command must produce for the task to be considered done. The agent compares actual output against this field mechanically.

**Format rules:**
- Must be specific enough that pass/fail is unambiguous.
- For test commands: state the minimum pass count and the required failure count (`N passed, 0 failed` — N must be ≥ the current baseline).
- For commands that check output: quote the exact string that must appear, or the exact string that must not appear.
- For exit-code checks: state the required exit code (0 for success).

**Valid:** `Exit code 0. Output contains "passed" and "0 failed". Test count ≥ 128.`

**Valid:** `Exit code 0. No output (absence of DeprecationWarning is the signal).`

**Invalid:** `Tests pass.` ← Not specific enough. How many? Which ones?

**Invalid:** `No errors.` ← Does not distinguish warnings from errors, or test failures from lint failures.

---

### Field 5 — Acceptance Criteria

**What it is:** An ordered checklist of conditions that must all be true for the task to be done. Each item must be independently verifiable.

**Format rules:**
- Minimum two items; maximum eight.
- Each item is a checkbox `- [ ]`.
- Each item must describe a verifiable condition, not an activity. "Tests written" is an activity. "New test `test_failed_job_goes_to_dead_letter` passes" is a verifiable condition.
- Do not duplicate the Verification Command here. The criteria describe *what* is true; the command is *how* you check it.

**Valid:**
```
- [ ] `uv run python -W error::DeprecationWarning -c "from app.models import tenancy"` exits 0
- [ ] All 128 existing tests continue to pass
- [ ] No new `datetime.utcnow` call appears anywhere in `services/api/app/`
```

**Invalid:**
```
- [ ] Fix the deprecation warnings ← activity, not condition
- [ ] Make sure it works ← not verifiable
```

---

### Field 6 — Dependencies

**What it is:** A list of conditions that must be true before this task can start. Unsatisfied dependencies are escalation triggers.

**Format rules:**
- List each dependency as a bullet.
- For each dependency, state whether it is currently satisfied (✅) or not (❌).
- If all dependencies are satisfied, write `None.`
- Do not list the standard development environment (Docker running, `.env` present) as a dependency — those are assumed.

**Valid:**
```
- ✅ `packages/shared-types/src/index.ts` exports `HealthResponse`
- ❌ Migration `007_add_failed_jobs_table.py` must exist before this task starts
```

**Valid:** `None.`

**Invalid:** `The app must be working.` ← Too vague. What aspect? How to verify?

---

### Field 7 — Out of Scope

**What it is:** An explicit list of things this task must not do, even if they seem related or adjacent. This is the primary scope-creep prevention mechanism.

**Format rules:**
- Minimum one item. If you cannot think of anything out of scope, you have not thought about scope enough.
- Each item must be specific enough that an agent can determine whether a proposed change crosses the line.
- Reference `ROADMAP.md` IDs or `MASTER.md` exclusions where applicable.

**Valid:**
```
- Do not change any business logic in the models — only the `default=` column argument
- Do not fix the same pattern in `services/worker/` — that is a separate task
- Do not add new tests beyond those that directly verify the fix
```

**Invalid:** `Don't break anything.` ← Not actionable.

---

### Field 8 — Relevant Files

**What it is:** A list of files the agent should read before starting and will likely modify. Not required to be exhaustive, but must include the primary target files.

**Format rules:**
- Full path relative to the monorepo root.
- Mark each as `read` (must read, may not modify) or `modify` (expected to change).
- If a file does not exist yet and must be created, mark it `create`.

**Valid:**
```
- `services/api/app/models/tenancy.py` — modify
- `services/api/app/models/shopify.py` — modify
- `services/api/tests/test_rls.py` — modify (fix one call site)
- `services/api/app/routers/health.py` — read (understand existing pattern)
```

**Invalid:** `The models directory.` ← Not specific enough for an agent to know what to read.

---

### Field 9 — Effort Estimate

**What it is:** A single effort label from the standard scale. Used by the agent to calibrate how many implementation steps to expect and when unexpected complexity should trigger escalation.

**Format rules:** Exactly one of: `XS`, `S`, `M`, `L`. See `ROADMAP.md` for definitions.

**Escalation rule:** If an XS or S task requires changes to more files than listed in Field 8, or if implementation has taken longer than the effort estimate suggests it should, the agent must stop and report the discrepancy before continuing.

---

### Field 10 — Escalation Conditions

**What it is:** Task-specific triggers that require human input, in addition to the global triggers in `AGENT_WORKFLOW.md §6.1`. These are conditions the issue author knows about that the agent cannot anticipate from the code alone.

**Format rules:**
- At minimum, one item (even if it is "None beyond global triggers").
- State the condition, not just the concern. "If X is true, stop" — not "be careful about X".

**Valid:**
```
- If `datetime.timezone` is already imported in the target file under a different alias, stop — aliasing patterns must be consistent across the codebase and require a human decision.
- If more than 15 call sites are found, stop — the issue assumed a small blast radius.
```

**Valid:** `None beyond the global triggers in AGENT_WORKFLOW.md §6.1.`

---

## Validation Checklist

Before starting any issue, the agent must verify the issue itself is well-formed. An issue fails validation if any of the following are true:

```
[ ] Field 2 (Success State) is more than one sentence
[ ] Field 3 (Verification Command) contains the word "check", "verify", "ensure", "look at",
    or "run the app" without a literal shell command following it
[ ] Field 4 (Expected Result) says only "tests pass" or "no errors" without specifics
[ ] Field 5 (Acceptance Criteria) contains an item that is an activity rather than a condition
[ ] Field 6 (Dependencies) lists an unsatisfied dependency marked ❌
[ ] Any field still contains its placeholder text from the template
```

If the issue fails validation → escalate with the specific fields that are non-compliant. Do not attempt to infer what the author intended.

---

## Template (copy this for every new issue)

```markdown
## Problem Statement

<!-- Observable description of current broken/missing behaviour. Max 3 sentences. No solution. -->

## Success State

<!-- Single sentence. Present tense. Externally observable. Falsifiable. -->

## Verification Command

```bash
# Runnable command(s). No manual steps. No external services.
```

## Expected Verification Result

<!-- Exact output or exit code. Include minimum test count if applicable. -->

## Acceptance Criteria

- [ ] 
- [ ] 
- [ ] All existing tests continue to pass (count ≥ N from PROJECT_STATUS.md)

## Dependencies

<!-- ✅ or ❌ for each. Write "None." if no dependencies. -->

## Out of Scope

<!-- Minimum one item. Reference ROADMAP.md IDs or MASTER.md exclusions. -->

## Relevant Files

<!-- path/to/file.py — read | modify | create -->

## Effort Estimate

<!-- XS | S | M | L -->

## Escalation Conditions

<!-- Task-specific stop conditions. Or: "None beyond AGENT_WORKFLOW.md §6.1." -->
```

---

## Example 1 — Bug Issue (H-04: `datetime.utcnow()` deprecation)

This example is drawn from a real known issue in the codebase. `datetime.utcnow()` is deprecated in Python 3.12 and will raise a hard error in Python 3.14. It currently appears in 15 model `default=` column arguments and one test call site.

---

**Title:** `[Bug] Replace datetime.utcnow() with timezone-aware equivalent across models`

**Labels:** `bug`, `severity:medium`

**ROADMAP.md reference:** H-04

---

## Problem Statement

Fourteen SQLAlchemy model columns in `services/api/app/models/` use `default=datetime.utcnow` as the column default, and one call site exists in `services/api/tests/test_rls.py:92`. Python 3.12 emits `DeprecationWarning` for `datetime.utcnow()`; Python 3.14 will raise a hard `AttributeError`. Running `python -W error::DeprecationWarning` against the models module currently exits non-zero.

## Success State

Every `datetime.utcnow` reference in `services/api/` is replaced with `lambda: datetime.now(tz=timezone.utc)`, and running the models import under `-W error::DeprecationWarning` exits 0 with no output.

## Verification Command

```bash
# 1. Confirm no DeprecationWarning is raised on model import
cd services/api && uv run python -W error::DeprecationWarning -c \
  "from app.models import tenancy, shopify, catalogue, orders, inventory, audit, recommendations"

# 2. Confirm no remaining utcnow references in app source
grep -rn "utcnow" services/api/app/ --include="*.py"

# 3. Confirm all tests still pass
just test
```

## Expected Verification Result

Command 1: exit code 0, no output.
Command 2: exit code 1 (grep finds no matches — grep returns 1 when nothing is found), no output.
Command 3: exit code 0. Output contains `passed` and `0 failed`. Test count ≥ 128.

## Acceptance Criteria

- [ ] `uv run python -W error::DeprecationWarning -c "from app.models import tenancy, shopify, catalogue, orders, inventory, audit, recommendations"` exits 0 with no output
- [ ] `grep -rn "utcnow" services/api/app/ --include="*.py"` returns no matches
- [ ] The single call site in `services/api/tests/test_rls.py:92` is also replaced
- [ ] All 128 existing tests pass with 0 failures

## Dependencies

None.

## Out of Scope

- Do not change any business logic or column constraints — only the `default=` argument
- Do not touch `services/worker/` — a separate grep should be run to check it, but fixing it is a separate task
- Do not change the column type from `DateTime(timezone=True)` — it is already correct
- Do not add or remove any model fields
- Do not update any migration files — the column definitions in migrations are historical records and are not executed at runtime

## Relevant Files

- `services/api/app/models/tenancy.py` — modify (4 call sites)
- `services/api/app/models/shopify.py` — modify (2 call sites)
- `services/api/app/models/recommendations.py` — modify (6 call sites)
- `services/api/app/models/inventory.py` — modify (1 call site)
- `services/api/app/models/audit.py` — modify (1 call site)
- `services/api/tests/test_rls.py` — modify (1 call site at line 92)

## Effort Estimate

XS

## Escalation Conditions

- If `timezone` is not already imported from `datetime` in a target file and adding the import would conflict with an existing `timezone` name from another module, stop and report the conflict.
- If more than 15 total `utcnow` call sites are found across `services/api/app/`, stop — the issue assumed a bounded blast radius and the actual scope needs human review.

---

## Example 2 — Feature Issue (H-06: Shopify API key startup validation)

This is a real unresolved gap. `config.py` currently validates `SHOPIFY_APP_URL`, `SHOPIFY_REDIRECT_URI`, `KMS_KEY_ID`, `SESSION_SECRET`, and `CSRF_SECRET` at startup but does not check `SHOPIFY_API_KEY` or `SHOPIFY_API_SECRET`. A misconfigured app will accept the install redirect and then crash silently at the HMAC verification step.

---

**Title:** `[Feature] Add startup validation for SHOPIFY_API_KEY and SHOPIFY_API_SECRET`

**Labels:** `task`, `hardening`

**ROADMAP.md reference:** H-06

---

## Problem Statement

`services/api/app/config.py` contains a `validate_required_for_shopify()` method that checks `SHOPIFY_APP_URL`, `SHOPIFY_REDIRECT_URI`, and `KMS_KEY_ID` at startup. It does not check `SHOPIFY_API_KEY` or `SHOPIFY_API_SECRET`. If either is missing or empty, the API starts without warning, accepts the Shopify OAuth install redirect, and fails with an unhandled exception at the HMAC verification step in `oauth.py:57`. The operator receives no advance notice that the configuration is incomplete.

## Success State

When the API starts with `SHOPIFY_API_KEY` or `SHOPIFY_API_SECRET` set to an empty string, `validate_required_for_shopify()` returns both variable names in its missing list, and the startup lifespan handler logs a `WARNING` that includes both names before the first request is served.

## Verification Command

```bash
# 1. Unit test: validate_required_for_shopify returns correct missing vars
cd services/api && uv run pytest tests/test_config_validation.py -v

# 2. Confirm the new test file exists and the test count increased
just test
```

## Expected Verification Result

Command 1: exit code 0. Output contains `passed` and `0 failed`. All tests in `test_config_validation.py` listed as PASSED.
Command 2: exit code 0. Test count ≥ 130 (128 baseline + at least 2 new tests).

## Acceptance Criteria

- [ ] `settings.validate_required_for_shopify()` returns `["SHOPIFY_API_KEY"]` when `shopify_api_key` is `""`
- [ ] `settings.validate_required_for_shopify()` returns `["SHOPIFY_API_SECRET"]` when `shopify_api_secret` is `""`
- [ ] `settings.validate_required_for_shopify()` returns both names when both are `""`
- [ ] `settings.validate_required_for_shopify()` returns an empty list when both are non-empty strings
- [ ] The startup lifespan handler in `main.py` already calls `validate_required_for_shopify()` — confirm it will log the new missing vars without any change to `main.py`
- [ ] Two new tests in `services/api/tests/test_config_validation.py` cover the cases above
- [ ] All 128 existing tests pass with 0 failures

## Dependencies

- ✅ `config.py` already has `validate_required_for_shopify()` at line 73
- ✅ `main.py` already calls `validate_required_for_shopify()` in the lifespan handler and logs missing vars

## Out of Scope

- Do not add validation for `SHOPIFY_SCOPES` or `SHOPIFY_API_VERSION` — these have safe defaults
- Do not change the log level for missing Shopify vars (already `WARNING` — leave it)
- Do not add minimum-length checks for the key/secret values — presence check only
- Do not modify `main.py` — the lifespan handler already handles the output of `validate_required_for_shopify()`
- Do not add validation for `SHOPIFY_API_KEY` or `SHOPIFY_API_SECRET` format (they are opaque strings)

## Relevant Files

- `services/api/app/config.py` — modify (`validate_required_for_shopify` method only)
- `services/api/tests/test_config_validation.py` — create (new test file)
- `services/api/app/main.py` — read only (confirm no change needed)

## Effort Estimate

XS

## Escalation Conditions

- If `test_config_validation.py` already exists (from a previous session) with different test names or different assertions, stop and report the conflict rather than overwriting.
- None beyond the global triggers in `AGENT_WORKFLOW.md §6.1`.

---

## Example 3 — Infrastructure Issue (ROADMAP stale: H-02 already complete)

This example demonstrates an **infrastructure/audit** issue — specifically, correcting a stale roadmap entry. The audit in Phase 4 revealed that `GET /health/ready` was listed as unbuilt (H-02 in `ROADMAP.md`) but already exists in `services/api/app/routers/health.py`. The infrastructure issue is to correct the project state documents, not to build anything.

---

**Title:** `[Infrastructure] Correct stale ROADMAP.md and PROJECT_STATUS.md entries`

**Labels:** `task`, `documentation`

---

## Problem Statement

`ROADMAP.md` lists H-02 (`GET /health/ready` endpoint) as unbuilt under Hardening. The endpoint already exists in `services/api/app/routers/health.py` and is registered in `main.py`. `PROJECT_STATUS.md` does not list `GET /health/ready` in its Overall State table. Two documents describe reality incorrectly, which causes an agent following `AGENT_WORKFLOW.md` to attempt to implement an already-implemented feature.

## Success State

`ROADMAP.md` no longer lists H-02 as an open item, `PROJECT_STATUS.md`'s Overall State table contains a row for the health endpoint marked ✅ Complete, and the TD-02 entry in PROJECT_STATUS.md is removed.

## Verification Command

```bash
# 1. Confirm H-02 line is gone from the Hardening table
grep "H-02" threados/ROADMAP.md

# 2. Confirm health endpoint row exists in PROJECT_STATUS.md
grep "health" threados/PROJECT_STATUS.md

# 3. Confirm TD-02 is gone from PROJECT_STATUS.md
grep "TD-02" threados/PROJECT_STATUS.md

# 4. Confirm the actual endpoint still works (no code was changed)
just test
```

## Expected Verification Result

Command 1: exit code 1, no output (grep finds no match — the H-02 line is gone).
Command 2: exit code 0, output contains a line with "health" and "✅".
Command 3: exit code 1, no output (TD-02 line is gone).
Command 4: exit code 0. Output contains `passed` and `0 failed`. Count ≥ 128.

## Acceptance Criteria

- [ ] `ROADMAP.md` Hardening table does not contain an H-02 row
- [ ] H-02 is present in a `## Completed` section at the bottom of `ROADMAP.md` with the date it was completed
- [ ] `PROJECT_STATUS.md` Overall State table contains: `Health check endpoint | ✅ Complete | GET /health/live and GET /health/ready`
- [ ] `PROJECT_STATUS.md` Known Issues table does not contain TD-02
- [ ] All existing tests pass with 0 failures (no code was changed)

## Dependencies

None.

## Out of Scope

- Do not modify `health.py` or any other code file — this is a documentation-only change
- Do not renumber remaining ROADMAP.md items (H-03 stays H-03, etc.) — IDs are stable references
- Do not update any other potentially stale roadmap items in this task — each stale item is a separate issue

## Relevant Files

- `ROADMAP.md` — modify
- `PROJECT_STATUS.md` — modify
- `services/api/app/routers/health.py` — read only (confirm what exists before updating docs)

## Effort Estimate

XS

## Escalation Conditions

- If `health.py` does not contain both `/health/live` and `/health/ready` routes when read, stop — the premise of this issue is wrong and the documents may need different corrections.
- None beyond the global triggers in `AGENT_WORKFLOW.md §6.1`.
