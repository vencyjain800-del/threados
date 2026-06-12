import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { gbp, num, num1, formatDay } from "@/lib/format";
import { PageHeader } from "@/components/common/PageHeader";
import { KpiCard } from "@/components/common/KpiCard";
import { RiskBadge } from "@/components/common/RiskBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Boxes, PoundSterling, CalendarClock, AlertTriangle, TrendingUp, ArrowRight } from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-card p-2.5 shadow-sm text-xs">
      <div className="font-medium">{formatDay(label)}</div>
      <div className="text-muted-foreground mt-1">
        {num(p.units)} units · {gbp(p.revenue)}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api
      .get("/dashboard/summary")
      .then((r) => active && setData(r.data))
      .catch((e) => active && setError(e?.response?.data?.detail || "Failed to load dashboard"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const kpis = data?.kpis;

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        title={data?.brand ? `${data.brand} • Operations` : "Operations"}
        subtitle="Inventory health, demand outlook, and signals — today."
      />

      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        data-testid="dashboard-kpi-row"
      >
        <KpiCard
          label="Inventory value"
          value={loading ? "—" : gbp(kpis.inventory_value_retail)}
          hint={loading ? "" : `${num(kpis.sku_count)} SKUs · cost ${gbp(kpis.inventory_value_cost)}`}
          icon={PoundSterling}
          loading={loading}
          testid="kpi-inventory-value"
        />
        <KpiCard
          label="Total units"
          value={loading ? "—" : num(kpis.total_units)}
          hint={loading ? "" : `Last 30d sold: ${num(kpis.units_30d)}`}
          icon={Boxes}
          loading={loading}
          testid="kpi-total-units"
        />
        <KpiCard
          label="Days of stock"
          value={loading ? "—" : `${num1(kpis.days_of_stock)} days`}
          hint="Weighted by demand"
          icon={CalendarClock}
          loading={loading}
          testid="kpi-days-of-stock"
        />
        <KpiCard
          label="Low stock alerts"
          value={loading ? "—" : num(kpis.low_stock_count)}
          hint="Action required"
          icon={AlertTriangle}
          tone={kpis?.low_stock_count > 0 ? "warning" : "default"}
          loading={loading}
          testid="kpi-low-stock-alert-count"
        />
      </div>

      {/* Recent sales */}
      <Card className="mt-6" data-testid="dashboard-recent-sales-section">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="font-display text-base font-semibold">Recent sales · 30 days</CardTitle>
            <div className="text-xs text-muted-foreground mt-0.5">
              {loading ? "—" : `${gbp(kpis.revenue_30d)} revenue · ${num(kpis.units_30d)} units`}
            </div>
          </div>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <div className="h-[220px]" data-testid="dashboard-recent-sales-chart">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.recent_sales} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDay}
                    fontSize={11}
                    stroke="hsl(var(--muted-foreground))"
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    fontSize={11}
                    stroke="hsl(var(--muted-foreground))"
                    tickLine={false}
                    axisLine={false}
                    width={32}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: "hsl(var(--border))" }} />
                  <Area
                    type="monotone"
                    dataKey="units"
                    stroke="hsl(var(--chart-1))"
                    strokeWidth={2}
                    fill="url(#salesFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <Card data-testid="dashboard-best-sellers-section">
          <CardHeader className="pb-2">
            <CardTitle className="font-display text-base font-semibold">Best sellers · 30 days</CardTitle>
            <div className="text-xs text-muted-foreground">By revenue</div>
          </CardHeader>
          <CardContent>
            <SmallList items={data?.best_sellers} loading={loading} mode="best" />
          </CardContent>
        </Card>

        <Card data-testid="dashboard-slow-movers-section">
          <CardHeader className="pb-2">
            <CardTitle className="font-display text-base font-semibold">Slow movers · 30 days</CardTitle>
            <div className="text-xs text-muted-foreground">By units sold</div>
          </CardHeader>
          <CardContent>
            <SmallList items={data?.slow_movers} loading={loading} mode="slow" />
          </CardContent>
        </Card>
      </div>

      {/* Low stock alerts */}
      <Card className="mt-6" data-testid="dashboard-low-stock-alerts-section">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="font-display text-base font-semibold">Low stock alerts</CardTitle>
            <div className="text-xs text-muted-foreground">SKUs at risk of stockout</div>
          </div>
          <Link
            to="/risks"
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </CardHeader>
        <CardContent className="pt-0">
          {loading ? (
            <Skeleton className="h-32 w-full" />
          ) : data.low_stock_alerts.length === 0 ? (
            <div className="text-sm text-muted-foreground py-6">All SKUs comfortably stocked.</div>
          ) : (
            <div className="divide-y divide-border">
              {data.low_stock_alerts.map((a) => (
                <Link
                  key={a.sku_id}
                  to={`/products/${a.sku_id}`}
                  className="flex items-center justify-between py-3 hover:bg-muted/40 -mx-2 px-2 rounded-md transition-colors"
                  data-testid={`low-stock-row-${a.sku_id}`}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{a.name}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {a.sku_id} · {a.category}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <div className="text-sm font-medium tabular-nums">{num(a.current_stock)} units</div>
                      <div className="text-xs text-muted-foreground tabular-nums">{num1(a.days_of_stock)}d cover</div>
                    </div>
                    <RiskBadge bucket={a.bucket} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {error && (
        <div
          data-testid="global-error-alert"
          className="mt-6 text-sm text-[hsl(var(--risk-high))] bg-[hsl(var(--risk-high)/0.08)] border border-[hsl(var(--risk-high)/0.25)] rounded-md px-3 py-2"
        >
          {error}
        </div>
      )}
    </div>
  );
}

function SmallList({ items, loading, mode }) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }
  if (!items?.length) {
    return <div className="text-sm text-muted-foreground py-6">No data yet.</div>;
  }
  return (
    <div className="divide-y divide-border">
      {items.map((i) => (
        <Link
          key={i.sku_id}
          to={`/products/${i.sku_id}`}
          className="flex items-center justify-between py-2.5 -mx-2 px-2 rounded-md hover:bg-muted/40 transition-colors"
          data-testid={`${mode}-row-${i.sku_id}`}
        >
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">{i.name}</div>
            <div className="text-xs text-muted-foreground truncate">
              {i.sku_id} · {i.category}
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm font-medium tabular-nums">
              {mode === "best" ? gbp(i.revenue_30d) : `${num(i.units_30d)}u`}
            </div>
            <div className="text-xs text-muted-foreground tabular-nums">
              {num(i.current_stock)} in stock
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
