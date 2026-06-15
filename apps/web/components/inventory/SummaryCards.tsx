"use client";

import type { TierCountResponse } from "@threados/shared-types";
import { tierCardClasses, tierLabel } from "./RiskBadge";

const SUMMARY_TIERS = ["stockout", "reorder", "overstock", "dead"] as const;

interface SummaryCardsProps {
  tierCounts: TierCountResponse[];
  totalRevAtRisk: number;
  emergencyOrders: number;
  loading: boolean;
}

export function SummaryCards({
  tierCounts,
  totalRevAtRisk,
  emergencyOrders,
  loading,
}: SummaryCardsProps) {
  const getCount = (tier: string): number =>
    tierCounts.find((t) => t.tier === tier)?.count ?? 0;

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {SUMMARY_TIERS.map((tier) => (
          <div
            key={tier}
            className="bg-gray-50 border border-gray-200 rounded-lg p-4 animate-pulse"
          >
            <div className="h-3 bg-gray-200 rounded w-20 mb-3" />
            <div className="h-8 bg-gray-200 rounded w-10 mb-1" />
            <div className="h-3 bg-gray-200 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {SUMMARY_TIERS.map((tier) => {
          const c = tierCardClasses(tier);
          const count = getCount(tier);
          return (
            <div
              key={tier}
              className={`${c.bg} ${c.border} border rounded-lg p-4`}
            >
              <p className={`text-xs font-semibold uppercase tracking-wide ${c.label}`}>
                {tierLabel(tier)}
              </p>
              <p className={`text-3xl font-bold mt-1 ${c.count}`}>{count}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {count === 1 ? "variant" : "variants"}
              </p>
            </div>
          );
        })}
      </div>

      {(totalRevAtRisk > 0 || emergencyOrders > 0) && (
        <div className="flex gap-4 text-sm text-gray-600">
          {totalRevAtRisk > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-red-400" />
              <span>
                Revenue at risk:{" "}
                <span className="font-semibold text-gray-900">
                  ${totalRevAtRisk.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                </span>
              </span>
            </span>
          )}
          {emergencyOrders > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              <span>
                Emergency orders:{" "}
                <span className="font-semibold text-gray-900">{emergencyOrders}</span>
              </span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
