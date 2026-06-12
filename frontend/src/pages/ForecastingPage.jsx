import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { num, num1 } from "@/lib/format";
import { PageHeader } from "@/components/common/PageHeader";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { RiskBadge } from "@/components/common/RiskBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, ArrowUp, ArrowDown, Minus } from "lucide-react";

const SORTS = [
  { value: "confidence_desc", label: "Confidence (high)" },
  { value: "confidence_asc", label: "Confidence (low)" },
  { value: "forecast_desc", label: "30d forecast (high)" },
  { value: "forecast_asc", label: "30d forecast (low)" },
  { value: "name", label: "Name (A-Z)" },
];

function Sparkline({ values }) {
  if (!values?.length) return null;
  const w = 80;
  const h = 24;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = w / Math.max(1, values.length - 1);
  const points = values
    .map((v, i) => `${i * step},${h - ((v - min) / range) * h}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="sparkline overflow-visible">
      <polyline
        fill="none"
        stroke="hsl(var(--chart-1))"
        strokeWidth="1.5"
        points={points}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TrendIcon({ trend }) {
  if (trend > 0.03) return <ArrowUp className="h-3.5 w-3.5 text-[hsl(var(--success))]" />;
  if (trend < -0.03) return <ArrowDown className="h-3.5 w-3.5 text-[hsl(var(--risk-high))]" />;
  return <Minus className="h-3.5 w-3.5 text-muted-foreground" />;
}

export default function ForecastingPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("confidence_desc");
  const [category, setCategory] = useState("all");
  const [cats, setCats] = useState([]);

  useEffect(() => {
    api.get("/products").then((r) => setCats(r.data.categories || []));
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const params = { sort, category };
    if (q) params.q = q;
    api
      .get("/forecasting", { params })
      .then((r) => active && setData(r.data))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [q, sort, category]);

  return (
    <div data-testid="forecasting-page">
      <PageHeader
        title="Forecasting"
        subtitle="30 / 60 / 90 day demand outlook and confidence per SKU."
      />

      <Card className="mb-4">
        <CardContent className="p-4 flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="h-4 w-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-testid="forecasting-search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search SKUs"
              className="pl-8"
            />
          </div>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-full md:w-[180px]" data-testid="forecasting-category-select">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {cats.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger className="w-full md:w-[220px]" data-testid="forecasting-confidence-sort">
              <SelectValue placeholder="Sort" />
            </SelectTrigger>
            <SelectContent>
              {SORTS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto scroll-fade">
            <table className="w-full text-sm" data-testid="forecasting-table">
              <thead className="bg-muted/40 border-b border-border">
                <tr className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Product</th>
                  <th className="text-right px-4 py-3 font-medium">Stock</th>
                  <th className="text-right px-4 py-3 font-medium">Daily</th>
                  <th className="text-right px-4 py-3 font-medium">30d</th>
                  <th className="text-right px-4 py-3 font-medium">60d</th>
                  <th className="text-right px-4 py-3 font-medium">90d</th>
                  <th className="text-left px-4 py-3 font-medium">Trend</th>
                  <th className="text-left px-4 py-3 font-medium">14d</th>
                  <th className="text-left px-4 py-3 font-medium">Confidence</th>
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
                  : data?.items?.map((i) => (
                      <tr
                        key={i.sku_id}
                        className="border-b border-border hover:bg-muted/40 transition-colors"
                        data-testid={`forecasting-row-${i.sku_id}`}
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
                        <td className="px-4 py-3 text-right tabular-nums">{num1(i.daily_forecast)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{num(i.forecast_30)}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{num(i.forecast_60)}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{num(i.forecast_90)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <TrendIcon trend={i.trend} />
                            <span className="tabular-nums">{(i.trend * 100).toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Sparkline values={i.sparkline} />
                        </td>
                        <td className="px-4 py-3 w-[180px]">
                          <ConfidenceBar value={i.confidence} testid={`forecasting-confidence-${i.sku_id}`} />
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
