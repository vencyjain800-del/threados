import { Link } from "react-router-dom";
import { TrendingUp, Boxes, Sparkles, ShieldAlert, ShoppingBag, ArrowRight, Calculator } from "lucide-react";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { RiskBadge } from "@/components/common/RiskBadge";
import { gbp, num, formatDateShort, daysFromNow } from "@/lib/format";
import { Button } from "@/components/ui/button";

const ICONS = {
  velocity: TrendingUp,
  stock: Boxes,
  forecast: Sparkles,
  confidence: ShieldAlert,
  risk: ShieldAlert,
};

/** Reusable, accessible "Why this recommendation?" panel.
 * Accepts a recommendation row from /api/recommendations OR the explanation+meta from /api/products/{id}.
 */
export function WhyRecommendationPanel({ item, onCreatePO, onOpenSku }) {
  if (!item) return null;
  const ex = item.explanation;
  if (!ex) return null;
  const daysOut = daysFromNow(item.reorder_by_date);
  return (
    <div className="space-y-4" data-testid="why-recommendation-panel">
      <div className="rounded-lg border border-border bg-muted/40 p-4">
        <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground">Recommendation</div>
        <div className="font-display text-xl font-semibold mt-1 leading-tight">{ex.headline}</div>
        {item.recommended_qty > 0 && item.reorder_by_date && (
          <div className="text-sm text-muted-foreground mt-1">
            By {formatDateShort(item.reorder_by_date)}
            {daysOut <= 14 && (
              <span className="ml-2 text-xs text-[hsl(var(--warning))]">
                ({daysOut <= 0 ? "order now" : `in ${daysOut}d`})
              </span>
            )}
          </div>
        )}
        <div className="flex flex-wrap gap-2 mt-3">
          {item.bucket && <RiskBadge bucket={item.bucket} label={item.risk_label} />}
          {item.supplier_name && (
            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border border-border bg-card text-foreground/85">
              {item.supplier_name}
            </span>
          )}
          {item.recommended_qty > 0 && (
            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border border-border bg-card text-foreground/85">
              {num(item.recommended_qty)} units · {gbp(item.order_cost ?? item.recommended_qty * (item.cost || 0))}
            </span>
          )}
        </div>
      </div>

      <div>
        <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground mb-2">Why this recommendation?</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {ex.drivers.map((d) => {
            const Icon = ICONS[d.key] || Sparkles;
            return (
              <div
                key={d.key}
                className="rounded-lg border border-border bg-card p-3"
                data-testid={`why-driver-${d.key}`}
              >
                <div className="flex items-center justify-between">
                  <div className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground">{d.label}</div>
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <div className="font-display text-base font-semibold mt-1 tabular-nums">{d.value}</div>
                <div className="text-xs text-muted-foreground mt-1 leading-snug">{d.detail}</div>
                {d.key === "confidence" && (
                  <div className="mt-2">
                    <ConfidenceBar value={item.confidence} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground mb-2 flex items-center gap-1.5">
          <Calculator className="h-3.5 w-3.5" /> Behind the maths
        </div>
        <ul className="space-y-1.5 text-sm text-foreground/85 rounded-lg border border-border bg-card p-3">
          {ex.math.map((m, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-muted-foreground select-none">•</span>
              <span>{m}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-center gap-2 pt-1">
        {item.recommended_qty > 0 && onCreatePO && (
          <Button onClick={() => onCreatePO(item)} data-testid="why-create-po-button">
            <ShoppingBag className="h-4 w-4" /> Create purchase order
          </Button>
        )}
        {onOpenSku && (
          <Button variant="secondary" asChild>
            <Link to={`/products/${item.sku_id}`} onClick={onOpenSku}>
              Open SKU <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        )}
      </div>
    </div>
  );
}
