import { cn } from "@/lib/utils";

const CONFIG = {
  high_stockout: { label: "High stockout risk", color: "risk-high" },
  medium_stockout: { label: "Medium stockout risk", color: "risk-med" },
  healthy: { label: "Healthy", color: "risk-healthy" },
  medium_overstock: { label: "Medium overstock risk", color: "warning" },
  high_overstock: { label: "High overstock risk", color: "warning" },
};

export function RiskBadge({ bucket, label, className }) {
  const cfg = CONFIG[bucket] || { label: label || bucket, color: "muted" };
  return (
    <span
      data-testid={`risk-badge-${bucket}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        className
      )}
      style={{
        backgroundColor: `hsl(var(--${cfg.color}) / 0.10)`,
        color: `hsl(var(--${cfg.color}))`,
        borderColor: `hsl(var(--${cfg.color}) / 0.25)`,
      }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: `hsl(var(--${cfg.color}))` }}
      />
      {label || cfg.label}
    </span>
  );
}
