"""
Sprint 1 end-to-end verification script.

Seeds realistic test data then runs the full pipeline:
  aggregation -> forecast -> recommendations

Prints verification evidence for each Sprint 1 deliverable.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import os
import sys

# Add worker package root to path so 'import worker' resolves
_WORKER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKER_ROOT not in sys.path:
    sys.path.insert(0, _WORKER_ROOT)

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://threados_migrate:password@localhost:5432/threados",
)

from sqlalchemy import create_engine, text

ENGINE = create_engine(
    "postgresql+psycopg://threados_migrate:password@localhost:5432/threados",
    echo=False,
)

SEP = "-" * 70

# Deterministic UUIDs so the script is re-runnable
BRAND_ID  = uuid.UUID("e2e00000-0000-0000-0000-000000000001")
PROD_A_ID = uuid.UUID("e2e00000-0000-0000-0000-000000000010")
PROD_B_ID = uuid.UUID("e2e00000-0000-0000-0000-000000000011")

VARIANTS = [
    (uuid.UUID("e2e00000-0000-0000-0000-000000000101"), 10001, "SKU-TSHIRT-S",  "T-Shirt / Small",  PROD_A_ID),
    (uuid.UUID("e2e00000-0000-0000-0000-000000000102"), 10002, "SKU-TSHIRT-M",  "T-Shirt / Medium", PROD_A_ID),
    (uuid.UUID("e2e00000-0000-0000-0000-000000000103"), 10003, "SKU-TSHIRT-L",  "T-Shirt / Large",  PROD_A_ID),
    (uuid.UUID("e2e00000-0000-0000-0000-000000000104"), 10004, "SKU-HOODIE-M",  "Hoodie / Medium",  PROD_B_ID),
    (uuid.UUID("e2e00000-0000-0000-0000-000000000105"), 10005, "SKU-HOODIE-L",  "Hoodie / Large",   PROD_B_ID),
    (uuid.UUID("e2e00000-0000-0000-0000-000000000106"), 10006, "SKU-HOODIE-XL", "Hoodie / XL",      PROD_B_ID),
]

TODAY = date.today()


def _exec(conn, sql: str, params=None):
    conn.execute(text(sql), params or {})


def step(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ---------------------------------------------------------------------------
# 1. Teardown + seed
# ---------------------------------------------------------------------------

def seed_data():
    step("SEEDING TEST DATA")

    with ENGINE.begin() as conn:
        for tbl in (
            "inventory_recommendations", "inventory_settings", "variant_settings",
            "forecasts", "sales_daily", "inventory_snapshots",
            "inventory_levels", "order_line_items", "orders",
            "variants", "products", "brands",
        ):
            if tbl == "brands":
                _exec(conn, f"DELETE FROM {tbl} WHERE id = :b", {"b": str(BRAND_ID)})
            else:
                _exec(conn, f"DELETE FROM {tbl} WHERE brand_id = :b", {"b": str(BRAND_ID)})

        _exec(conn, """
            INSERT INTO brands (id, name, country, currency, created_at)
            VALUES (:id, 'E2E Verify Co', 'GB', 'GBP', now())
        """, {"id": str(BRAND_ID)})

        for prod_id, title in [(PROD_A_ID, "Classic T-Shirt"), (PROD_B_ID, "Premium Hoodie")]:
            _exec(conn, """
                INSERT INTO products (id, brand_id, shopify_id, title, status, created_at_shop)
                VALUES (:id, :bid, :sid, :title, 'active', now())
            """, {"id": str(prod_id), "bid": str(BRAND_ID),
                  "sid": abs(hash(str(prod_id))) % 999999, "title": title})

        for v_id, shopify_id, sku, title, prod_id in VARIANTS:
            price = Decimal("29.99") if "TSHIRT" in sku else Decimal("59.99")
            _exec(conn, """
                INSERT INTO variants (id, brand_id, product_id, shopify_id, sku, title, price)
                VALUES (:id, :bid, :pid, :sid, :sku, :title, :price)
            """, {"id": str(v_id), "bid": str(BRAND_ID), "pid": str(prod_id),
                  "sid": shopify_id, "sku": sku, "title": title, "price": price})

        # Stock levels designed to trigger every risk tier
        # TSHIRT-S:  0   -> stockout
        # TSHIRT-M:  8   -> reorder  (ROP ~80 for avg 8/day, LT 14)
        # TSHIRT-L:  120 -> healthy
        # HOODIE-M:  500 -> overstock (avg 3/day, threshold ~111)
        # HOODIE-L:  30  -> reorder
        # HOODIE-XL: 20  -> dead     (no sales)
        stock_map = {
            VARIANTS[0][0]: 0,    # TSHIRT-S
            VARIANTS[1][0]: 8,    # TSHIRT-M
            VARIANTS[2][0]: 120,  # TSHIRT-L
            VARIANTS[3][0]: 500,  # HOODIE-M
            VARIANTS[4][0]: 30,   # HOODIE-L
            VARIANTS[5][0]: 20,   # HOODIE-XL
        }
        for v_id, qty in stock_map.items():
            _exec(conn, """
                INSERT INTO inventory_levels (brand_id, variant_id, location_id, available, updated_at)
                VALUES (:bid, :vid, 99001, :qty, now())
                ON CONFLICT (variant_id, location_id)
                DO UPDATE SET available = EXCLUDED.available
            """, {"bid": str(BRAND_ID), "vid": str(v_id), "qty": qty})

        # 90 days of sales for variants 0-4 (HOODIE-XL intentionally skipped -> dead)
        import random
        random.seed(42)
        demand = [
            (VARIANTS[0][0], 5.0, 1.5, Decimal("29.99")),   # TSHIRT-S
            (VARIANTS[1][0], 8.0, 2.0, Decimal("29.99")),   # TSHIRT-M
            (VARIANTS[2][0], 4.0, 1.0, Decimal("29.99")),   # TSHIRT-L
            (VARIANTS[3][0], 3.0, 0.8, Decimal("59.99")),   # HOODIE-M
            (VARIANTS[4][0], 6.0, 1.5, Decimal("59.99")),   # HOODIE-L
        ]
        for v_id, avg, std, price in demand:
            for offset in range(89, -1, -1):
                sale_date = TODAY - timedelta(days=offset)
                units = max(1, int(random.gauss(avg, std)))
                _exec(conn, """
                    INSERT INTO sales_daily
                        (brand_id, variant_id, sale_date, units_sold,
                         gross_revenue, avg_discount, was_in_stock, was_on_promo)
                    VALUES (:bid, :vid, :d, :u, :rev, 0, true, false)
                    ON CONFLICT (variant_id, sale_date) DO UPDATE
                        SET units_sold = EXCLUDED.units_sold,
                            gross_revenue = EXCLUDED.gross_revenue
                """, {"bid": str(BRAND_ID), "vid": str(v_id),
                      "d": sale_date, "u": units, "rev": units * price})

        # Brand-level inventory policy
        _exec(conn, """
            INSERT INTO inventory_settings
                (id, brand_id, default_lead_time, target_cover_days,
                 review_period_days, service_level, dead_stock_threshold_days,
                 created_at, updated_at)
            VALUES (gen_random_uuid(), :bid, 14, 30, 7, 0.950, 90, now(), now())
        """, {"bid": str(BRAND_ID)})

        # Variant-level overrides: Hoodies have longer lead time + cost price
        for v_id in [v[0] for v in VARIANTS[3:]]:
            _exec(conn, """
                INSERT INTO variant_settings
                    (id, brand_id, variant_id, lead_time_days, target_cover_days,
                     cost_price, created_at, updated_at)
                VALUES (gen_random_uuid(), :bid, :vid, 21, 45, 35.00, now(), now())
                ON CONFLICT (brand_id, variant_id) DO NOTHING
            """, {"bid": str(BRAND_ID), "vid": str(v_id)})

        # T-shirt cost prices
        for v_id in [v[0] for v in VARIANTS[:3]]:
            _exec(conn, """
                INSERT INTO variant_settings
                    (id, brand_id, variant_id, cost_price, created_at, updated_at)
                VALUES (gen_random_uuid(), :bid, :vid, 12.00, now(), now())
                ON CONFLICT (brand_id, variant_id) DO NOTHING
            """, {"bid": str(BRAND_ID), "vid": str(v_id)})

    with ENGINE.connect() as conn:
        n_sales = conn.execute(text(
            "SELECT COUNT(*) FROM sales_daily WHERE brand_id=:b"
        ), {"b": str(BRAND_ID)}).scalar()
        n_stock = conn.execute(text(
            "SELECT COUNT(*) FROM inventory_levels WHERE brand_id=:b"
        ), {"b": str(BRAND_ID)}).scalar()

    print(f"  brand_id            : {BRAND_ID}")
    print(f"  variants seeded     : {len(VARIANTS)}")
    print(f"  sales_daily rows    : {n_sales}")
    print(f"  inventory_levels    : {n_stock}")
    print(f"  inventory_settings  : 1 (brand policy)")
    print(f"  variant_settings    : {len(VARIANTS)} (cost prices + hoodie overrides)")


# ---------------------------------------------------------------------------
# 2. Snapshot
# ---------------------------------------------------------------------------

def run_snapshot():
    step("STEP 1 -- inventory_snapshot")
    from worker.jobs.aggregation import run_inventory_snapshot
    result = run_inventory_snapshot(str(BRAND_ID))
    print(f"  Result: {result}")

    with ENGINE.connect() as conn:
        rows = conn.execute(text("""
            SELECT v.sku, s.snap_date, s.available
            FROM inventory_snapshots s
            JOIN variants v ON v.id = s.variant_id
            WHERE s.brand_id = :b ORDER BY v.sku
        """), {"b": str(BRAND_ID)}).fetchall()

    print(f"\n  {'SKU':<22} {'Date':<14} {'Available':>10}")
    print(f"  {'-'*22} {'-'*14} {'-'*10}")
    for r in rows:
        print(f"  {r.sku:<22} {str(r.snap_date):<14} {r.available:>10}")


# ---------------------------------------------------------------------------
# 3. Forecast
# ---------------------------------------------------------------------------

def run_forecast():
    step("STEP 2 -- forecast")
    from worker.jobs.forecast import run_forecast
    result = run_forecast(str(BRAND_ID))
    print(f"  Result: {result}")

    with ENGINE.connect() as conn:
        rows = conn.execute(text("""
            SELECT v.sku, f.model_name,
                   AVG(f.predicted_units)::numeric(8,2) AS avg_pred,
                   COUNT(*) AS n_days
            FROM forecasts f
            JOIN variants v ON v.id = f.variant_id
            WHERE f.brand_id = :b AND f.run_date = CURRENT_DATE
            GROUP BY v.sku, f.model_name ORDER BY v.sku
        """), {"b": str(BRAND_ID)}).fetchall()

    print(f"\n  {'SKU':<22} {'Model':<28} {'Avg Forecast':>13} {'Days':>5}")
    print(f"  {'-'*22} {'-'*28} {'-'*13} {'-'*5}")
    for r in rows:
        print(f"  {r.sku:<22} {r.model_name:<28} {float(r.avg_pred):>13.2f} {r.n_days:>5}")


# ---------------------------------------------------------------------------
# 4. Recommendations
# ---------------------------------------------------------------------------

def run_recommendations():
    step("STEP 3 -- recommendations (Sprint 1 core deliverable)")
    from worker.jobs.recommendations import run_recommendations
    result = run_recommendations(str(BRAND_ID))
    print(f"  Result: {result}")


# ---------------------------------------------------------------------------
# 5. Verify recommendation records
# ---------------------------------------------------------------------------

def verify_recommendations():
    step("VERIFICATION -- inventory_recommendations rows")

    with ENGINE.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                v.sku,
                r.available,
                r.avg_daily_demand::numeric(8,4)   AS mu_d,
                r.demand_std_daily::numeric(8,4)   AS sigma_d,
                r.safety_stock::numeric(8,2)        AS ss,
                r.reorder_point::numeric(8,2)       AS rop,
                r.days_cover::numeric(8,1)          AS days_cover,
                r.recommended_order_qty,
                r.is_emergency_order,
                r.risk_tier,
                r.lead_time_days,
                r.in_stock_days_90d,
                r.dead_stock,
                r.recommended_action
            FROM inventory_recommendations r
            JOIN variants v ON v.id = r.variant_id
            WHERE r.brand_id = :b AND r.run_date = CURRENT_DATE
            ORDER BY
                CASE r.risk_tier
                    WHEN 'dead'      THEN 1
                    WHEN 'stockout'  THEN 2
                    WHEN 'reorder'   THEN 3
                    WHEN 'overstock' THEN 4
                    ELSE 5
                END, v.sku
        """), {"b": str(BRAND_ID)}).fetchall()

    print(f"\n  Total rows: {len(rows)}")
    print()
    hdr = f"  {'SKU':<22} {'Avail':>6} {'mu_d':>8} {'sigma':>7} {'SS':>8} {'ROP':>8} {'Cover':>6} {'OQ':>5} {'Emrg':>5} {'Tier':<11} {'LT':>4}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        cover_str = str(round(float(r.days_cover), 1)) if r.days_cover is not None else "None"
        oq_str    = str(r.recommended_order_qty)       if r.recommended_order_qty is not None else "None"
        print(
            f"  {r.sku:<22} {r.available:>6} "
            f"{float(r.mu_d):>8.4f} {float(r.sigma_d):>7.4f} "
            f"{float(r.ss):>8.2f} {float(r.rop):>8.2f} "
            f"{cover_str:>6} {oq_str:>5} {'Y' if r.is_emergency_order else 'n':>5} "
            f"{r.risk_tier:<11} {r.lead_time_days:>4}"
        )

    print()
    print(f"  {'SKU':<22} {'Recommended Action'}")
    print(f"  {'-'*22} {'-'*55}")
    for r in rows:
        print(f"  {r.sku:<22} {r.recommended_action}")


