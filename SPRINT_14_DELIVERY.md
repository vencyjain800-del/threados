# Sprint 14 Delivery — O-03: Recommendation Staleness Alert

**Date:** 2026-06-15
**Issue:** #9 — O-03: Recommendation staleness alert
**Branch:** auto-sprint-14
**Effort:** S (half-day, 2 files changed)

---

## Objective

Add an operator-facing health endpoint that makes it immediately visible when the
recommendation job has not run for any active brand within the last 24 hours.

---

## Scope

**In scope:**
- New `GET /health/staleness` endpoint in `services/api/app/routers/health.py`
- 8 new tests in `services/api/tests/test_health.py`

**Out of scope:**
- Email/Slack/webhook notifications (out-of-scope per ROADMAP.md)
- Per-brand auth-gated staleness view
- Automatic job re-triggering on staleness detection

---

## Files Changed

| File | Change |
|------|--------|
| `services/api/app/routers/health.py` | Added `GET /health/staleness` endpoint |
| `services/api/tests/test_health.py` | New file — 8 tests for liveness, readiness, and staleness |
| `PROJECT_STATUS.md` | Sprint 14 row, test count, overall state row, next candidates |
| `ROADMAP.md` | O-03 moved from Observability table to Completed |
| `SPRINT_14_DELIVERY.md` | This file |

---

## Endpoint Design

```
GET /health/staleness
```

- **Auth:** None (system-level operator endpoint, consistent with `/health/live` and `/health/ready`)
- **DB access:** `system_session()` — uses `threados_migrate` role with `rolbypassrls=True`; the only role that can query `FORCE RLS` tables cross-tenant without a tenant GUC
- **Staleness threshold:** 24 hours (constant `_STALENESS_THRESHOLD_HOURS`)

### Query

```sql
SELECT sc.brand_id::text AS brand_id, MAX(ir.run_at) AS last_run_at
FROM   shopify_connections sc
LEFT   JOIN inventory_recommendations ir ON ir.brand_id = sc.brand_id
WHERE  sc.uninstalled_at IS NULL
GROUP  BY sc.brand_id
ORDER  BY sc.brand_id
```

Active brands = `uninstalled_at IS NULL`. LEFT JOIN ensures brands that have never run
recommendations appear with `last_run_at = NULL`.

### Response shape

```json
{
  "threshold_hours": 24,
  "checked_at": "2026-06-15T16:00:00.000000+00:00",
  "total_count": 3,
  "stale_count": 1,
  "any_stale": true,
  "brands": [
    {
      "brand_id": "uuid-string",
      "last_run_at": "2026-06-14T10:00:00+00:00",
      "hours_since_last_run": 30.12,
      "is_stale": true
    },
    {
      "brand_id": "uuid-string",
      "last_run_at": null,
      "hours_since_last_run": null,
      "is_stale": true
    },
    {
      "brand_id": "uuid-string",
      "last_run_at": "2026-06-15T15:00:00+00:00",
      "hours_since_last_run": 1.0,
      "is_stale": false
    }
  ]
}
```

`any_stale: true` is the single boolean a monitoring tool needs for an uptime check.

---

## How to Use This Endpoint

**Uptime monitoring (e.g. UptimeRobot, Pingdom):**
- URL: `https://{api_host}/health/staleness`
- Assert: response body contains `"any_stale": false`
- Alert: if `any_stale` is `true` for more than 15 minutes

**Manual operator check:**
```bash
curl https://api.threados.com/health/staleness | jq '.brands[] | select(.is_stale)'
```

---

## Tests Added (8)

| Test | Assertion |
|------|-----------|
| `test_liveness` | `/health/live` returns `{"status": "ok"}` |
| `test_readiness` | `/health/ready` returns `{"status": "ok"}` |
| `test_staleness_envelope` | All required top-level keys present |
| `test_staleness_no_active_connections` | Empty brands → `stale_count=0`, `any_stale=false` |
| `test_staleness_fresh_brand` | `last_run_at` 1h ago → `is_stale=false` |
| `test_staleness_stale_brand` | `last_run_at` 30h ago → `is_stale=true` |
| `test_staleness_never_ran` | `last_run_at=null` → `is_stale=true`, `hours=null` |
| `test_staleness_counts_consistent` | `stale_count` and `any_stale` match brands list |

All tests mock `system_session()` to avoid cross-session transaction visibility issues with the test DB's rollback-per-test isolation model.

---

## Verification

```
ruff check app/routers/health.py tests/test_health.py  →  All checks passed
API tests:  147 passed / 0 failed  (↑8 from Sprint 13's 139)
Worker tests:  137 passed / 0 failed  (unchanged)
```

---

## Review Checklist

- [ ] CI is green
- [ ] Test delta is ≥ 0 (no tests removed)
- [ ] `PROJECT_STATUS.md` Sprint History updated
- [ ] No files outside task scope changed

**To approve:** merge this PR.
**To reject:** close this PR with a comment explaining why. Claude will not retry the same task without a new instruction.
**To request changes:** leave a review comment. Claude will address it in the next session.
