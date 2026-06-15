"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { recommendations, inventory, auth } from "@/lib/api-client";
import type {
  RecommendationItemResponse,
  RecommendationListResponse,
  RecommendationSummaryResponse,
  RecommendationDetailResponse,
  InventorySummaryItemResponse,
} from "@threados/shared-types";
import { AppNav } from "@/components/AppNav";
import { SummaryCards } from "@/components/inventory/SummaryCards";
import { RiskBadge } from "@/components/inventory/RiskBadge";
import { DetailPanel } from "@/components/inventory/DetailPanel";

const TIER_FILTERS = [
  { value: "", label: "All" },
  { value: "stockout", label: "Stockout" },
  { value: "reorder", label: "Reorder" },
  { value: "overstock", label: "Overstock" },
  { value: "dead", label: "Dead Stock" },
  { value: "healthy", label: "Healthy" },
] as const;

const PAGE_SIZE = 25;

// ---------------------------------------------------------------------------
// Demo mode: injected when ?demo=true, bypasses auth + API calls
// ---------------------------------------------------------------------------
const DEMO_SUMMARY: RecommendationSummaryResponse = {
  run_date: "2026-06-14T10:00:00Z",
  total_variants: 48,
  tier_counts: [
    { tier: "stockout", count: 4 },
    { tier: "reorder", count: 11 },
    { tier: "overstock", count: 7 },
    { tier: "dead", count: 3 },
    { tier: "healthy", count: 23 },
  ],
  total_revenue_at_risk: "12480.00",
  total_capital_trapped: "8250.00",
  emergency_orders: 2,
};

const DEMO_ID_1 = "00000000-0001-0001-0001-000000000001";
const DEMO_ID_2 = "00000000-0002-0002-0002-000000000002";
const DEMO_ID_3 = "00000000-0003-0003-0003-000000000003";
const DEMO_ID_4 = "00000000-0004-0004-0004-000000000004";
const DEMO_ID_5 = "00000000-0005-0005-0005-000000000005";

function demoItem(
  id: string,
  variantId: string,
  tier: "stockout" | "reorder" | "overstock" | "dead" | "healthy",
  available: number,
  daysCover: string | null,
  stockoutDate: string | null,
  orderQty: number | null,
  emergency: boolean,
  revenueAtRisk: string | null,
  capitalTrapped: string | null,
): RecommendationItemResponse {
  return {
    id,
    variant_id: variantId,
    run_date: "2026-06-14",
    run_at: "2026-06-14T10:00:00Z",
    available,
    lead_time_days: 14,
    target_cover_days: 30,
    review_period_days: 7,
    z_score: "1.645",
    in_stock_days_90d: 87,
    avg_daily_demand: "1.43",
    demand_std_daily: "0.62",
    days_cover: daysCover,
    stockout_date: stockoutDate,
    safety_stock: "9.2",
    reorder_point: "22.0",
    recommended_order_qty: orderQty,
    is_emergency_order: emergency,
    overstock_units: tier === "overstock" ? 80 : null,
    excess_cover_days: tier === "overstock" ? "38.5" : null,
    dead_stock: tier === "dead",
    risk_tier: tier,
    recommended_action:
      tier === "stockout"
        ? "Place an emergency order immediately. Stock will be depleted soon."
        : tier === "reorder"
          ? "Reorder now to maintain your target cover days."
          : tier === "overstock"
            ? "Consider promotions or bundles to reduce excess inventory."
            : tier === "dead"
              ? "This SKU has had no sales in 90+ days. Consider liquidation."
              : "Stock levels are healthy.",
    revenue_at_risk: revenueAtRisk,
    capital_trapped: capitalTrapped,
    created_at: "2026-06-14T10:00:00Z",
  };
}

