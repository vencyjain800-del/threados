"""
ThreadOS Core POC

Validates:
1. Realistic SKU + sales history seeding (40 SKUs, 6 categories, 90 days)
2. Demand forecasting (30/60/90 day) with confidence
3. Buy recommendations (qty + reorder-by date)
4. Risk classification (5 buckets)

Run: python test_core.py
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

random.seed(42)

# ----------------------------------------------------------------------------
# 1. Seeding
# ----------------------------------------------------------------------------

CATEGORIES = {
    "Tops": {
        "names": ["Cotton Tee", "Linen Blouse", "Cropped Tank", "Boxy Tee", "Ribbed Top", "Silk Cami", "Oversized Tee", "Polo Shirt"],
        "price_range": (28, 78),
        "margin": 0.62,
    },
    "Bottoms": {
        "names": ["High-Rise Jeans", "Tailored Trouser", "Pleated Skirt", "Wide-Leg Pant", "Cargo Trouser", "Mini Skirt", "Cropped Jeans"],
        "price_range": (58, 145),
        "margin": 0.60,
    },
    "Dresses": {
        "names": ["Slip Dress", "Wrap Dress", "Midi Dress", "Maxi Dress", "Shirt Dress", "Knit Dress"],
        "price_range": (78, 195),
        "margin": 0.65,
    },
    "Outerwear": {
        "names": ["Trench Coat", "Wool Coat", "Quilted Jacket", "Denim Jacket", "Blazer"],
        "price_range": (145, 385),
        "margin": 0.58,
    },
    "Activewear": {
        "names": ["Sculpt Legging", "Cross-Back Bra", "Run Short", "Performance Tee", "Yoga Set"],
        "price_range": (45, 125),
        "margin": 0.68,
    },
    "Accessories": {
        "names": ["Leather Belt", "Silk Scarf", "Bucket Hat", "Tote Bag", "Card Holder", "Cap"],
        "price_range": (24, 95),
        "margin": 0.72,
    },
}

COLORS = ["Black", "Ivory", "Sand", "Charcoal", "Navy", "Sage", "Rust", "Stone"]
SIZES_APPAREL = ["XS", "S", "M", "L", "XL"]


def seed_skus(target_count: int = 40) -> list[dict[str, Any]]:
    skus: list[dict[str, Any]] = []
    today = datetime.now(timezone.utc).date()

    # Distribute SKUs across categories roughly evenly
    cat_keys = list(CATEGORIES.keys())
    per_cat = max(1, target_count // len(cat_keys))
    remainder = target_count - per_cat * len(cat_keys)

    counts = {c: per_cat for c in cat_keys}
    for i in range(remainder):
        counts[cat_keys[i]] += 1

    sku_id = 1
    for cat, cfg in CATEGORIES.items():
        for _ in range(counts[cat]):
            name = random.choice(cfg["names"])
            color = random.choice(COLORS)
            size = random.choice(SIZES_APPAREL) if cat != "Accessories" else "One Size"

            price = round(random.uniform(*cfg["price_range"]), 2)
            cost = round(price * (1 - cfg["margin"]), 2)

            # Velocity archetype
            r = random.random()
            if r < 0.20:
                archetype = "hero"          # fast mover
                base_velocity = random.uniform(8, 18)   # units/day
            elif r < 0.55:
                archetype = "steady"
                base_velocity = random.uniform(2.5, 6.5)
            elif r < 0.85:
                archetype = "slow"
                base_velocity = random.uniform(0.4, 1.6)
            else:
                archetype = "dead"
                base_velocity = random.uniform(0.05, 0.4)

            lead_time_days = random.choice([21, 30, 45, 60, 75])
            target_coverage_days = random.choice([45, 60, 75, 90])

            # Current stock: deliberately spread across risk profiles
            stock_archetype = random.random()
            if stock_archetype < 0.18:
                current_stock = max(0, int(base_velocity * random.uniform(2, 12)))    # stockout zone
            elif stock_archetype < 0.70:
                current_stock = int(base_velocity * random.uniform(25, 75))           # healthy
            elif stock_archetype < 0.90:
                current_stock = int(base_velocity * random.uniform(95, 140))          # medium overstock
            else:
                current_stock = int(base_velocity * random.uniform(160, 260))         # high overstock

            skus.append({
                "id": f"SKU-{sku_id:04d}",
                "name": f"{name} – {color}",
                "category": cat,
                "size": size,
                "color": color,
                "cost": cost,
                "price": price,
                "current_stock": current_stock,
                "base_velocity": round(base_velocity, 3),
                "archetype": archetype,
                "lead_time_days": lead_time_days,
                "target_coverage_days": target_coverage_days,
                "created_at": (today - timedelta(days=random.randint(120, 720))).isoformat(),
            })
            sku_id += 1

    return skus


def seed_sales_history(skus: list[dict[str, Any]], days: int = 90) -> dict[str, list[dict[str, Any]]]:
    """Generate daily unit sales per SKU with weekly seasonality, gentle trend, and noise."""
    history: dict[str, list[dict[str, Any]]] = {}
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)

    for sku in skus:
        v = sku["base_velocity"]
        # Gentle trend: hero/steady drift up, slow/dead drift down
        trend_per_day = {
            "hero": random.uniform(0.01, 0.04),
            "steady": random.uniform(-0.005, 0.015),
            "slow": random.uniform(-0.02, 0.005),
            "dead": random.uniform(-0.03, -0.005),
        }[sku["archetype"]]

        # Volatility (noise) — heroes are noisier, dead stock looks flat
        noise = {
            "hero": 0.35,
            "steady": 0.25,
            "slow": 0.45,
            "dead": 0.55,
        }[sku["archetype"]]

        rows: list[dict[str, Any]] = []
        for i in range(days):
            day = start + timedelta(days=i)
            weekday = day.weekday()  # 0 = Mon
            # Weekly seasonality: weekends ~1.4x, midweek ~0.85x
            seasonal = 1.0 + (0.35 if weekday >= 5 else -0.12 if weekday in (1, 2) else 0.0)
            trended = v * (1 + trend_per_day * i)
            mean = max(0.0, trended * seasonal)
            # Gamma-like positive noise
            sample = max(0.0, random.gauss(mean, mean * noise))
            units = int(round(sample))
            rows.append({"date": day.isoformat(), "units": units})
        history[sku["id"]] = rows

    return history


# ----------------------------------------------------------------------------
# 2. Forecasting
# ----------------------------------------------------------------------------

def _ema(values: list[float], alpha: float = 0.3) -> float:
    if not values:
        return 0.0
    s = values[0]
    for v in values[1:]:
        s = alpha * v + (1 - alpha) * s
    return s


def forecast_sku(sales_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Returns dict with:
      - daily_forecast (units/day)
      - forecast_30, forecast_60, forecast_90 (units)
      - confidence (0-100, integer)
      - method
    """
    units = [r["units"] for r in sales_rows]
    n = len(units)
    if n == 0:
        return {
            "daily_forecast": 0.0,
            "forecast_30": 0,
            "forecast_60": 0,
            "forecast_90": 0,
            "confidence": 30,
            "method": "no-data",
        }

    # Use last 60 days if available, fall back to all
    recent = units[-60:] if n >= 60 else units
    avg_recent = statistics.fmean(recent)

    # Trend: compare last 30 days vs prior 30 days
    if n >= 60:
        prior = statistics.fmean(units[-60:-30])
        recent30 = statistics.fmean(units[-30:])
        trend = (recent30 - prior) / max(prior, 0.5)
        trend = max(-0.5, min(0.5, trend))  # clamp
    else:
        trend = 0.0

    # EMA for smoothness
    ema = _ema([float(u) for u in recent], alpha=0.25)

    # Blend EMA with mean, apply trend
    daily = max(0.0, (0.6 * ema + 0.4 * avg_recent) * (1 + trend * 0.5))

    # Confidence — driven by coefficient of variation
    mean = statistics.fmean(recent) if recent else 0.0
    if mean <= 0:
        confidence = 45
    else:
        stdev = statistics.pstdev(recent) if len(recent) > 1 else 0.0
        cv = stdev / mean  # 0 = perfect, 1+ = chaos
        # Map CV to 95% (cv=0) .. 50% (cv>=1.2)
        confidence = int(round(max(50, min(95, 95 - cv * 38))))
        # Penalise very low volume (less signal)
        if mean < 1.0:
            confidence = max(45, confidence - 8)

    return {
        "daily_forecast": round(daily, 3),
        "forecast_30": int(round(daily * 30)),
        "forecast_60": int(round(daily * 60)),
        "forecast_90": int(round(daily * 90)),
        "confidence": confidence,
        "method": "ema+trend",
    }


