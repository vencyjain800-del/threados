## What

One paragraph: what does this PR do?

## Why

Why is this change needed? Link to the issue, roadmap item, or sprint it belongs to.

Closes #

## How

Brief description of the approach taken. Call out any non-obvious decisions.

## Test plan

How was this tested? Check all that apply:

- [ ] Ran `just test` — all tests pass
- [ ] Ran `npm run type-check` in `apps/web` — 0 errors
- [ ] Ran `just lint` — 0 errors
- [ ] Manually tested in browser (describe what you verified)
- [ ] Added new tests (list them)
- [ ] `test_rls.py` verified passing (required for any DB / auth / model change)

## Definition of Done checklist

- [ ] No extra features beyond the issue scope
- [ ] No `console.log` / `print()` / debug statements
- [ ] No hardcoded secrets or credentials
- [ ] New env vars documented in `MASTER.md` and `.env.example`
- [ ] Loading / error / empty states implemented for all new UI
- [ ] `PROJECT_STATUS.md` updated if overall feature state changed
- [ ] `ROADMAP.md` updated if items were completed or new ones discovered

## Screenshots *(for UI changes)*

Before | After
--- | ---
&nbsp; | &nbsp;

## Notes for reviewer

Anything the reviewer should pay particular attention to, or context they need to evaluate correctness:
