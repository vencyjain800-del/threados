"""Seed realistic ThreadOS data: 40 SKUs, 90 days history, 6 UK/EU suppliers."""
import random
from datetime import datetime, timedelta, timezone
from db import db

random.seed(42)

CATEGORIES = {
    "Tops": {
        "names": ["Cotton Tee", "Linen Blouse", "Cropped Tank", "Boxy Tee", "Ribbed Top", "Silk Cami", "Oversized Tee", "Polo Shirt"],
        "price_range": (28, 78),
        "margin": 0.62,
        "supplier": "sup-porto-knit",
    },
    "Bottoms": {
        "names": ["High-Rise Jeans", "Tailored Trouser", "Pleated Skirt", "Wide-Leg Pant", "Cargo Trouser", "Mini Skirt", "Cropped Jeans"],
        "price_range": (58, 145),
        "margin": 0.60,
        "supplier": "sup-istanbul-denim",
    },
    "Dresses": {
        "names": ["Slip Dress", "Wrap Dress", "Midi Dress", "Maxi Dress", "Shirt Dress", "Knit Dress"],
        "price_range": (78, 195),
        "margin": 0.65,
        "supplier": "sup-lisbon-cut",
    },
    "Outerwear": {
        "names": ["Trench Coat", "Wool Coat", "Quilted Jacket", "Denim Jacket", "Blazer"],
        "price_range": (145, 385),
        "margin": 0.58,
        "supplier": "sup-manchester-mills",
    },
    "Activewear": {
        "names": ["Sculpt Legging", "Cross-Back Bra", "Run Short", "Performance Tee", "Yoga Set"],
        "price_range": (45, 125),
        "margin": 0.68,
        "supplier": "sup-vietnam-tech",
    },
    "Accessories": {
        "names": ["Leather Belt", "Silk Scarf", "Bucket Hat", "Tote Bag", "Card Holder", "Cap"],
        "price_range": (24, 95),
        "margin": 0.72,
        "supplier": "sup-firenze-leather",
    },
}

SUPPLIERS = [
    {"id": "sup-porto-knit", "name": "Porto Knitwear Co.", "country": "Portugal", "city": "Porto", "contact_name": "Mariana Silva", "contact_email": "mariana@portoknit.example", "specialty": "Jersey, ribbed knits, sustainable cottons", "lead_time_days": 45, "min_order_value": 2500, "currency": "GBP", "rating": 4.7, "notes": "Reliable, good with small reorders. GOTS certified."},
    {"id": "sup-istanbul-denim", "name": "Istanbul Denim Atelier", "country": "Türkiye", "city": "İstanbul", "contact_name": "Cem Yılmaz", "contact_email": "cem@istanbuldenim.example", "specialty": "Selvedge denim, tailored trousers, washes", "lead_time_days": 60, "min_order_value": 5000, "currency": "GBP", "rating": 4.5, "notes": "Strong on denim. Ask for wash development lead time."},
    {"id": "sup-lisbon-cut", "name": "Lisbon Cut & Sew", "country": "Portugal", "city": "Lisboa", "contact_name": "Inez Costa", "contact_email": "inez@lisboncutsew.example", "specialty": "Dresses, blouses, finishing", "lead_time_days": 50, "min_order_value": 3500, "currency": "GBP", "rating": 4.8, "notes": "Beautiful finish quality. Books up fast in autumn."},
    {"id": "sup-manchester-mills", "name": "Manchester Mills", "country": "United Kingdom", "city": "Manchester", "contact_name": "Jamie O’Brien", "contact_email": "jamie@manchestermills.example", "specialty": "Outerwear, technical fabrics, wool", "lead_time_days": 75, "min_order_value": 8000, "currency": "GBP", "rating": 4.3, "notes": "UK-based, longer lead but reliable for AW drops."},
    {"id": "sup-vietnam-tech", "name": "Saigon Performance", "country": "Vietnam", "city": "Ho Chi Minh City", "contact_name": "Linh Tran", "contact_email": "linh@saigonperf.example", "specialty": "Activewear, recycled poly, seamless", "lead_time_days": 70, "min_order_value": 6000, "currency": "GBP", "rating": 4.6, "notes": "Sea freight only \u2014 budget for the lead."},
    {"id": "sup-firenze-leather", "name": "Firenze Pelle Studio", "country": "Italy", "city": "Firenze", "contact_name": "Giulia Romano", "contact_email": "giulia@firenzepelle.example", "specialty": "Belts, small leather goods, accessories", "lead_time_days": 40, "min_order_value": 1500, "currency": "GBP", "rating": 4.9, "notes": "Boutique scale. Pricier but very fast for top-ups."},
]

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
                "supplier_id": cfg["supplier"],
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
        trend_per_day = {"hero": random.uniform(0.01, 0.04), "steady": random.uniform(-0.005, 0.015), "slow": random.uniform(-0.02, 0.005), "dead": random.uniform(-0.03, -0.005)}[sku["archetype"]]
        noise = {"hero": 0.35, "steady": 0.25, "slow": 0.45, "dead": 0.55}[sku["archetype"]]
        for i in range(days):
            day = start + timedelta(days=i)
            weekday = day.weekday()
            seasonal = 1.0 + (0.35 if weekday >= 5 else (-0.12 if weekday in (1, 2) else 0.0))
            trended = v * (1 + trend_per_day * i)
            mean = max(0.0, trended * seasonal)
            sample = max(0.0, random.gauss(mean, mean * noise))
            units = int(round(sample))
            history.append({"sku_id": sku["id"], "date": day.isoformat(), "units": units, "revenue": round(units * sku["price"], 2)})
    return history


async def seed_if_empty() -> int:
    sup_existing = await db.suppliers.count_documents({})
    if sup_existing == 0:
        await db.suppliers.insert_many(SUPPLIERS)
        await db.suppliers.create_index("id", unique=True)

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
    await db.products.create_index("supplier_id")
    await db.purchase_orders.create_index("id", unique=True)
    await db.purchase_orders.create_index("status")
    return len(skus)


async def ensure_supplier_links() -> None:
    cat_to_sup = {c: cfg["supplier"] for c, cfg in CATEGORIES.items()}
    async for p in db.products.find({"$or": [{"supplier_id": {"$exists": False}}, {"supplier_id": None}]}, {"_id": 0, "id": 1, "category": 1}):
        sup = cat_to_sup.get(p["category"]) or "sup-porto-knit"
        await db.products.update_one({"id": p["id"]}, {"$set": {"supplier_id": sup}})