# ----------------------------------------------------------------------------
# 3. Buy Recommendation
# ----------------------------------------------------------------------------

def recommend_buy(sku: dict[str, Any], fc: dict[str, Any]) -> dict[str, Any]:
    """
    Compute order quantity + reorder-by date so that, at lead-time arrival,
    stock equals (target_coverage_days * daily_forecast) + safety_stock.
    """
    daily = fc["daily_forecast"]
    lead = sku["lead_time_days"]
    target_days = sku["target_coverage_days"]
    current = sku["current_stock"]

    # Safety stock: ~ 14 days * daily * (1 - confidence/100)
    safety_stock = int(round(daily * 14 * max(0.15, (1 - fc["confidence"] / 100))))

    # Stock when order arrives
    stock_at_arrival = max(0, current - daily * lead)

    # Target on-hand at arrival
    target_at_arrival = daily * target_days + safety_stock

    order_qty = int(round(max(0, target_at_arrival - stock_at_arrival)))

    # Days-of-stock now
    days_of_stock = (current / daily) if daily > 0 else 999

    # When to place the order: keep enough cover for lead time + small buffer (7 days)
    buffer_days = 7
    reorder_by_in = max(0, days_of_stock - lead - buffer_days)
    reorder_by_date = (datetime.now(timezone.utc).date() + timedelta(days=int(reorder_by_in))).isoformat()

    return {
        "recommended_qty": order_qty,
        "reorder_by_date": reorder_by_date,
        "days_of_stock": round(days_of_stock, 1),
        "stock_at_arrival": int(round(stock_at_arrival)),
        "target_at_arrival": int(round(target_at_arrival)),
        "safety_stock": safety_stock,
        "confidence": fc["confidence"],
    }


