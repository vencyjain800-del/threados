# Sprint 13 Delivery — O-02: Worker Job Duration Metrics

**Date:** 2026-06-15
**Issue:** #8 — Worker job duration + failure metrics (O-02)
**Effort:** S (half-day, 3 files changed + 2 test files)

---

## Problem

No visibility into how long forecast, recommendation, or sync jobs take. Without duration
in the structured log, slow jobs are invisible until they time out or fail.

## What Was Added

Every worker job now logs `duration_s` (float, rounded to 2 decimal places) in its `*.done`
structured log line, measured with `time.monotonic()` from job start to the point the
done-log is emitted.

| File | Function | Done event | Change |
|------|----------|-----------|--------|
| `services/worker/worker/jobs/forecast.py` | `run_forecast` | `forecast.done` | `import time`; `_t0`; `duration_s` |
| `services/worker/worker/jobs/recommendations.py` | `run_recommendations` | `recommendations.done` | `import time`; `_t0`; `duration_s` |
| `services/worker/worker/jobs/sync.py` | `run_backfill` | `sync.backfill.done` | `import time`; `_t0`; `duration_s` |
| `services/worker/worker/jobs/sync.py` | `run_incremental` | `sync.incremental.done` | `_t0`; `duration_s` |

### Example log output

```json
{"event": "forecast.done", "brand_id": "...", "run_date": "2026-06-15", "rows": 840, "duration_s": 1.23}
{"event": "sync.backfill.done", "brand_id": "...", "products": 120, "orders": 540, "duration_s": 8.41}
```

---

## Bonus Fix

Removed a pre-existing duplicate dict key (`0.950: 1.645` shadowing `0.95: 1.645`) in the
z-score table in `recommendations.py` — caught by ruff F601 during lint pass.

---

## Tests Added

| File | Test | Assertion |
|------|------|-----------|
| `services/worker/tests/test_forecast.py` | `test_run_forecast_logs_duration` | `forecast.done` call has `duration_s: float` |
| `services/worker/tests/test_recommendations.py` | `test_run_recommendations_logs_duration` | `recommendations.done` call has `duration_s: float` |

Sync duration coverage is provided by the structural guarantee — same pattern, same field.

---

## Verification

```
ruff check forecast.py recommendations.py sync.py  →  All checks passed
Worker tests:  137 passed / 0 failed  (↑2 from Sprint 12's 135)
API tests:     139 passed / 0 failed
```
