import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { num, num1, formatDateShort } from "@/lib/format";
import { PageHeader } from "@/components/common/PageHeader";
import { RiskBadge } from "@/components/common/RiskBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { Search } from "lucide-react";

const BUCKET_COLOR = {
  high_stockout: "risk-high",
  medium_stockout: "risk-med",
  healthy: "risk-healthy",
  medium_overstock: "warning",
  high_overstock: "warning",
};

const ORDER = ["high_stockout", "medium_stockout", "healthy", "medium_overstock", "high_overstock"];

export default function RisksPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bucket, setBucket] = useState("all");
  const [q, setQ] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    const params = { bucket };
    if (q) params.q = q;
    api
      .get("/risks", { params })
      .then((r) => active && setData(r.data))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [bucket, q]);

  return (
    <div data-testid="risks-page">
      <PageHeader
        title="Risk centre"
        subtitle="Spot stockouts and overstock before they cost you."
      />

      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-6"
        data-testid="risk-bucket-cards"
      >
        {ORDER.map((b) => {
          const item = data?.summary?.find((s) => s.bucket === b) || {
            bucket: b,
            label: "",
            count: 0,
            definition: "",
          };
          const color = BUCKET_COLOR[b];
          const active = bucket === b;
          return (
            <button
              key={b}
              data-testid={`risk-bucket-${b.replace("_", "-")}`}
              onClick={() => setBucket(active ? "all" : b)}
              className={cn(
                "text-left rounded-lg border bg-card p-4 transition-all hover:shadow-sm",
                active ? "border-foreground/40 shadow-sm" : "border-border"
              )}
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: `hsl(var(--${color}))` }}
                />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-[0.06em]">
                  {item.label || b}
                </span>
              </div>
              <div className="font-display text-2xl font-semibold mt-1.5 tabular-nums">
                {loading ? "—" : item.count}
              </div>
              <div className="text-xs text-muted-foreground mt-1 leading-snug line-clamp-3">
                {item.definition}
              </div>
            </button>
          );
        })}
      </div>

      <Card className="mb-4">
        <CardContent className="p-4 flex flex-col md:flex-row gap-3 md:items-center">
          <div className="relative flex-1">
            <Search className="h-4 w-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-testid="risks-search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by SKU or product name"
              className="pl-8"
            />
          </div>
          <div className="text-xs text-muted-foreground">
            {bucket === "all" ? "Showing all risks" : `Filter: ${data?.summary?.find((s) => s.bucket === bucket)?.label}`}
          </div>
          {bucket !== "all" && (
            <button
              onClick={() => setBucket("all")}
              className="text-xs text-foreground hover:underline"
              data-testid="risks-clear-filter"
            >
              Clear filter
            </button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto scroll-fade">
            <table className="w-full text-sm" data-testid="risks-table">
              <thead className="bg-muted/40 border-b border-border">
                <tr className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Product</th>
                  <th className="text-right px-4 py-3 font-medium">Stock</th>
                  <th className="text-right px-4 py-3 font-medium">Days cover</th>
                  <th className="text-right px-4 py-3 font-medium">Lead</th>
                  <th className="text-left px-4 py-3 font-medium">Risk</th>
                  <th className="text-left px-4 py-3 font-medium">Why</th>
                  <th className="text-right px-4 py-3 font-medium">Order</th>
                  <th className="text-left px-4 py-3 font-medium">Reorder by</th>
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        <td colSpan={9} className="px-4 py-3">
                          <Skeleton className="h-5 w-full" />
                        </td>
                      </tr>
                    ))
                  : data?.items?.length
                  ? data.items.map((i) => (
                      <tr
                        key={i.sku_id}
                        className="border-b border-border hover:bg-muted/40 transition-colors"
                        data-testid={`risks-row-${i.sku_id}`}
                      >
                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                          <Link to={`/products/${i.sku_id}`} className="hover:text-foreground">
                            {i.sku_id}
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <Link to={`/products/${i.sku_id}`} className="font-medium hover:underline">
                            {i.name}
                          </Link>
                          <div className="text-xs text-muted-foreground">{i.category}</div>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">{num(i.current_stock)}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{num1(i.days_of_stock)}d</td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{i.lead_time_days}d</td>
                        <td className="px-4 py-3">
                          <RiskBadge bucket={i.bucket} label={i.label} />
                        </td>
                        <td className="px-4 py-3 text-foreground/85 max-w-[320px]">{i.reason}</td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {i.recommended_qty > 0 ? num(i.recommended_qty) : <span className="text-muted-foreground">—</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          {i.recommended_qty > 0 ? formatDateShort(i.reorder_by_date) : "—"}
                        </td>
                      </tr>
                    ))
                  : (
                      <tr>
                        <td colSpan={9} className="px-4 py-12 text-center text-sm text-muted-foreground" data-testid="risks-empty-state">
                          No SKUs in this bucket.
                        </td>
                      </tr>
                    )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
