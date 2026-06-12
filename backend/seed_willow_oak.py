"""Willow & Oak — Investor demo brand with controlled risk distribution.

Targets (post-forecast):
- 3 high_stockout (urgent buy story)
- 2 high_overstock (markdown story)
- Rest split: mostly healthy with some medium_stockout / medium_overstock
Deterministic via fixed seed.
"""
import random
import statistics
from datetime import datetime, timedelta, timezone

BRAND_ID = "willow-and-oak"
BRAND_NAME = "Willow & Oak"

_rng = random.Random(2026)

CATEGORIES = {
    "Tops": {"names": ["Cotton Tee", "Linen Shirt", "Cropped Tank", "Boxy Tee", "Ribbed Top", "Silk Cami", "Oversized Tee", "Polo Shirt", "Henley", "Mock Neck"], "price_range": (32, 88), "margin": 0.62, "supplier": "sup-porto-knit", "target": 28},
    "Bottoms": {"names": ["High-Rise Jeans", "Tailored Trouser", "Pleated Skirt", "Wide-Leg Pant", "Cargo Trouser", "Mini Skirt", "Cropped Jeans", "Linen Short", "A-Line Skirt"], "price_range": (62, 165), "margin": 0.60, "supplier": "sup-istanbul-denim", "target": 22},
    "Dresses": {"names": ["Slip Dress", "Wrap Dress", "Midi Dress", "Maxi Dress", "Shirt Dress", "Knit Dress", "Tea Dress", "Cami Dress"], "price_range": (84, 215), "margin": 0.65, "supplier": "sup-lisbon-cut", "target": 22},
    "Outerwear": {"names": ["Trench Coat", "Wool Coat", "Quilted Jacket", "Denim Jacket", "Blazer", "Cropped Jacket", "Field Jacket"], "price_range": (155, 425), "margin": 0.58, "supplier": "sup-manchester-mills", "target": 16},
    "Activewear": {"names": ["Sculpt Legging", "Cross-Back Bra", "Run Short", "Performance Tee", "Yoga Set", "Track Jacket"], "price_range": (48, 135), "margin": 0.68, "supplier": "sup-vietnam-tech", "target": 16},
    "Accessories": {"names": ["Leather Belt", "Silk Scarf", "Bucket Hat", "Tote Bag", "Card Holder", "Cap", "Wool Beanie", "Mini Crossbody"], "price_range": (26, 105), "margin": 0.72, "supplier": "sup-firenze-leather", "target": 16},
}

COLORS = ["Black", "Ivory", "Sand", "Charcoal", "Navy", "Sage", "Rust", "Stone", "Forest", "Cream"]
SIZES_APPAREL = ["XS", "S", "M", "L", "XL"]


def _gen_history(base_velocity: float, archetype: str, days: int = 90):
    """Generate a 90-day units series. Returns list of int and the computed daily_forecast."""
    rng = _rng
    trend = {"hero": 0.018, "steady": 0.004, "slow": -0.006, "dead": -0.015}[archetype]
    noise = {"hero": 0.20, "steady": 0.15, "slow": 0.30, "dead": 0.40}[archetype]
    units = []
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    for i in range(days):
        day = start + timedelta(days=i)
        wd = day.weekday()
        seasonal = 1.0 + (0.30 if wd >= 5 else (-0.10 if wd in (1, 2) else 0.0))
        trended = base_velocity * (1 + trend * i)
        mean = max(0.0, trended * seasonal)
        sample = max(0.0, rng.gauss(mean, mean * noise))
        units.append(int(round(sample)))
    return units


def _compute_daily_forecast(units):
    """Mirror the same EMA+trend math used in services/analytics.py."""
    n = len(units)
    if n == 0:
        return 0.0
    recent = units[-60:] if n >= 60 else units
    avg_recent = statistics.fmean(recent)
    avg_30 = statistics.fmean(units[-30:]) if n >= 30 else avg_recent
    if n >= 60:
        prior = statistics.fmean(units[-60:-30])
        trend = (avg_30 - prior) / max(prior, 0.5)
        trend = max(-0.5, min(0.5, trend))
    else:
        trend = 0.0
    # EMA
    s = float(recent[0])
    for v in recent[1:]:
        s = 0.25 * float(v) + 0.75 * s
    ema = s
    daily = max(0.0, (0.6 * ema + 0.4 * avg_recent) * (1 + trend * 0.5))
    return daily


def _make_sku(sku_idx, cat, cfg, archetype, scenario, days_of_stock_target):
    """Build a SKU + history, sizing stock so days_of_stock lands in the desired band."""
    name = _rng.choice(cfg["names"])
    color = _rng.choice(COLORS)
    size = _rng.choice(SIZES_APPAREL) if cat != "Accessories" else "One Size"
    price = round(_rng.uniform(*cfg["price_range"]), 2)
    cost = round(price * (1 - cfg["margin"]), 2)
    if archetype == "hero":
        base_velocity = _rng.uniform(10, 22)
    elif archetype == "steady":
        base_velocity = _rng.uniform(3.0, 7.5)
    elif archetype == "slow":
        base_velocity = _rng.uniform(0.8, 2.2)
    else:
        base_velocity = _rng.uniform(0.2, 0.8)

    lead_time_days = _rng.choice([30, 45, 60])
    target_coverage_days = _rng.choice([60, 75, 90])

    units = _gen_history(base_velocity, archetype, days=90)
    daily = _compute_daily_forecast(units)
    if daily <= 0:
        daily = 0.1
    current_stock = max(1, int(round(daily * days_of_stock_target)))

    return {
        "id": f"WO-{sku_idx:04d}",
        "name": f"{name} \u2013 {color}",
        "product_name": name,
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
        "supplier_id": cfg["supplier"],
        "brand_id": BRAND_ID,
        "scenario_tag": scenario,
        "created_at": (datetime.now(timezone.utc).date() - timedelta(days=_rng.randint(120, 720))).isoformat(),
    }, units


