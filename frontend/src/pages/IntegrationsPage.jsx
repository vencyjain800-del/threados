import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { gbp, num, formatDateShort } from "@/lib/format";
import {
  ShoppingBag,
  Plug,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Power,
  ShieldCheck,
  Database,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

function StatusPill({ status }) {
  if (status === "connected") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full border border-[hsl(var(--success))/0.3] bg-[hsl(var(--success))/0.10] text-[hsl(var(--success))]">
        <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--success))]" />
        Connected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full border border-border bg-muted text-muted-foreground">
      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />
      Not connected
    </span>
  );
}

export default function IntegrationsPage() {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [storeUrl, setStoreUrl] = useState("ateliersable.myshopify.com");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/integrations/shopify");
      setDoc(r.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const connect = async () => {
    setBusy(true);
    try {
      const r = await api.post("/integrations/shopify/connect", { store_url: storeUrl });
      setDoc(r.data);
      toast.success("Shopify connected");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to connect Shopify");
    } finally {
      setBusy(false);
    }
  };

  const sync = async () => {
    setBusy(true);
    try {
      const r = await api.post("/integrations/shopify/sync");
      setDoc(r.data);
      toast.success("Sync complete");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Sync failed");
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    if (!window.confirm("Disconnect Shopify? Demo data will remain intact.")) return;
    setBusy(true);
    try {
      const r = await api.post("/integrations/shopify/disconnect");
      setDoc(r.data);
      toast.success("Shopify disconnected");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Disconnect failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="integrations-page">
      <PageHeader
        title="Integrations"
        subtitle="Connect your storefront so ThreadOS can pull live inventory and sales."
      />

      <Card data-testid="shopify-integration-card">
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="h-10 w-10 rounded-lg bg-[hsl(var(--success))/0.10] grid place-items-center text-[hsl(var(--success))]">
                <ShoppingBag className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <div className="font-display text-lg font-semibold">Shopify</div>
                  {loading ? (
                    <Skeleton className="h-5 w-24" />
                  ) : (
                    <StatusPill status={doc?.status} />
                  )}
                </div>
                <div className="text-sm text-muted-foreground mt-1 max-w-md">
                  Sync products, inventory levels, and sales history. ThreadOS turns it into
                  forecasts, risks, and recommendations.
                </div>
              </div>
            </div>

            <div className="flex flex-col sm:items-end gap-2 text-sm">
              {doc?.status === "connected" && (
                <>
                  <div className="font-mono text-xs text-muted-foreground">{doc.store_url}</div>
                  <div className="text-xs text-muted-foreground">
                    Last sync {doc?.last_sync_at ? formatDateShort(doc.last_sync_at) : "\u2014"}
                  </div>
                </>
              )}
            </div>
          </div>

          {loading ? (
            <div className="mt-6 space-y-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-2/3" />
            </div>
          ) : doc?.status === "connected" ? (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3">
              <DataTile
                icon={Database}
                label="Products synced"
                value={num(doc.data?.products_imported)}
              />
              <DataTile
                icon={Database}
                label="Sales records"
                value={num(doc.data?.sales_records_imported)}
              />
              <DataTile icon={ShieldCheck} label="Mode" value="Demo (sandbox)" />
              <div className="md:col-span-3 flex flex-wrap items-center gap-2 pt-2">
                <Button onClick={sync} disabled={busy} data-testid="shopify-sync-button">
                  <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> Sync now
                </Button>
                <Button
                  variant="secondary"
                  onClick={disconnect}
                  disabled={busy}
                  data-testid="shopify-disconnect-button"
                >
                  <Power className="h-4 w-4" /> Disconnect
                </Button>
              </div>
            </div>
          ) : (
            <div className="mt-6 space-y-3 max-w-lg">
              <Label htmlFor="store-url" className="text-xs text-muted-foreground">
                Shopify store URL
              </Label>
              <Input
                id="store-url"
                value={storeUrl}
                onChange={(e) => setStoreUrl(e.target.value)}
                placeholder="yourbrand.myshopify.com"
                data-testid="shopify-store-input"
              />
              <div className="flex items-center gap-2">
                <Button onClick={connect} disabled={busy} data-testid="shopify-connect-button">
                  <Plug className="h-4 w-4" /> Connect Shopify
                </Button>
                <span className="text-xs text-muted-foreground">
                  Demo flow — no credentials needed.
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Event log */}
      <Card className="mt-6">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="font-display text-base font-semibold">Activity</div>
              <div className="text-xs text-muted-foreground">Latest 30 sync and connection events.</div>
            </div>
          </div>
          {loading ? (
            <Skeleton className="h-32 w-full" />
          ) : (doc?.events || []).length === 0 ? (
            <div className="text-sm text-muted-foreground py-6">
              No activity yet. Connect Shopify to start syncing.
            </div>
          ) : (
            <div className="divide-y divide-border" data-testid="shopify-activity-log">
              {[...(doc.events || [])].reverse().map((e, idx) => {
                const Icon =
                  e.type === "connect"
                    ? CheckCircle2
                    : e.type === "disconnect"
                    ? XCircle
                    : RefreshCw;
                const tone =
                  e.type === "connect"
                    ? "text-[hsl(var(--success))]"
                    : e.type === "disconnect"
                    ? "text-[hsl(var(--risk-high))]"
                    : "text-[hsl(var(--info))]";
                return (
                  <div key={idx} className="flex items-start gap-3 py-3">
                    <Icon className={`h-4 w-4 mt-0.5 ${tone}`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm">{e.message}</div>
                      <div className="text-xs text-muted-foreground">{formatDateShort(e.at)}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Coming soon */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-6">
        {[
          { name: "WooCommerce", desc: "Sync products and orders from Woo." },
          { name: "Centra", desc: "For DTC brands on Centra." },
          { name: "Xero / QuickBooks", desc: "Pull cost prices and PO accounting." },
        ].map((p) => (
          <Card key={p.name} className="opacity-80">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="font-medium">{p.name}</div>
                <span className="text-[10px] uppercase tracking-[0.06em] text-muted-foreground border border-border rounded px-1.5 py-0.5">
                  Soon
                </span>
              </div>
              <div className="text-xs text-muted-foreground mt-1">{p.desc}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function DataTile({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-center justify-between text-xs uppercase tracking-[0.06em] text-muted-foreground">
        <span>{label}</span>
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="font-display text-lg font-semibold mt-1 tabular-nums">{value}</div>
    </div>
  );
}