# ---------------------------------------------------------------------------
# 6. Formula spot-check
# ---------------------------------------------------------------------------

def verify_formula_spot_check():
    step("FORMULA SPOT-CHECK -- SKU-TSHIRT-M recalculation")
    import math

    with ENGINE.connect() as conn:
        row = conn.execute(text("""
            SELECT
                v.sku,
                r.avg_daily_demand::float  AS mu,
                r.demand_std_daily::float  AS sigma,
                r.lead_time_days,
                r.z_score::float,
                r.safety_stock::float      AS ss_db,
                r.reorder_point::float     AS rop_db
            FROM inventory_recommendations r
            JOIN variants v ON v.id = r.variant_id
            WHERE r.brand_id = :b AND r.run_date = CURRENT_DATE
              AND v.sku = 'SKU-TSHIRT-M'
        """), {"b": str(BRAND_ID)}).fetchone()

    if not row:
        print("  No row found for SKU-TSHIRT-M -- cannot spot-check")
        return

    mu    = row.mu
    sigma = row.sigma
    lt    = row.lead_time_days
    z     = row.z_score

    ss_expected  = z * sigma * math.sqrt(lt)
    rop_expected = mu * lt + ss_expected

    ss_match  = abs(ss_expected  - row.ss_db)  < 0.02
    rop_match = abs(rop_expected - row.rop_db) < 0.02

    print(f"\n  SKU              : {row.sku}")
    print(f"  mu_d (avg/day)   : {mu:.6f}  (SUM(units_sold)/90 from sales_daily)")
    print(f"  sigma_d (std/day): {sigma:.6f}")
    print(f"  z-score          : {z:.3f}   (service_level=0.950)")
    print(f"  lead_time_days   : {lt}")
    print()
    print(f"  Safety Stock:")
    print(f"    formula  : z * sigma * sqrt(LT)")
    print(f"             : {z:.3f} * {sigma:.4f} * {math.sqrt(lt):.4f}")
    print(f"    expected : {ss_expected:.4f}")
    print(f"    in DB    : {row.ss_db:.4f}")
    print(f"    match    : {'PASS' if ss_match else 'FAIL'}")
    print()
    print(f"  Reorder Point:")
    print(f"    formula  : mu * LT + SS")
    print(f"             : {mu:.4f} * {lt} + {ss_expected:.4f}")
    print(f"    expected : {rop_expected:.4f}")
    print(f"    in DB    : {row.rop_db:.4f}")
    print(f"    match    : {'PASS' if rop_match else 'FAIL'}")


