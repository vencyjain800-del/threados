# ThreadOS — Definition of Done

A piece of work is **Done** only when every applicable item below is checked. Items marked *(if applicable)* are skipped only when explicitly noted in the PR description.

---

## Code

- [ ] Implements exactly what the sprint/issue specifies — no extra features, no removed features
- [ ] No TypeScript errors (`npm run type-check` passes with 0 errors)
- [ ] No Python type errors (`uv run mypy app` passes in `services/api`)
- [ ] Linting passes (`just lint` exits 0)
- [ ] No `console.log`, `print()`, or debug statements left in
- [ ] No TODO/FIXME comments added (if you find one, file an issue for it separately)
- [ ] New backend endpoints follow the existing router pattern (prefix, tags, `require_brand` dep)
- [ ] New shared types added to `packages/shared-types/src/index.ts` and exported *(if applicable)*
- [ ] New API client methods added to `apps/web/lib/api-client.ts` *(if applicable)*

## Tests

- [ ] All existing tests pass: `just test` exits 0 with **0 failures**
- [ ] `test_rls.py` passes (must be verified explicitly when touching DB models, sessions, or RLS)
- [ ] New backend logic has at least one test covering the happy path
- [ ] New validation logic has at least one test covering a rejection case (4xx)
- [ ] Test count has not decreased from the previous sprint baseline

## Security

- [ ] No user-controlled input used in raw SQL — always use parameterised queries or ORM
- [ ] No secrets or credentials committed (no `.env`, no hardcoded keys)
- [ ] Tenant data access uses `tenant_session(brand_id)`, not `system_session()`
- [ ] New endpoints that return tenant data are guarded by `require_brand`
- [ ] Frontend pages that require auth call `auth.me().catch(() => router.push("/login"))` in `useEffect`

## UX (frontend changes only)

- [ ] Loading states shown for all async data fetches (skeleton or spinner)
- [ ] Error states shown with user-facing message and Retry button where retrying makes sense
- [ ] Empty states shown when a list or table has zero results
- [ ] No `catch(() => null)` swallowing API errors that affect visible UI
- [ ] New pages added to the nav in `AppNav.tsx` *(if applicable)*
- [ ] No new UI component libraries introduced (no shadcn / radix / lucide)

## Documentation

- [ ] `PROJECT_STATUS.md` updated if overall feature state changed
- [ ] `ROADMAP.md` updated if items were completed or new ones discovered
- [ ] `CLAUDE.md` updated if architecture, commands, or key patterns changed *(if applicable)*
- [ ] PR description explains *why* the change was made, not just *what*

## Deployment readiness *(for changes that touch infrastructure)*

- [ ] New environment variables documented in `MASTER.md` and `.env.example`
- [ ] New migrations have a working `downgrade()` function
- [ ] New migrations tested against a clean database (`just db-reset && just db-migrate`)
