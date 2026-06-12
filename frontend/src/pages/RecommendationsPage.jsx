import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { gbp, num, formatDateShort, daysFromNow } from "@/lib/format";
import { PageHeader } from "@/components/common/PageHeader";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { RiskBadge } from "@/components/common/RiskBadge";
import { WhyRecommendationPanel } from "@/components/common/WhyRecommendationPanel";
import { HowWeCalculateButton } from "@/components/common/HowWeCalculate";
import { CreatePOModal } from "@/components/common/CreatePOModal";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, Search, ShoppingBag, Sparkles } from "lucide-react";

const RISKS = [
  { value: "all", label: "All risks" },
  { value: "high_stockout", label: "High stockout" },
  { value: "medium_stockout", label: "Medium stockout" },
  { value: "healthy", label: "Healthy" },
  { value: "medium_overstock", label: "Medium overstock" },
  { value: "high_overstock", label: "High overstock" },
];

export default function RecommendationsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [risk, setRisk] = useState("all");
  const [open, setOpen] = useState(null);
  const [cats, setCats] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [category, setCategory] = useState("all");
  const [supplierId, setSupplierId] = useState("all");
  const [poItem, setPoItem] = useState(null);

  useEffect(() => {
    api.get("/products", { params: { page_size: 5 } }).then((r) => setCats(r.data.categories || []));
    api.get("/suppliers").then((r) => setSuppliers(r.data.items || []));
  }, []);

  const reload = () => {
    setLoading(true);
    const params = { risk, category, supplier_id: supplierId };
    if (q) params.q = q;
    api
      .get("/recommendations", { params })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, risk, category, supplierId]);

  const exportCsv = () => {
    if (!data?.items?.length) return;
    const headers = [
      "SKU", "Name", "Category", "Supplier", "Current stock", "Sales velocity/day", "Forecast 30d", "Forecast 90d", "Recommended qty", "Reorder by", "Confidence (%)", "Order cost (GBP)", "Risk",
    ];
    const rows = data.items.map((i) => [
      i.sku_id,
      `"${i.name.replace(/"/g, '""')}"`,
      i.category,
      i.supplier_name || "",
      i.current_stock,
      i.daily_forecast,
      i.forecast_30,
      i.forecast_90,
      i.recommended_qty,
      i.reorder_by_date,
      i.confidence,
      i.order_cost,
      i.risk_label,
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `threados-recommendations-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid="recommendations-page">
      <PageHeader
        title="Buy recommendations"
        subtitle="What to order, how much, and when — with the reasoning for every line."
        actions={
          <div className="flex items-center gap-2">
            <HowWeCalculateButton />
            <Button
              variant="default"
              onClick={exportCsv}
              disabled={loading || !data?.items?.length}
              data-testid="recommendations-export-button"
            >
              <Download className="h-4 w-4" /> Export CSV
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        <SummaryTile label="SKUs to order" value={loading ? "\u2014" : num(data.total)} hint="Actionable" />
        <SummaryTile label="Units to order" value={loading ? "\u2014" : num(data.total_order_units)} hint="Across all SKUs" />
        <SummaryTile label="Estimated capital" value={loading ? "\u2014" : gbp(data.total_order_cost)} hint="At unit cost" />
      </div>

      {!loading && data?.by_supplier?.length > 0 && (
        <Card className="mb-4" data-testid="recommendations-by-supplier">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground mb-3">
              Capital allocation by supplier
            </div>
            <div className="flex flex-wrap gap-2">
              {data.by_supplier.map((b) => (
                <button
                  key={b.supplier_id}
                  onClick={() => setSupplierId(b.supplier_id === supplierId ? "all" : b.supplier_id)}
                  className={`text-left rounded-lg border px-3 py-2 transition-colors ${supplierId === b.supplier_id ? "border-foreground/40 bg-muted" : "border-border bg-card hover:bg-muted/60"}`}
                  data-testid={`recommendations-supplier-chip-${b.supplier_id}`}
                >
                  <div className="text-xs font-medium">{b.supplier_name}</div>
                  <div className="text-[11px] text-muted-foreground tabular-nums">
                    {num(b.sku_count)} SKUs · {num(b.units)}u · {gbp(b.cost)}
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="mb-4">
        <CardContent className="p-4 flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="h-4 w-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-testid="recommendations-search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search SKUs"
              className="pl-8"
            />
          </div>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-full md:w-[180px]" data-testid="recommendations-category-select">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {cats.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={supplierId} onValueChange={setSupplierId}>
            <SelectTrigger className="w-full md:w-[220px]" data-testid="recommendations-supplier-select">
              <SelectValue placeholder="Supplier" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All suppliers</SelectItem>
              {suppliers.map((s) => (
                <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={risk} onValueChange={setRisk}>
            <SelectTrigger className="w-full md:w-[200px]" data-testid="recommendations-risk-select">
              <SelectValue placeholder="Risk" />
            </SelectTrigger>
            <SelectContent>
              {RISKS.map((r) => (
                <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto scroll-fade">
            <table className="w-full text-sm" data-testid="recommendations-table">
              <thead className="bg-muted/40 border-b border-border">
                <tr className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Product</th>
                  <th className="text-left px-4 py-3 font-medium">Supplier</th>
                  <th className="text-right px-4 py-3 font-medium">Stock</th>
                  <th className="text-right px-4 py-3 font-medium">90d Fc</th>
                  <th className="text-right px-4 py-3 font-medium">Order</th>
                  <th className="text-left px-4 py-3 font-medium">Reorder by</th>
                  <th className="text-right px-4 py-3 font-medium">Capital</th>
                  <th className="text-left px-4 py-3 font-medium">Risk</th>
                  <th className="text-left px-4 py-3 font-medium">Confidence</th>
                  <th className="text-right px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        <td colSpan={11} className="px-4 py-3">
                          <Skeleton className="h-5 w-full" />
                        </td>
                      </tr>
                    ))
                  : data?.items?.length
                  ? data.items.map((i) => {
                      const days = daysFromNow(i.reorder_by_date);
                      return (
                        <tr
                          key={i.sku_id}
                          className="border-b border-border hover:bg-muted/40 transition-colors cursor-pointer"
                          data-testid={`recommendation-row-${i.sku_id}`}
                          onClick={() => setOpen(i)}
                        >
                          <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                            <Link to={`/products/${i.sku_id}`} onClick={(e) => e.stopPropagation()} className="hover:text-foreground">
                              {i.sku_id}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            <Link to={`/products/${i.sku_id}`} onClick={(e) => e.stopPropagation()} className="font-medium hover:underline">
                              {i.name}
                            </Link>
                            <div className="text-xs text-muted-foreground">{i.category}</div>
                          </td>
                          <td className="px-4 py-3 text-xs text-muted-foreground">{i.supplier_name || "\u2014"}</td>
                          <td className="px-4 py-3 text-right tabular-nums">{num(i.current_stock)}</td>
                          <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{num(i.forecast_90)}</td>
                          <td className="px-4 py-3 text-right tabular-nums font-semibold">{num(i.recommended_qty)}</td>
                          <td className="px-4 py-3 text-sm">
                            <div>{formatDateShort(i.reorder_by_date)}</div>
                            <div className="text-xs text-muted-foreground">{days <= 0 ? "now" : `in ${days}d`}</div>
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">{gbp(i.order_cost)}</td>
                          <td className="px-4 py-3"><RiskBadge bucket={i.bucket} /></td>
                          <td className="px-4 py-3 w-[170px]"><ConfidenceBar value={i.confidence} /></td>
                          <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                            <div className="flex items-center gap-1 justify-end">
                              <Button variant="ghost" size="sm" onClick={() => setOpen(i)} data-testid={`recommendation-why-${i.sku_id}`}>
                                <Sparkles className="h-4 w-4" /> Why
                              </Button>
                              <Button variant="secondary" size="sm" onClick={() => setPoItem(i)} data-testid={`recommendation-create-po-${i.sku_id}`}>
                                <ShoppingBag className="h-4 w-4" /> PO
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  : (
                    <tr>
                      <td colSpan={11} className="px-4 py-12 text-center text-sm text-muted-foreground" data-testid="recommendations-empty-state">
                        No buy recommendations match these filters.
                      </td>
                    </tr>
                  )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Sheet open={!!open} onOpenChange={(v) => !v && setOpen(null)}>
        <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto" data-testid="recommendations-explanation-drawer">
          {open && (
            <>
              <SheetHeader>
                <SheetTitle className="font-display">{open.name}</SheetTitle>
              </SheetHeader>
              <div className="mt-4">
                <WhyRecommendationPanel
                  item={open}
                  onCreatePO={(it) => {
                    setPoItem(it);
                  }}
                  onOpenSku={() => setOpen(null)}
                />
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      <CreatePOModal
        open={!!poItem}
        onOpenChange={(v) => !v && setPoItem(null)}
        item={poItem}
        onCreated={() => {
          setPoItem(null);
        }}
      />
    </div>
  );
}

function SummaryTile({ label, value, hint }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground">{label}</div>
        <div className="font-display text-2xl font-semibold tabular-nums mt-1.5">{value}</div>
        {hint && <div className="text-xs text-muted-foreground mt-0.5">{hint}</div>}
      </CardContent>
    </Card>
  );
}
