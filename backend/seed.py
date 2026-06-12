"""Seed realistic ThreadOS data: 40 SKUs across 6 categories + 90 days history."""
import random
from datetime import datetime, timedelta, timezone
from db import db

random.seed(42)

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


def _build_skus(target_count: int = 40):
    skus = []
    today = datetime.now(timezone.utc).date()
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
            r = random.random()
            if r < 0.20:
                archetype = "hero"
                base_velocity = random.uniform(8, 18)
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

            sa = random.random()
            if sa < 0.18:
                current_stock = max(0, int(base_velocity * random.uniform(2, 12)))
            elif sa < 0.70:
                current_stock = int(base_velocity * random.uniform(25, 75))
            elif sa < 0.90:
                current_stock = int(base_velocity * random.uniform(95, 140))
            else:
                current_stock = int(base_velocity * random.uniform(160, 260))

            skus.append({
                "id": f"SKU-{sku_id:04d}",
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
                "created_at": (today - timedelta(days=random.randint(120, 720))).isoformat(),
            })
            sku_id += 1
    return skus


def _build_history(skus, days=90):
    history = []
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    for sku in skus:
        v = sku["base_velocity"]
        trend_per_day = {
            "hero": random.uniform(0.01, 0.04),
            "steady": random.uniform(-0.005, 0.015),
            "slow": random.uniform(-0.02, 0.005),
            "dead": random.uniform(-0.03, -0.005),
        }[sku["archetype"]]
        noise = {"hero": 0.35, "steady": 0.25, "slow": 0.45, "dead": 0.55}[sku["archetype"]]
        for i in range(days):
            day = start + timedelta(days=i)
            weekday = day.weekday()
            seasonal = 1.0 + (0.35 if weekday >= 5 else (-0.12 if weekday in (1, 2) else 0.0))
            trended = v * (1 + trend_per_day * i)
            mean = max(0.0, trended * seasonal)
            sample = max(0.0, random.gauss(mean, mean * noise))
            units = int(round(sample))
            history.append({
                "sku_id": sku["id"],
                "date": day.isoformat(),
                "units": units,
                "revenue": round(units * sku["price"], 2),
            })
    return history


async def seed_if_empty() -> int:
    existing = await db.products.count_documents({})
    if existing > 0:
        return 0
    skus = _build_skus(40)
    history = _build_history(skus, days=90)
    if skus:
        await db.products.insert_many(skus)
    if history:
        await db.sales_history.insert_many(history)
        await db.sales_history.create_index("sku_id")
        await db.sales_history.create_index("date")
    await db.products.create_index("id", unique=True)
    await db.products.create_index("category")
    return len(skus)


async def reset_and_seed() -> int:
    await db.products.delete_many({})
    await db.sales_history.delete_many({})
    return await seed_if_empty()