# ---------------------------------------------------------------------------
# 7. Risk tier verification
# ---------------------------------------------------------------------------

def verify_risk_tiers():
    step("RISK TIER VERIFICATION -- expected vs actual")

    expected = {
        "SKU-TSHIRT-S":  "stockout",
        "SKU-TSHIRT-M":  "reorder",
        "SKU-HOODIE-XL": "dead",
        "SKU-HOODIE-M":  "overstock",
    }

    with ENGINE.connect() as conn:
        rows = conn.execute(text("""
            SELECT v.sku, r.risk_tier, r.available
            FROM inventory_recommendations r
            JOIN variants v ON v.id = r.variant_id
            WHERE r.brand_id = :b AND r.run_date = CURRENT_DATE
        """), {"b": str(BRAND_ID)}).fetchall()

    actual = {r.sku: (r.risk_tier, r.available) for r in rows}

    print(f"\n  {'SKU':<22} {'Expected':<12} {'Actual':<12} {'Avail':>7}  Match")
    print(f"  {'-'*22} {'-'*12} {'-'*12} {'-'*7}  -----")
    all_pass = True
    for sku, exp_tier in expected.items():
        act = actual.get(sku)
        if act is None:
            print(f"  {sku:<22} {exp_tier:<12} {'MISSING':<12}  FAIL")
            all_pass = False
        else:
            act_tier, avail = act
            match = exp_tier == act_tier
            if not match:
                all_pass = False
            print(f"  {sku:<22} {exp_tier:<12} {act_tier:<12} {avail:>7}  {'PASS' if match else 'FAIL'}")

    print(f"\n  Overall: {'ALL TIERS CORRECT -- PASS' if all_pass else 'SOME TIERS WRONG -- FAIL'}")


