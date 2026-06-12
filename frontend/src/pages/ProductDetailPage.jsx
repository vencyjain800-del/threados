import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ChevronLeft, Calendar, TrendingUp, ShoppingBag, ShieldAlert, Boxes } from "lucide-react";
import { api } from "@/lib/api";
import { gbp, num, num1, formatDay, formatDateShort, daysFromNow } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/common/RiskBadge";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

function Tip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      <div className="font-medium">{formatDay(label)}</div>
      <div className="text-muted-foreground mt-1">{num(p.units)} units sold</div>
    </div>
  );
}

export default function ProductDetailPage() {
  const { skuId } = useParams();
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.get(`/products/${skuId}`).then((r) => active && setD(r.data)).finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [skuId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }
  if (!d) return <div className="text-sm text-muted-foreground">SKU not found.</div>;

  const { sku, forecast, recommendation, risk, units_30d, revenue_30d, sales_history } = d;
  const reorderIn = daysFromNow(recommendation.reorder_by_date);

  return (
    <div data-testid="product-detail-page">
      <Link
        to="/inventory"
        className="inline-flex items-center text-xs text-muted-foreground hover:text-foreground mb-4"
      >
        <ChevronLeft className="h-3 w-3 mr-1" /> Back to inventory
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
            {sku.id} <span>·</span> {sku.category} <span>·</span> {sku.size}
          </div>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold mt-1">{sku.name}</h1>
          <div className="text-sm text-muted-foreground mt-1">
            {gbp(sku.price)} retail · {gbp(sku.cost)} cost · {sku.lead_time_days}d lead time
          </div>
        </div>
        <div>
          <RiskBadge bucket={risk.bucket} />
        </div>
      </div>

      {/* Top metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <MetricBox label="Current stock" value={num(sku.current_stock)} hint="units" testid="sku-current-stock" icon={Boxes} />
        <MetricBox label="30d units sold" value={num(units_30d)} hint={gbp(revenue_30d)} icon={TrendingUp} />
        <MetricBox label="Days of stock" value={`${num1(risk.days_of_stock)}d`} hint={`vs ${sku.lead_time_days}d lead`} icon={Calendar} />
        <MetricBox label="Confidence" value={`${forecast.confidence}%`} hint="on 90d forecast" icon={ShieldAlert} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="font-display text-base">Sales history · 90 days</CardTitle>
            <div className="text-xs text-muted-foreground">Daily units sold with trend</div>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]" data-testid="sku-sales-history-chart">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={sales_history} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDay}
                    fontSize={11}
                    stroke="hsl(var(--muted-foreground))"
                    tickLine={false}
                    axisLine={false}
                    minTickGap={32}
                  />
                  <YAxis fontSize={11} stroke="hsl(var(--muted-foreground))" tickLine={false} axisLine={false} width={32} />
                  <Tooltip content={<Tip />} cursor={{ fill: "hsl(var(--muted))", fillOpacity: 0.4 }} />
                  <Bar dataKey="units" fill="hsl(var(--chart-1))" fillOpacity={0.35} radius={[2, 2, 0, 0]} />
                  <Line
                    type="monotone"
                    dataKey="units"
                    stroke="hsl(var(--chart-1))"
                    strokeWidth={2}
                    dot={false}
                  />
                  <ReferenceLine
                    y={forecast.daily_forecast}
                    stroke="hsl(var(--success))"
                    strokeDasharray="4 4"
                    label={{ value: `forecast ${num1(forecast.daily_forecast)}/d`, fill: "hsl(var(--muted-foreground))", fontSize: 11, position: "right" }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-base">Forecast</CardTitle>
              <div className="text-xs text-muted-foreground">Demand projection (units)</div>
            </CardHeader>
            <CardContent className="space-y-3">
              <ForecastRow label="Next 30 days" value={forecast.forecast_30} testid="sku-forecast-30-card" />
              <ForecastRow label="Next 60 days" value={forecast.forecast_60} testid="sku-forecast-60-card" />
              <ForecastRow label="Next 90 days" value={forecast.forecast_90} testid="sku-forecast-90-card" />
              <div className="pt-2 border-t border-border">
                <div className="text-xs text-muted-foreground mb-1.5">Confidence</div>
                <ConfidenceBar value={forecast.confidence} testid="forecast-confidence-progress" />
                <div className="text-[11px] text-muted-foreground mt-2">
                  Method: exponential moving average + 30/30 trend.
                </div>
              </div>
            </CardContent>
          </Card>

          <Card data-testid="sku-buy-recommendation">
            <CardHeader className="pb-2">
              <CardTitle className="font-display text-base flex items-center gap-2">
                <ShoppingBag className="h-4 w-4" /> Buy recommendation
              </CardTitle>
            </CardHeader>
            <CardContent>
              {recommendation.recommended_qty > 0 ? (
                <>
                  <div className="font-display text-3xl font-semibold">
                    {num(recommendation.recommended_qty)} <span className="text-sm font-normal text-muted-foreground">units</span>
                  </div>
                  <div className="text-sm mt-1">
                    Reorder by <span className="font-medium">{formatDateShort(recommendation.reorder_by_date)}</span>
                    {reorderIn <= 14 && (
                      <span className="ml-2 text-xs text-[hsl(var(--warning))]">({reorderIn <= 0 ? "now" : `in ${reorderIn}d`})</span>
                    )}
                  </div>
                  <ul className="mt-4 space-y-1.5 text-xs text-muted-foreground">
                    <li>• Target cover: {sku.target_coverage_days} days post-arrival</li>
                    <li>• Lead time: {sku.lead_time_days} days</li>
                    <li>• Safety stock: {num(recommendation.safety_stock)} units</li>
                    <li>• Stock at arrival (forecast): {num(recommendation.stock_at_arrival)} units</li>
                  </ul>
                </>
              ) : (
                <div className="text-sm text-muted-foreground">
                  No buy needed right now. Coverage is comfortable.
                </div>
              )}
            </CardContent>
          </Card>

          <Card data-testid="sku-risk-explanation">
            <CardHeader className="pb-2">
              <CardTitle className="font-display text-base">Risk explanation</CardTitle>
            </CardHeader>
            <CardContent>
              <RiskBadge bucket={risk.bucket} className="mb-2" />
              <p className="text-sm text-foreground/85">{risk.reason}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value, hint, icon: Icon, testid }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4" data-testid={testid}>
      <div className="flex items-center justify-between text-xs uppercase tracking-[0.06em] text-muted-foreground">
        <span>{label}</span>
        {Icon && <Icon className="h-3.5 w-3.5" />}
      </div>
      <div className="font-display text-xl font-semibold mt-1.5 tabular-nums">{value}</div>
      {hint && <div className="text-xs text-muted-foreground mt-0.5">{hint}</div>}
    </div>
  );
}

function ForecastRow({ label, value, testid }) {
  return (
    <div className="flex items-center justify-between" data-testid={testid}>
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-display text-xl font-semibold tabular-nums">{num(value)}</span>
    </div>
  );
}
