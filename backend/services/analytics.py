"""Forecasting, recommendations, risk classification, and explainability."""
import statistics
from datetime import datetime, timedelta, timezone


def _ema(values, alpha=0.25):
    if not values:
        return 0.0
    s = float(values[0])
    for v in values[1:]:
        s = alpha * float(v) + (1 - alpha) * s
    return s


def forecast_from_history(sales_rows: list[dict]) -> dict:
    units = [int(r.get("units", 0)) for r in sales_rows]
    n = len(units)
    if n == 0:
        return {"daily_forecast": 0.0, "forecast_30": 0, "forecast_60": 0, "forecast_90": 0, "confidence": 50, "method": "no-data", "trend": 0.0, "avg_30": 0.0, "avg_60": 0.0}
    recent = units[-60:] if n >= 60 else units
    avg_recent = statistics.fmean(recent)
    avg_30 = statistics.fmean(units[-30:]) if n >= 30 else avg_recent
    avg_60 = avg_recent
    if n >= 60:
        prior = statistics.fmean(units[-60:-30])
        recent30 = avg_30
        trend = (recent30 - prior) / max(prior, 0.5)
        trend = max(-0.5, min(0.5, trend))
    else:
        trend = 0.0
    ema = _ema([float(u) for u in recent], alpha=0.25)
    daily = max(0.0, (0.6 * ema + 0.4 * avg_recent) * (1 + trend * 0.5))
    mean = statistics.fmean(recent) if recent else 0.0
    if mean <= 0:
        confidence = 45
    else:
        stdev = statistics.pstdev(recent) if len(recent) > 1 else 0.0
        cv = stdev / mean
        confidence = int(round(max(50, min(95, 95 - cv * 38))))
        if mean < 1.0:
            confidence = max(45, confidence - 8)
    return {"daily_forecast": round(daily, 3), "forecast_30": int(round(daily * 30)), "forecast_60": int(round(daily * 60)), "forecast_90": int(round(daily * 90)), "confidence": confidence, "method": "ema+trend", "trend": round(trend, 3), "avg_30": round(avg_30, 2), "avg_60": round(avg_60, 2)}


def recommend_buy(sku: dict, fc: dict) -> dict:
    daily = float(fc["daily_forecast"])
    lead = int(sku["lead_time_days"])
    target_days = int(sku["target_coverage_days"])
    current = int(sku["current_stock"])
    confidence = int(fc["confidence"])
    safety_stock = int(round(daily * 14 * max(0.15, (1 - confidence / 100))))
    stock_at_arrival = max(0, current - daily * lead)
    target_at_arrival = daily * target_days + safety_stock
    order_qty = int(round(max(0, target_at_arrival - stock_at_arrival)))
    days_of_stock = (current / daily) if daily > 0 else 999.0
    buffer_days = 7
    reorder_by_in = max(0, days_of_stock - lead - buffer_days)
    reorder_by_date = (datetime.now(timezone.utc).date() + timedelta(days=int(min(365, reorder_by_in)))).isoformat()
    return {"recommended_qty": order_qty, "reorder_by_date": reorder_by_date, "days_of_stock": round(min(999.0, days_of_stock), 1), "stock_at_arrival": int(round(stock_at_arrival)), "target_at_arrival": int(round(target_at_arrival)), "safety_stock": safety_stock, "confidence": confidence, "lead_time_days": lead, "target_coverage_days": target_days}


RISK_LABELS = {"high_stockout": "High Stockout Risk", "medium_stockout": "Medium Stockout Risk", "healthy": "Healthy Inventory", "medium_overstock": "Medium Overstock Risk", "high_overstock": "High Overstock Risk"}


def classify_risk(sku: dict, fc: dict) -> dict:
    daily = float(fc["daily_forecast"])
    current = int(sku["current_stock"])
    lead = int(sku["lead_time_days"])
    days_of_stock = (current / daily) if daily > 0 else 999.0
    coverage_ratio = days_of_stock / max(lead, 1)
    if days_of_stock < lead * 0.6:
        bucket = "high_stockout"
        reason = f"Only {int(days_of_stock)} days of stock vs {lead} day lead time \u2014 you risk going dark."
    elif days_of_stock < lead * 1.1:
        bucket = "medium_stockout"
        reason = f"{int(days_of_stock)} days of stock barely covers a {lead} day lead time."
    elif days_of_stock > 180:
        bucket = "high_overstock"
        reason = f"{int(min(999, days_of_stock))} days of stock \u2014 capital tied up, markdown risk."
    elif days_of_stock > 120:
        bucket = "medium_overstock"
        reason = f"{int(days_of_stock)} days of stock \u2014 above typical 90 day cover."
    else:
        bucket = "healthy"
        reason = f"{int(days_of_stock)} days of stock \u2014 within a healthy operating range."
    return {"bucket": bucket, "label": RISK_LABELS[bucket], "reason": reason, "days_of_stock": round(min(999.0, days_of_stock), 1), "coverage_ratio": round(coverage_ratio, 2)}


