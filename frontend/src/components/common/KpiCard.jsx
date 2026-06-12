import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function KpiCard({ label, value, hint, icon: Icon, tone = "default", loading, testid }) {
  const toneStyles = {
    default: "text-foreground",
    success: "text-[hsl(var(--success))]",
    warning: "text-[hsl(var(--warning))]",
    danger: "text-[hsl(var(--risk-high))]",
  };
  return (
    <Card className="border-border" data-testid={testid}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-[0.08em] text-muted-foreground font-medium">
              {label}
            </div>
            {loading ? (
              <Skeleton className="h-8 w-32 mt-2" />
            ) : (
              <div className={cn("font-display text-2xl sm:text-3xl font-semibold mt-2 tabular-nums", toneStyles[tone])}>
                {value}
              </div>
            )}
            {hint && !loading && (
              <div className="text-xs text-muted-foreground mt-1">{hint}</div>
            )}
          </div>
          {Icon && (
            <div className="h-9 w-9 rounded-md bg-muted/70 grid place-items-center text-muted-foreground">
              <Icon className="h-4 w-4" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