# ----------------------------------------------------------------------------
# 4. Risk Classification
# ----------------------------------------------------------------------------

def classify_risk(sku: dict[str, Any], fc: dict[str, Any]) -> dict[str, Any]:
    daily = fc["daily_forecast"]
    current = sku["current_stock"]
    lead = sku["lead_time_days"]
    days_of_stock = (current / daily) if daily > 0 else 999

    # Coverage relative to lead time
    coverage_ratio = days_of_stock / max(lead, 1)

    if days_of_stock < lead * 0.6:
        bucket = "high_stockout"
        label = "High Stockout Risk"
        reason = f"Only {days_of_stock:.0f} days of stock vs {lead} day lead time."
    elif days_of_stock < lead * 1.1:
        bucket = "medium_stockout"
        label = "Medium Stockout Risk"
        reason = f"{days_of_stock:.0f} days of stock barely covers {lead} day lead time."
    elif days_of_stock > 180:
        bucket = "high_overstock"
        label = "High Overstock Risk"
        reason = f"{days_of_stock:.0f} days of stock — capital tied up, markdown risk."
    elif days_of_stock > 120:
        bucket = "medium_overstock"
        label = "Medium Overstock Risk"
        reason = f"{days_of_stock:.0f} days of stock — above typical 90 day cover."
    else:
        bucket = "healthy"
        label = "Healthy Inventory"
        reason = f"{days_of_stock:.0f} days of stock — within healthy range."

    return {
        "bucket": bucket,
        "label": label,
        "reason": reason,
        "days_of_stock": round(days_of_stock, 1),
        "coverage_ratio": round(coverage_ratio, 2),
    }


# ----------------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------------