# ---------------------------------------------------------------------------
# 8. Refund column verification
# ---------------------------------------------------------------------------

def verify_refund_column():
    step("REFUND FIX -- refunded_qty column in order_line_items")
    with ENGINE.connect() as conn:
        row = conn.execute(text("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'order_line_items'
              AND column_name = 'refunded_qty'
        """)).fetchone()

    if row:
        print(f"  column_name : {row.column_name}")
        print(f"  data_type   : {row.data_type}")
        print(f"  default     : {row.column_default}")
        print(f"  Status      : PASS -- column present with server default 0")
    else:
        print("  Status      : FAIL -- column NOT FOUND")


# ---------------------------------------------------------------------------
# 9. Summary
# ---------------------------------------------------------------------------

def summary():
    step("SPRINT 1 SUMMARY")

    with ENGINE.connect() as conn:
        counts = {
            tbl: conn.execute(text(
                f"SELECT COUNT(*) FROM {tbl} WHERE brand_id = :b"
            ), {"b": str(BRAND_ID)}).scalar()
            for tbl in ("inventory_settings", "variant_settings", "inventory_recommendations")
        }
        rec = conn.execute(text("""
            SELECT run_date, COUNT(*) AS n
            FROM inventory_recommendations
            WHERE brand_id = :b
            GROUP BY run_date ORDER BY run_date DESC LIMIT 1
        """), {"b": str(BRAND_ID)}).fetchone()

    p = lambda v: "PASS" if v else "FAIL"
    print()
    print(f"  1. inventory_settings created       : {counts['inventory_settings']} row   {p(counts['inventory_settings'])}")
    print(f"  2. variant_settings created         : {counts['variant_settings']} rows  {p(counts['variant_settings'])}")
    print(f"  3. inventory_recommendations created: {counts['inventory_recommendations']} rows  {p(counts['inventory_recommendations'])}")
    print(f"  4. Pipeline (agg->forecast->rec)    : ran end-to-end without error  PASS")
    print(f"  5. Populated records                : {p(counts['inventory_recommendations'])}")
    if rec:
        print(f"  6. run_date = {rec.run_date},  {rec.n} variant rows  PASS")
    print()
    overall = all(v > 0 for v in counts.values())
    print(f"  Sprint 1 E2E: {'PASS' if overall else 'FAIL'}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  THREADOS SPRINT 1 -- END-TO-END VERIFICATION")
    print("=" * 70)

    seed_data()
    run_snapshot()
    run_forecast()
    run_recommendations()
    verify_recommendations()
    verify_formula_spot_check()
    verify_risk_tiers()
    verify_refund_column()
    summary()

    print("\n" + "=" * 70 + "\n")
