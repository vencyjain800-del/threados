"use client";

import type { RecommendationDetailResponse } from "@threados/shared-types";
import { RiskBadge } from "./RiskBadge";

interface DetailPanelProps {
  variantId: string;
  detail: RecommendationDetailResponse | null;
  loading: boolean;
  skuLabel: string;
  onClose: () => void;
}

function fmt(val: string | null | undefined, decimals = 2): string {
  if (val === null || val === undefined) return "—";
  const n = parseFloat(val);
  return isNaN(n) ? val : n.toFixed(decimals);
}

function fmtDate(val: string | null | undefined): string {
  if (!val) return "—";
  return new Date(val).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function DetailPanel({
  variantId,
  detail,
  loading,
  skuLabel,
  onClose,
}: DetailPanelProps) {
  const latest = detail?.latest ?? null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end" aria-modal="true">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/20"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative w-full max-w-md bg-white shadow-xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
              Variant detail
            </p>
            <p className="text-sm font-semibold text-gray-900 mt-0.5">{skuLabel}</p>
            <p className="text-xs text-gray-400 font-mono mt-0.5">
              {variantId.slice(0, 18)}…
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-6">
          {loading && (
            <div className="space-y-3 animate-pulse">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-4 bg-gray-100 rounded" />
              ))}
            </div>
          )}

          {!loading && !latest && (
            <p className="text-sm text-gray-400 text-center py-8">
              No recommendation data available.
            </p>
          )}

          {!loading && latest && (
            <>
              {/* Risk tier + action */}
              <div className="space-y-2">
                <RiskBadge tier={latest.risk_tier} size="md" />
                <p className="text-sm text-gray-700">{latest.recommended_action}</p>
              </div>

              {/* Current inventory */}
              <section>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Current Inventory
                </h4>
                <dl className="space-y-2">
                  <Row label="Available units" value={String(latest.available)} />
                  <Row label="Days of cover" value={fmt(latest.days_cover, 1)} />
                  <Row
                    label="Stockout date"
                    value={fmtDate(latest.stockout_date)}
                    highlight={latest.stockout_date !== null}
                  />
                </dl>
              </section>

              {/* Forecast demand */}
              <section>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Forecast Demand
                </h4>
                <dl className="space-y-2">
                  <Row label="Avg daily demand" value={`${fmt(latest.avg_daily_demand, 2)} units`} />
                  <Row label="Demand std dev" value={`±${fmt(latest.demand_std_daily, 2)} units`} />
                  <Row label="In-stock days (90d)" value={`${latest.in_stock_days_90d} days`} />
                </dl>
              </section>

              {/* Replenishment model */}
              <section>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Replenishment
                </h4>
                <dl className="space-y-2">
                  <Row label="Safety stock" value={`${fmt(latest.safety_stock, 0)} units`} />
                  <Row label="Reorder point" value={`${fmt(latest.reorder_point, 0)} units`} />
                  <Row
                    label="Recommended order qty"
                    value={
                      latest.recommended_order_qty !== null
                        ? `${latest.recommended_order_qty} units`
                        : "None required"
                    }
                    highlight={latest.recommended_order_qty !== null}
                  />
                  {latest.is_emergency_order && (
                    <div className="mt-1 rounded bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700 font-medium">
                      Emergency order — lead time exceeds cover window
                    </div>
                  )}
                </dl>
              </section>

              {/* Settings used */}
              <section>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Policy Settings
                </h4>
                <dl className="space-y-2">
                  <Row label="Lead time" value={`${latest.lead_time_days} days`} />
                  <Row label="Target cover" value={`${latest.target_cover_days} days`} />
                  <Row label="Service level (z)" value={fmt(latest.z_score, 3)} />
                  {latest.overstock_units !== null && (
                    <Row label="Overstock units" value={String(latest.overstock_units)} />
                  )}
                  {latest.excess_cover_days !== null && (
                    <Row label="Excess cover" value={`${fmt(latest.excess_cover_days, 1)} days`} />
                  )}
                </dl>
              </section>

              {/* Value metrics */}
              {(latest.revenue_at_risk !== null || latest.capital_trapped !== null) && (
                <section>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    Financial Impact
                  </h4>
                  <dl className="space-y-2">
                    {latest.revenue_at_risk !== null && (
                      <Row
                        label="Revenue at risk"
                        value={`$${parseFloat(latest.revenue_at_risk).toLocaleString("en-US", { maximumFractionDigits: 2 })}`}
                        highlight
                      />
                    )}
                    {latest.capital_trapped !== null && (
                      <Row
                        label="Capital trapped"
                        value={`$${parseFloat(latest.capital_trapped).toLocaleString("en-US", { maximumFractionDigits: 2 })}`}
                      />
                    )}
                  </dl>
                </section>
              )}

              {/* History */}
              {detail !== null && detail.history.length > 1 && (
                <section>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    Recommendation History
                  </h4>
                  <ul className="space-y-1.5">
                    {detail.history.map((h, i) => (
                      <li
                        key={h.id}
                        className="flex items-center justify-between text-xs py-1.5 border-b border-gray-100 last:border-0"
                      >
                        <span className="text-gray-500">
                          {fmtDate(h.run_date)}
                          {i === 0 && (
                            <span className="ml-1.5 text-brand-600 font-medium">(latest)</span>
                          )}
                        </span>
                        <RiskBadge tier={h.risk_tier} />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd
        className={`text-sm font-medium ${highlight ? "text-gray-900" : "text-gray-700"}`}
      >
        {value}
      </dd>
    </div>
  );
}
