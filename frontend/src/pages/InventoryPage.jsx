import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { gbp, num, num1 } from "@/lib/format";
import { PageHeader } from "@/components/common/PageHeader";
import { RiskBadge } from "@/components/common/RiskBadge";
import { Pagination } from "@/components/common/Pagination";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Search } from "lucide-react";

const RISKS = [
  { value: "all", label: "All risks" },
  { value: "high_stockout", label: "High stockout risk" },
  { value: "medium_stockout", label: "Medium stockout risk" },
  { value: "healthy", label: "Healthy" },
  { value: "medium_overstock", label: "Medium overstock risk" },
  { value: "high_overstock", label: "High overstock risk" },
];

const SORTS = [
  { value: "name", label: "Name (A-Z)" },
  { value: "stock_desc", label: "Stock (high to low)" },
  { value: "stock_asc", label: "Stock (low to high)" },
  { value: "days_asc", label: "Days of stock (low)" },
  { value: "days_desc", label: "Days of stock (high)" },
  { value: "revenue_desc", label: "30d revenue (high)" },
  { value: "recommended_desc", label: "Recommended qty (high)" },
];

export default function InventoryPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("all");
  const [risk, setRisk] = useState("all");
  const [sort, setSort] = useState("name");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [suppliers, setSuppliers] = useState([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [supplierId, setSupplierId] = useState(searchParams.get("supplier") || "all");

  useEffect(() => {
    api.get("/suppliers").then((r) => setSuppliers(r.data.items || []));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [q, category, risk, sort, supplierId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const params = { category, risk, sort, supplier_id: supplierId, page, page_size: pageSize };
    if (q) params.q = q;
    api
      .get("/products", { params })
      .then((r) => active && setData(r.data))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [q, category, risk, sort, supplierId, page, pageSize]);

  const categories = data?.categories || [];

  return (
    <div data-testid="inventory-page">
      <PageHeader title="Inventory" subtitle="Every SKU — stock, demand, risk, and recommendation." />

      <Card className="mb-4">
        <CardContent className="p-4 flex flex-col md:flex-row gap-3 md:items-center flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="h-4 w-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-testid="inventory-search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search SKU, name, or category"
              className="pl-8"
            />
          </div>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-full md:w-[170px]" data-testid="inventory-category-select">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={supplierId}
            onValueChange={(v) => {
              setSupplierId(v);
              if (v === "all") {
                searchParams.delete("supplier");
              } else {
                searchParams.set("supplier", v);
              }
              setSearchParams(searchParams, { replace: true });
            }}
          >
            <SelectTrigger className="w-full md:w-[200px]" data-testid="inventory-supplier-select">
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
            <SelectTrigger className="w-full md:w-[200px]" data-testid="inventory-risk-select">
              <SelectValue placeholder="Risk" />
            </SelectTrigger>
            <SelectContent>
              {RISKS.map((r) => (
                <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger className="w-full md:w-[200px]" data-testid="inventory-sort-select">
              <SelectValue placeholder="Sort" />
            </SelectTrigger>
            <SelectContent>
              {SORTS.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}>
            <SelectTrigger className="w-full md:w-[110px]" data-testid="inventory-page-size-select">
              <SelectValue placeholder="Page size" />
            </SelectTrigger>
            <SelectContent>
              {[10, 25, 50, 100].map((n) => (
                <SelectItem key={n} value={String(n)}>{n} / page</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto scroll-fade">
            <table className="w-full text-sm" data-testid="inventory-table">
              <thead className="bg-muted/40 border-b border-border">
                <tr className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Product</th>
                  <th className="text-left px-4 py-3 font-medium">Category</th>
                  <th className="text-left px-4 py-3 font-medium">Supplier</th>
                  <th className="text-right px-4 py-3 font-medium">Stock</th>
                  <th className="text-right px-4 py-3 font-medium">Days cover</th>
                  <th className="text-right px-4 py-3 font-medium">30d revenue</th>
                  <th className="text-right px-4 py-3 font-medium">90d forecast</th>
                  <th className="text-right px-4 py-3 font-medium">Suggested buy</th>
                  <th className="text-left px-4 py-3 font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        <td colSpan={10} className="px-4 py-3">
                          <Skeleton className="h-5 w-full" />
                        </td>
                      </tr>
                    ))
                  : data?.items?.length
                  ? data.items.map((i) => (
                      <tr
                        key={i.sku_id}
                        className="border-b border-border hover:bg-muted/40 transition-colors"
                        data-testid={`inventory-row-${i.sku_id}`}
                      >
                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                          <Link to={`/products/${i.sku_id}`} className="hover:text-foreground">{i.sku_id}</Link>
                        </td>
                        <td className="px-4 py-3">
                          <Link to={`/products/${i.sku_id}`} className="font-medium hover:underline">{i.name}</Link>
                          <div className="text-xs text-muted-foreground">
                            {i.size} · {gbp(i.price)}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{i.category}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{i.supplier_name || "\u2014"}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{num(i.current_stock)}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{num1(i.days_of_stock)}d</td>
                        <td className="px-4 py-3 text-right tabular-nums">{gbp(i.revenue_30d)}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{num(i.forecast_90)}</td>
                        <td className="px-4 py-3 text-right tabular-nums font-medium">
                          {i.recommended_qty > 0 ? num(i.recommended_qty) : <span className="text-muted-foreground">\u2014</span>}
                        </td>
                        <td className="px-4 py-3"><RiskBadge bucket={i.bucket} /></td>
                      </tr>
                    ))
                  : (
                    <tr>
                      <td colSpan={10} className="px-4 py-12 text-center text-sm text-muted-foreground" data-testid="inventory-empty-state">
                        No SKUs match your filters. Try clearing filters.
                      </td>
                    </tr>
                  )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
      {!loading && data && (
        <Pagination
          page={data.page}
          pageCount={data.page_count}
          total={data.total}
          pageSize={data.page_size}
          onChange={(p) => setPage(p)}
        />
      )}
    </div>
  );
}