const DEMO_LIST: RecommendationListResponse = {
  items: [
    demoItem("r1", DEMO_ID_1, "stockout", 2, "1.4", "2026-06-17", 120, true, "1720.00", null),
    demoItem("r2", DEMO_ID_2, "stockout", 18, "6.2", "2026-06-21", 80, true, "2340.00", null),
    demoItem("r3", DEMO_ID_3, "reorder", 45, "14.1", null, 60, false, null, null),
    demoItem("r4", DEMO_ID_4, "overstock", 210, "68.5", null, null, false, null, "8250.00"),
    demoItem("r5", DEMO_ID_5, "dead", 94, "180.0", null, null, false, null, "2100.00"),
  ],
  total: 25,
  page: 1,
  page_size: 25,
  run_date: "2026-06-14T10:00:00Z",
};

const DEMO_SKU_MAP: [string, InventorySummaryItemResponse][] = [
  [DEMO_ID_1, { variant_id: DEMO_ID_1, sku: "TS-BLK-M", variant_title: "Black / M", product_title: "Classic Tee", total_available: 2 }],
  [DEMO_ID_2, { variant_id: DEMO_ID_2, sku: "TS-WHT-L", variant_title: "White / L", product_title: "Classic Tee", total_available: 18 }],
  [DEMO_ID_3, { variant_id: DEMO_ID_3, sku: "HD-NVY-S", variant_title: "Navy / S", product_title: "Pullover Hoodie", total_available: 45 }],
  [DEMO_ID_4, { variant_id: DEMO_ID_4, sku: "JK-GRN-XL", variant_title: "Forest / XL", product_title: "Track Jacket", total_available: 210 }],
  [DEMO_ID_5, { variant_id: DEMO_ID_5, sku: "SH-BLU-32", variant_title: "Blue / 32", product_title: "Slim Chinos", total_available: 94 }],
];

const DEMO_DETAIL: RecommendationDetailResponse = {
  latest: demoItem("r1", DEMO_ID_1, "stockout", 2, "1.4", "2026-06-17", 120, true, "1720.00", null),
  history: [
    demoItem("r1", DEMO_ID_1, "stockout", 2, "1.4", "2026-06-17", 120, true, "1720.00", null),
    demoItem("r0", DEMO_ID_1, "reorder", 18, "12.6", null, 60, false, null, null),
  ],
};

function fmt(val: string | null | undefined, decimals = 1): string {
  if (!val) return "—";
  const n = parseFloat(val);
  return isNaN(n) ? "—" : n.toFixed(decimals);
}

function fmtDate(val: string | null | undefined): string {
  if (!val) return "—";
  return new Date(val).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
  });
}

function InventoryPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemoMode = searchParams.get("demo") === "true";

  // Data state
  const [summary, setSummary] = useState<RecommendationSummaryResponse | null>(null);
  const [listData, setListData] = useState<RecommendationListResponse | null>(null);
  const [skuMap, setSkuMap] = useState<Map<string, InventorySummaryItemResponse>>(new Map());
  const [detail, setDetail] = useState<RecommendationDetailResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // UI state
  const [tier, setTier] = useState<string>("");
  const [page, setPage] = useState(1);
  const [summaryLoading, setSummaryLoading] = useState(!isDemoMode);
  const [listLoading, setListLoading] = useState(!isDemoMode);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auth guard (skipped in demo mode)
  useEffect(() => {
    if (!isDemoMode) {
      auth.me().catch(() => router.push("/login"));
    }
  }, [router, isDemoMode]);

  // Demo mode — inject mock data immediately
  useEffect(() => {
    if (!isDemoMode) return;
    setSummary(DEMO_SUMMARY);
    setListData(DEMO_LIST);
    setSkuMap(new Map(DEMO_SKU_MAP));
    setSummaryLoading(false);
    setListLoading(false);
  }, [isDemoMode]);

  // Fetch summary cards
  useEffect(() => {
    if (isDemoMode) return;
    setSummaryLoading(true);
    recommendations
      .summary()
      .then(setSummary)
      .catch(() => setError("Failed to load summary."))
      .finally(() => setSummaryLoading(false));
  }, [isDemoMode]);

  // Fetch SKU names once — failure is non-fatal (falls back to variant ID display)
  useEffect(() => {
    if (isDemoMode) return;
    inventory
      .summary({ page: 1, page_size: 100 })
      .then((res) => {
        const m = new Map<string, InventorySummaryItemResponse>();
        for (const item of res.items) {
          m.set(item.variant_id, item);
        }
        setSkuMap(m);
      })
      .catch(() => {
        // SKU names are display-only; silently degrade to variant ID.
      });
  }, [isDemoMode]);

  // Fetch recommendation list
  const fetchList = useCallback(
    (newPage: number, newTier: string) => {
      if (isDemoMode) return;
      setListLoading(true);
      const params: {
        page: number;
        page_size: number;
        risk_tier?: string;
      } = { page: newPage, page_size: PAGE_SIZE };
      if (newTier) {
        params.risk_tier = newTier;
      }
      recommendations
        .list(params)
        .then(setListData)
        .catch(() => setError("Failed to load recommendations."))
        .finally(() => setListLoading(false));
    },
    [],
  );

  useEffect(() => {
    fetchList(page, tier);
  }, [fetchList, page, tier]);

  const handleTierChange = (newTier: string) => {
    setTier(newTier);
    setPage(1);
    setSelectedId(null);
    setDetail(null);
  };

  const handleSelectRow = useCallback(
    async (item: RecommendationItemResponse) => {
      if (item.variant_id === selectedId) {
        setSelectedId(null);
        setDetail(null);
        return;
      }
      setSelectedId(item.variant_id);
      if (isDemoMode) {
        setDetail(DEMO_DETAIL);
        return;
      }
      setDetailLoading(true);
      setDetail(null);
      try {
        const d = await recommendations.get(item.variant_id);
        setDetail(d);
      } catch {
        setDetail(null);
      } finally {
        setDetailLoading(false);
      }
    },
    [selectedId, isDemoMode],
  );

  const skuLabel = (variantId: string): string => {
    const info = skuMap.get(variantId);
    if (info?.sku) return info.sku;
    if (info?.variant_title) return info.variant_title;
    return variantId.slice(0, 8) + "…";
  };

  const productLabel = (variantId: string): string => {
    const info = skuMap.get(variantId);
    return info?.product_title ?? "";
  };

  const items = listData?.items ?? [];
  const total = listData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const runDate = listData?.run_date ?? summary?.run_date;

  return (
    <div className="min-h-screen bg-gray-50">
      <AppNav activePath="inventory" />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Inventory Intelligence</h1>
            <p className="text-sm text-gray-500 mt-1">
              {runDate ? (
                <>
                  Last run:{" "}
                  <span className="font-medium text-gray-700">
                    {new Date(runDate).toLocaleDateString("en-GB", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </>
              ) : summaryLoading ? (
                "Loading…"
              ) : (
                "No recommendations run yet"
              )}
            </p>
          </div>
          <Link
            href="/inventory/settings"
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 font-medium hover:bg-gray-50"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Settings
          </Link>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => {
                setError(null);
                fetchList(page, tier);
              }}
              className="ml-4 text-sm font-medium text-red-700 underline hover:text-red-900 whitespace-nowrap"
            >
              Retry
            </button>
          </div>
        )}

        {/* Summary cards */}
        <div className="mb-6">
          <SummaryCards
            tierCounts={summary?.tier_counts ?? []}
            totalRevAtRisk={parseFloat(summary?.total_revenue_at_risk ?? "0")}
            emergencyOrders={summary?.emergency_orders ?? 0}
            loading={summaryLoading}
          />
        </div>

        {/* Empty state — no runs */}
        {!summaryLoading && !listLoading && summary?.run_date === null && (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 className="mt-3 text-sm font-semibold text-gray-900">No recommendations yet</h3>
            <p className="mt-1 text-sm text-gray-500">
              Run a sync to generate inventory recommendations.
            </p>
            <Link
              href="/dashboard"
              className="mt-4 inline-flex items-center gap-1 text-sm text-brand-600 font-medium hover:text-brand-700"
            >
              Go to Dashboard to trigger a sync →
            </Link>
          </div>
        )}

        {/* Recommendation table */}
        {(listLoading || (listData && listData.run_date !== null)) && (
          <>
            {/* Risk tier filter */}
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              {TIER_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => handleTierChange(f.value)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                    tier === f.value
                      ? "bg-brand-600 text-white border-brand-600"
                      : "bg-white text-gray-600 border-gray-300 hover:border-gray-400 hover:text-gray-800"
                  }`}
                >
                  {f.label}
                  {f.value !== "" &&
                    summary?.tier_counts.find((t) => t.tier === f.value) && (
                      <span className="ml-1.5 opacity-70">
                        ({summary.tier_counts.find((t) => t.tier === f.value)?.count ?? 0})
                      </span>
                    )}
                </button>
              ))}
            </div>

            {/* Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        SKU / Variant
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Available
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Days Cover
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Stockout Date
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Reorder Qty
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Risk Tier
                      </th>
                      <th className="px-4 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {listLoading
                      ? Array.from({ length: 5 }).map((_, i) => (
                          <tr key={i} className="animate-pulse">
                            {Array.from({ length: 7 }).map((__, j) => (
                              <td key={j} className="px-4 py-3">
                                <div className="h-4 bg-gray-100 rounded" />
                              </td>
                            ))}
                          </tr>
                        ))
                      : items.map((item) => {
                          const isSelected = item.variant_id === selectedId;
                          return (
                            <tr
                              key={item.id}
                              onClick={() => {
                                void handleSelectRow(item);
                              }}
                              className={`cursor-pointer transition-colors ${
                                isSelected
                                  ? "bg-brand-50 border-l-2 border-brand-500"
                                  : "hover:bg-gray-50"
                              }`}
                            >
                              <td className="px-4 py-3">
                                <div className="text-sm font-medium text-gray-900">
                                  {skuLabel(item.variant_id)}
                                </div>
                                {productLabel(item.variant_id) && (
                                  <div className="text-xs text-gray-500 mt-0.5 truncate max-w-[180px]">
                                    {productLabel(item.variant_id)}
                                  </div>
                                )}
                              </td>
                              <td className="px-4 py-3 text-right text-sm text-gray-700 tabular-nums">
                                {item.available.toLocaleString()}
                              </td>
                              <td className="px-4 py-3 text-right text-sm text-gray-700 tabular-nums">
                                {fmt(item.days_cover, 1)}
                              </td>
                              <td className="px-4 py-3 text-right text-sm text-gray-700">
                                {fmtDate(item.stockout_date)}
                              </td>
                              <td className="px-4 py-3 text-right text-sm text-gray-700 tabular-nums">
                                {item.recommended_order_qty !== null
                                  ? item.recommended_order_qty.toLocaleString()
                                  : "—"}
                              </td>
                              <td className="px-4 py-3">
                                <RiskBadge tier={item.risk_tier} />
                              </td>
                              <td className="px-4 py-3 text-right">
                                <span className="text-xs text-gray-400">
                                  {isSelected ? "▾" : "▸"}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                  </tbody>
                </table>
              </div>

              {/* Empty table state */}
              {!listLoading && items.length === 0 && (
                <div className="px-4 py-10 text-center">
                  <p className="text-sm text-gray-500 font-medium">
                    {tier ? `No ${tier} variants found.` : "No recommendations found."}
                  </p>
                  {tier && (
                    <button
                      onClick={() => handleTierChange("")}
                      className="mt-2 text-sm text-brand-600 hover:text-brand-700 font-medium"
                    >
                      Clear filter
                    </button>
                  )}
                </div>
              )}

              {/* Pagination — only shown when there are multiple pages */}
              {!listLoading && total > PAGE_SIZE && (
                <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between">
                  <p className="text-sm text-gray-500">
                    {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total} variants
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* Detail slide-over */}
      {(selectedId !== null || detailLoading) && selectedId !== null && (
        <DetailPanel
          variantId={selectedId}
          detail={detail}
          loading={detailLoading}
          skuLabel={skuLabel(selectedId)}
          onClose={() => {
            setSelectedId(null);
            setDetail(null);
          }}
        />
      )}
    </div>
  );
}

export default function InventoryPage() {
  return (
    <Suspense>
      <InventoryPageInner />
    </Suspense>
  );
}