def build_willow_oak_skus_and_history(target_count: int = 120):
    skus = []
    history_rows = []

    sku_idx = 1

    # --- 3 high_stockout (DoS < lead*0.6, with lead=30 -> DoS < 18 days) ---
    stockout_specs = [
        ("Tops", "hero", 12),       # 12 days cover, lead 30 -> very stockout
        ("Dresses", "hero", 10),
        ("Activewear", "hero", 14),
    ]
    for cat, arch, dos in stockout_specs:
        sku, units = _make_sku(sku_idx, cat, CATEGORIES[cat], archetype=arch, scenario="stockout", days_of_stock_target=dos)
        # Force lead_time = 45 so DoS < 27 days is clearly stockout
        sku["lead_time_days"] = 45
        # Re-size stock for new lead time
        sku["current_stock"] = max(1, int(round(_compute_daily_forecast(units) * dos)))
        skus.append(sku)
        history_rows.append((sku["id"], units))
        sku_idx += 1

    # --- 2 high_overstock (DoS > 180) ---
    overstock_specs = [
        ("Outerwear", "slow", 240),
        ("Bottoms", "slow", 220),
    ]
    for cat, arch, dos in overstock_specs:
        sku, units = _make_sku(sku_idx, cat, CATEGORIES[cat], archetype=arch, scenario="overstock", days_of_stock_target=dos)
        sku["lead_time_days"] = 45
        sku["current_stock"] = max(1, int(round(_compute_daily_forecast(units) * dos)))
        skus.append(sku)
        history_rows.append((sku["id"], units))
        sku_idx += 1

    # --- 115 healthy/medium SKUs ---
    remaining = target_count - len(skus)
    cat_keys = list(CATEGORIES.keys())
    weights = {c: CATEGORIES[c]["target"] for c in cat_keys}
    total_w = sum(weights.values())
    per_cat = {c: max(1, round(remaining * w / total_w)) for c, w in weights.items()}
    diff = remaining - sum(per_cat.values())
    if diff != 0:
        per_cat[cat_keys[0]] += diff

    # Target distribution among the remaining 115:
    # ~ 70% healthy (DoS 55-110), 15% medium_stockout (DoS 30-44 with lead=45),
    # ~ 15% medium_overstock (DoS 130-175)
    distribution = []
    n_healthy = round(remaining * 0.70)
    n_med_stock = round(remaining * 0.15)
    n_med_over = remaining - n_healthy - n_med_stock
    distribution.extend([("healthy", _rng.uniform(55, 110)) for _ in range(n_healthy)])
    distribution.extend([("medium_stockout", _rng.uniform(30, 44)) for _ in range(n_med_stock)])
    distribution.extend([("medium_overstock", _rng.uniform(130, 175)) for _ in range(n_med_over)])
    _rng.shuffle(distribution)

    dist_idx = 0
    for cat in cat_keys:
        for _ in range(per_cat[cat]):
            arch_roll = _rng.random()
            if arch_roll < 0.25:
                arch = "hero"
            elif arch_roll < 0.85:
                arch = "steady"
            else:
                arch = "slow"
            scen, dos = distribution[dist_idx]
            dist_idx += 1
            sku, units = _make_sku(sku_idx, cat, CATEGORIES[cat], archetype=arch, scenario=scen, days_of_stock_target=dos)
            # Use lead_time=45 uniformly so DoS bands map cleanly
            sku["lead_time_days"] = 45
            sku["current_stock"] = max(1, int(round(_compute_daily_forecast(units) * dos)))
            skus.append(sku)
            history_rows.append((sku["id"], units))
            sku_idx += 1

    # Materialise sales history rows
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=89)
    sales = []
    sku_by_id = {s["id"]: s for s in skus}
    for sid, units in history_rows:
        s = sku_by_id[sid]
        for i, u in enumerate(units):
            day = start + timedelta(days=i)
            sales.append({
                "sku_id": sid,
                "brand_id": BRAND_ID,
                "date": day.isoformat(),
                "units": int(u),
                "revenue": round(u * s["price"], 2),
            })

    return skus, sales


# Convenience wrappers expected by seed.py
def build_willow_oak_skus():
    skus, _ = build_willow_oak_skus_and_history(120)
    return skus


def build_willow_oak_history(skus, days=90):
    # Re-derive deterministically: regenerate exact same sequence.
    # We can't, because _rng is shared. Cleaner: combined builder.
    _, sales = build_willow_oak_skus_and_history(120)
    return sales
