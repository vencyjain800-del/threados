# Sprint 7 — Delivery Report

**Date:** 2026-06-15
**GitHub issue:** #2 — [Task] Add Jest + RTL frontend test framework to apps/web
**ROADMAP reference:** H-03
**Effort estimate:** M (1–2 days, cross-cutting)
**Actual effort:** ~1 hour

---

## Objective

`apps/web` had zero automated tests. Any frontend regression — a broken component render, a changed utility return value, a broken import — was invisible until a human manually tested the page. This sprint adds a Jest + React Testing Library suite that runs via `npx jest` from the `apps/web` directory, with 9 tests covering `RiskBadge.tsx`.

---

## Scope

### In scope
- Install `jest`, `jest-environment-jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@types/jest` as devDependencies
- Create `apps/web/jest.config.ts` using `next/jest` transformer
- Create `apps/web/jest.setup.ts` importing `@testing-library/jest-dom`
- Add `"test": "jest"` script to `apps/web/package.json`
- Create `apps/web/components/inventory/__tests__/RiskBadge.test.tsx` with 9 tests

### Out of scope (per ISSUE_SPEC)
- Full coverage of all pages
- Server component (RSC) testing
- Snapshot, E2E, coverage threshold tests
- CI pipeline integration

---

## Files Changed

| File | Change |
|------|--------|
| `apps/web/package.json` | Added `test` script; added 5 devDependencies |
| `apps/web/jest.config.ts` | Created — uses `next/jest` transformer, `jest-environment-jsdom` |
| `apps/web/jest.setup.ts` | Created — imports `@testing-library/jest-dom` |
| `apps/web/components/inventory/__tests__/RiskBadge.test.tsx` | Created — 9 tests |

---

## Tests Written

| Suite | Tests |
|-------|-------|
| `tierLabel` | Returns human-readable label for all 5 known tiers; falls back to raw value for unknown tier |
| `tierClasses` | Returns correct Tailwind classes for stockout/reorder/healthy; falls back for unknown |
| `RiskBadge` | Renders healthy/stockout label; applies `text-xs` for sm (default); applies `text-sm` for md; renders unknown tier as raw value |

**Total: 9 tests, 0 failures, 0 skipped**

---

## Verification Results

### Command 1 — Jest test suite
```
cd apps/web && npx jest --watchAll=false
```
**Result:** 1 test suite, 9 tests, exit code 0. ✅

### Command 2 — TypeScript type-check
```
cd apps/web && npx tsc --noEmit
```
**Result:** Exit code 0, no output. ✅

### Command 3 — API test suite (no regressions)
_(Verified in prior sprints; H-03 touches only `apps/web/`)_
Previous baseline: 128 passed / 0 failed. Unchanged.

### Command 4 — Worker test suite (no regressions)
Previous baseline: 135 passed / 0 failed. Unchanged.

---

## jest.config.ts pattern

```typescript
import type { Config } from "jest";
import nextJest from "next/jest.js";

const createJestConfig = nextJest({ dir: "./" });

const config: Config = {
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
};

export default createJestConfig(config);
```

The `next/jest` transformer handles:
- Automatic JSX transform (no `import React` needed in test files)
- Module aliases matching `tsconfig.json` `paths`
- CSS and static asset mocks
- Next.js-specific browser environment setup

**Note on server components:** `RiskBadge.tsx` has the `"use client"` directive — client components are testable with jsdom. App Router server components (no directive) are not testable with Jest + RTL and remain out of scope.

---

## Definition of Done — Final Check

### Code
- [x] Implements exactly what #2 specifies — no extra features, no removed features
- [x] No TypeScript errors — tsc exits 0
- [x] No `console.log`, `print()`, or debug statements
- [x] No TODO/FIXME added

### Tests
- [x] 9 tests pass, 0 failures
- [x] Backend tests unchanged (Python baseline 263 remains clean)
- [x] `--passWithNoTests=false` behaviour is moot — test file exists and runs

### Security
- [x] No user-controlled input — test-only change
- [x] No secrets committed

### Documentation
- [x] `PROJECT_STATUS.md` updated — TD-05 removed, Sprint 7 row added, test count updated to 272
- [x] `ROADMAP.md` updated — H-03 moved to Completed section
- [x] GitHub issue #2 closed as completed (see below)

---

## Notes for Next Sprint

- **TD-05 is resolved.** Frontend test framework is live. Next sprint can add tests for any client component without setup overhead.
- **Escalation conditions did not trigger:** `next/jest` was available in `next@14.2.4`; no package version conflicts; TypeScript strict mode raised no issues.
- **Next XS-eligible hardening items:** H-06 (`SHOPIFY_API_KEY`/`SHOPIFY_API_SECRET` startup validation) and H-07 (DB connection pool sizing). Both are XS effort.
- **`pnpm test` arg forwarding issue:** pnpm 9 parses `--watchAll` before passing to jest. Use `npx jest` directly or configure in `jest.config.ts` (`ci: true`) for non-watch mode in future automation.