def confidence_tier(c: int):
    if c >= 80:
        return "High", "Sales pattern is steady \u2014 we trust this forecast."
    if c >= 65:
        return "Medium", "Some volatility, but the signal is clear."
    if c >= 55:
        return "Cautious", "Demand is bumpy \u2014 leave some headroom."
    return "Low", "Too little signal \u2014 review before committing capital."


def build_explanation(sku: dict, fc: dict, rec: dict, risk: dict) -> dict:
    daily = fc["daily_forecast"]
    trend_pct = round(fc["trend"] * 100)
    tier, tier_explain = confidence_tier(fc["confidence"])
    qty = rec["recommended_qty"]
    if qty > 0:
        headline = f"Order {qty} units by {rec['reorder_by_date']}."
    else:
        headline = "No order needed right now \u2014 coverage is comfortable."
    drivers = [
        {"key": "velocity", "label": "Sales velocity", "value": f"{daily:.1f} units / day", "detail": f"Last 30 days averaged {fc['avg_30']:.1f}/day. Trend vs prior 30 days: {trend_pct:+d}%."},
        {"key": "stock", "label": "Current stock", "value": f"{sku['current_stock']:,} units", "detail": f"That's {rec['days_of_stock']:.0f} days of cover at the current pace."},
        {"key": "forecast", "label": "Forecast demand", "value": f"{fc['forecast_30']:,} / {fc['forecast_60']:,} / {fc['forecast_90']:,} units", "detail": "Projected units for the next 30 / 60 / 90 days."},
        {"key": "confidence", "label": "Forecast confidence", "value": f"{fc['confidence']}% · {tier}", "detail": tier_explain},
        {"key": "risk", "label": "Stockout risk", "value": risk["label"], "detail": risk["reason"]},
    ]
    if qty > 0:
        math_bullets = [
            f"Lead time: {rec['lead_time_days']} days. Expected stock when order arrives \u2248 {rec['stock_at_arrival']} units.",
            f"Target cover after arrival: {rec['target_coverage_days']} days = {int(daily * rec['target_coverage_days'])} units.",
            f"Safety stock (covers forecast uncertainty): +{rec['safety_stock']} units.",
            f"Target on-hand at arrival: {rec['target_at_arrival']} units.",
            f"Recommended buy = {rec['target_at_arrival']} \u2212 {rec['stock_at_arrival']} = {qty} units.",
        ]
    else:
        math_bullets = [
            f"At {daily:.1f} units/day, {sku['current_stock']:,} units = {rec['days_of_stock']:.0f} days cover.",
            f"Lead time is {rec['lead_time_days']} days \u2014 you have a comfortable buffer.",
        ]
    return {"headline": headline, "drivers": drivers, "math": math_bullets, "confidence_tier": tier}


async def load_sku_history(db, sku_id: str) -> list[dict]:
    cursor = db.sales_history.find({"sku_id": sku_id}, {"_id": 0}).sort("date", 1)
    return await cursor.to_list(length=400)


async def build_full_sku_analytics(db, sku: dict) -> dict:
    rows = await load_sku_history(db, sku["id"])
    fc = forecast_from_history(rows)
    rec = recommend_buy(sku, fc)
    risk = classify_risk(sku, fc)
    units_30 = sum(int(r["units"]) for r in rows[-30:]) if rows else 0
    revenue_30 = sum(float(r.get("revenue", 0)) for r in rows[-30:]) if rows else 0.0
    return {"sku": sku, "forecast": fc, "recommendation": rec, "risk": risk, "units_30d": units_30, "revenue_30d": round(revenue_30, 2), "sales_history": rows, "explanation": build_explanation(sku, fc, rec, risk)}