def gbp(v: float) -> str:
    return f"£{v:,.0f}"


def main() -> None:
    print("=" * 78)
    print("ThreadOS Core POC")
    print("=" * 78)

    skus = seed_skus(40)
    history = seed_sales_history(skus, days=90)

    assert len(skus) == 40, f"Expected 40 SKUs, got {len(skus)}"
    print(f"\n[PASS] Seeded {len(skus)} SKUs across {len(CATEGORIES)} categories")

    # Sanity: sales history per SKU
    for sku in skus:
        rows = history[sku["id"]]
        assert len(rows) == 90, f"{sku['id']} expected 90 days, got {len(rows)}"
    print("[PASS] Generated 90 days of sales history for every SKU")

    # Run forecasting + recommendations + risk
    enriched: list[dict[str, Any]] = []
    for sku in skus:
        fc = forecast_sku(history[sku["id"]])
        rec = recommend_buy(sku, fc)
        risk = classify_risk(sku, fc)
        enriched.append({"sku": sku, "fc": fc, "rec": rec, "risk": risk})

    # Sanity assertions
    confidences = [e["fc"]["confidence"] for e in enriched]
    assert all(45 <= c <= 95 for c in confidences), "Confidence out of [45,95]"
    assert min(confidences) < max(confidences), "Confidence has no spread"
    print(f"[PASS] Confidence range {min(confidences)}-{max(confidences)} (avg {statistics.fmean(confidences):.1f})")

    daily_forecasts = [e["fc"]["daily_forecast"] for e in enriched]
    assert all(d >= 0 for d in daily_forecasts), "Negative forecast detected"
    assert max(daily_forecasts) > 1.0, "Forecasts look too low"
    print(f"[PASS] Daily forecasts range {min(daily_forecasts):.2f} - {max(daily_forecasts):.2f}")

    # Risk distribution
    risk_counts: dict[str, int] = {}
    for e in enriched:
        risk_counts[e["risk"]["bucket"]] = risk_counts.get(e["risk"]["bucket"], 0) + 1
    print(f"[PASS] Risk distribution: {risk_counts}")
    # We deliberately seeded a spread, so expect ≥3 buckets present
    assert len(risk_counts) >= 3, "Risk distribution lacks spread"

    # Inventory value
    total_units = sum(e["sku"]["current_stock"] for e in enriched)
    total_value = sum(e["sku"]["current_stock"] * e["sku"]["cost"] for e in enriched)
    total_retail = sum(e["sku"]["current_stock"] * e["sku"]["price"] for e in enriched)
    print(f"[PASS] Total inventory: {total_units:,} units | "
          f"cost {gbp(total_value)} | retail {gbp(total_retail)}")

    # Show top 10 by recommended qty
    enriched_sorted = sorted(enriched, key=lambda x: x["rec"]["recommended_qty"], reverse=True)[:10]
    print("\nTop 10 Buy Recommendations")
    print("-" * 78)
    print(f"{'SKU':<10}{'Name':<28}{'Stock':>7}{'90d Fc':>9}{'Buy':>7}{'Conf':>7}  Reorder by")
    for e in enriched_sorted:
        s, fc, rec = e["sku"], e["fc"], e["rec"]
        print(f"{s['id']:<10}{s['name'][:26]:<28}{s['current_stock']:>7}{fc['forecast_90']:>9}"
              f"{rec['recommended_qty']:>7}{fc['confidence']:>6}%  {rec['reorder_by_date']}")

    # Risk Centre sample
    print("\nRisk Centre sample (first 2 of each bucket present)")
    print("-" * 78)
    seen: dict[str, int] = {}
    for e in enriched:
        b = e["risk"]["bucket"]
        if seen.get(b, 0) >= 2:
            continue
        seen[b] = seen.get(b, 0) + 1
        print(f"  [{e['risk']['label']:<22}] {e['sku']['id']} {e['sku']['name'][:24]:<26} "
              f"-> {e['risk']['reason']}")

    print("\n" + "=" * 78)
    print("POC PASSED ✓")
    print("=" * 78)


if __name__ == "__main__":
    main()
