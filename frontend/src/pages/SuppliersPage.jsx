import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { gbp, num } from "@/lib/format";
import { Building2, Star, ChevronRight, Globe2, Clock } from "lucide-react";

export default function SuppliersPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get("/suppliers").then((r) => setData(r.data)).finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="suppliers-page">
      <PageHeader
        title="Suppliers"
        subtitle="Where every SKU is made — and how much cash sits with each partner."
      />

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="suppliers-grid">
          {data.items.map((s) => (
            <Card key={s.id} className="hover:shadow-sm transition-shadow" data-testid={`supplier-card-${s.id}`}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="h-10 w-10 rounded-lg bg-muted grid place-items-center text-muted-foreground shrink-0">
                      <Building2 className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-display text-base font-semibold truncate">{s.name}</div>
                      <div className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                        <Globe2 className="h-3 w-3" /> {s.city}, {s.country}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Star className="h-3.5 w-3.5 fill-[hsl(var(--warning))] text-[hsl(var(--warning))]" />
                    <span className="tabular-nums">{s.rating}</span>
                  </div>
                </div>

                <div className="text-sm text-foreground/85 mt-3 leading-snug">{s.specialty}</div>

                <div className="grid grid-cols-3 gap-3 mt-4">
                  <Metric label="SKUs" value={num(s.sku_count)} />
                  <Metric label="Inventory @ cost" value={gbp(s.inventory_cost)} />
                  <Metric label="Lead time" value={`${s.lead_time_days}d`} icon={Clock} />
                </div>

                <div className="flex flex-wrap gap-1.5 mt-4">
                  {s.categories.map((c) => (
                    <span
                      key={c}
                      className="text-[11px] px-2 py-0.5 rounded-full border border-border bg-muted text-foreground/85"
                    >
                      {c}
                    </span>
                  ))}
                </div>

                <div className="mt-4 pt-3 border-t border-border text-xs text-muted-foreground flex items-center justify-between">
                  <span>
                    {s.contact_name} · {s.contact_email}
                  </span>
                  <Link
                    to={`/inventory?supplier=${s.id}`}
                    className="inline-flex items-center gap-1 text-foreground hover:underline"
                    data-testid={`supplier-view-skus-${s.id}`}
                  >
                    View SKUs <ChevronRight className="h-3 w-3" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, icon: Icon }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.06em] text-muted-foreground flex items-center gap-1">
        {Icon && <Icon className="h-3 w-3" />}
        {label}
      </div>
      <div className="font-display text-base font-semibold tabular-nums mt-0.5">{value}</div>
    </div>
  );
}
