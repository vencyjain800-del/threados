import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export function ConfidenceBar({ value, testid, className }) {
  const v = Math.max(0, Math.min(100, Number(value || 0)));
  let color = "hsl(var(--risk-high))";
  if (v >= 75) color = "hsl(var(--success))";
  else if (v >= 60) color = "hsl(var(--info))";
  else if (v >= 50) color = "hsl(var(--warning))";

  return (
    <div className={cn("flex items-center gap-2 min-w-[100px]", className)} data-testid={testid}>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${v}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-medium tabular-nums w-9 text-right">{v}%</span>
    </div>
  );
}
