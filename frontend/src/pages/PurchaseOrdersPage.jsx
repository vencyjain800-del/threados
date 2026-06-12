import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { gbp, num, formatDateShort } from "@/lib/format";
import {
  FileText,
  Send,
  PackageCheck,
  Ban,
  Trash2,
  Building2,
  CalendarClock,
} from "lucide-react";
import { toast } from "sonner";

const STATUS_LABEL = {
  draft: "Draft",
  sent: "Sent",
  received: "Received",
  cancelled: "Cancelled",
};

const STATUS_TONE = {
  draft: "text-muted-foreground border-border bg-muted/40",
  sent: "text-[hsl(var(--info))] border-[hsl(var(--info))/0.3] bg-[hsl(var(--info))/0.10]",
  received: "text-[hsl(var(--success))] border-[hsl(var(--success))/0.3] bg-[hsl(var(--success))/0.10]",
  cancelled: "text-[hsl(var(--risk-high))] border-[hsl(var(--risk-high))/0.3] bg-[hsl(var(--risk-high))/0.10]",
};

function StatusBadge({ status }) {
  return (
    <span
      data-testid={`po-status-${status}`}
      className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${STATUS_TONE[status] || ""}`}
    >
      {STATUS_LABEL[status] || status}
    </span>
  );
}

export default function PurchaseOrdersPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("all");
  const [open, setOpen] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/purchase-orders", { params: { status } });
      setData(r.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const updateStatus = async (po, next) => {
    try {
      const r = await api.patch(`/purchase-orders/${po.id}/status`, { status: next });
      toast.success(`${po.number} marked ${STATUS_LABEL[next]}`);
      setOpen(r.data);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to update status");
    }
  };

  const remove = async (po) => {
    if (!window.confirm(`Delete ${po.number}?`)) return;
    try {
      await api.delete(`/purchase-orders/${po.id}`);
      toast.success(`${po.number} deleted`);
      setOpen(null);
      load();
    } catch (e) {
      toast.error("Failed to delete");
    }
  };

  const counts = data?.counts || {};
  const all = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div data-testid="purchase-orders-page">
      <PageHeader
        title="Purchase orders"
        subtitle="Draft, send, and receive POs based on your buy recommendations."
      />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4" data-testid="po-summary-row">
        <SummaryTile label="Total POs" value={all} />
        <SummaryTile label="Drafts" value={counts.draft || 0} />
        <SummaryTile label="Sent" value={counts.sent || 0} />
        <SummaryTile
          label="Open value"
          value={loading ? "\u2014" : gbp(data?.total_open_cost || 0)}
        />
      </div>

      <Card className="mb-4">
        <CardContent className="p-4 flex flex-col md:flex-row gap-3 md:items-center">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-full md:w-[200px]" data-testid="po-status-filter">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="sent">Sent</SelectItem>
              <SelectItem value="received">Received</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
          <div className="text-xs text-muted-foreground">
            Create a draft from the <span className="font-medium text-foreground">Recommendations</span> page.
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto scroll-fade">
            <table className="w-full text-sm" data-testid="po-table">
              <thead className="bg-muted/40 border-b border-border">
                <tr className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
                  <th className="text-left px-4 py-3 font-medium">PO #</th>
                  <th className="text-left px-4 py-3 font-medium">Supplier</th>
                  <th className="text-left px-4 py-3 font-medium">Items</th>
                  <th className="text-right px-4 py-3 font-medium">Units</th>
                  <th className="text-right px-4 py-3 font-medium">Total</th>
                  <th className="text-left px-4 py-3 font-medium">Reorder by</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        <td colSpan={8} className="px-4 py-3">
                          <Skeleton className="h-5 w-full" />
                        </td>
                      </tr>
                    ))
                  : (data?.items || []).length === 0
                  ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-sm text-muted-foreground" data-testid="po-empty-state">
                        No purchase orders yet. Head to <span className="font-medium text-foreground">Recommendations</span> to create your first draft.
                      </td>
                    </tr>
                  )
                  : data.items.map((po) => (
                      <tr
                        key={po.id}
                        className="border-b border-border hover:bg-muted/40 transition-colors cursor-pointer"
                        data-testid={`po-row-${po.number}`}
                        onClick={() => setOpen(po)}
                      >
                        <td className="px-4 py-3 font-mono text-xs">{po.number}</td>
                        <td className="px-4 py-3">
                          <div className="font-medium">{po.supplier?.name || "\u2014"}</div>
                          <div className="text-xs text-muted-foreground">
                            {po.supplier?.city ? `${po.supplier.city}, ${po.supplier.country}` : ""}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-sm">{po.lines.length} SKU{po.lines.length === 1 ? "" : "s"}</div>
                          <div className="text-xs text-muted-foreground truncate max-w-[280px]">
                            {po.lines.map((l) => l.name).slice(0, 2).join(", ")}
                            {po.lines.length > 2 ? "\u2026" : ""}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">{num(po.total_units)}</td>
                        <td className="px-4 py-3 text-right tabular-nums font-medium">{gbp(po.total_cost)}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          {po.reorder_by_date ? formatDateShort(po.reorder_by_date) : "\u2014"}
                        </td>
                        <td className="px-4 py-3"><StatusBadge status={po.status} /></td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{formatDateShort(po.created_at)}</td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Sheet open={!!open} onOpenChange={(v) => !v && setOpen(null)}>
        <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto" data-testid="po-detail-drawer">
          {open && (
            <>
              <SheetHeader>
                <SheetTitle className="font-display flex items-center gap-2">
                  <FileText className="h-4 w-4" /> {open.number}
                </SheetTitle>
              </SheetHeader>
              <div className="mt-4 space-y-4 text-sm">
                <div className="flex items-center justify-between">
                  <StatusBadge status={open.status} />
                  <div className="text-xs text-muted-foreground">
                    Created {formatDateShort(open.created_at)}
                  </div>
                </div>

                {open.supplier && (
                  <div className="rounded-lg border border-border bg-muted/40 p-3">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Building2 className="h-4 w-4" /> {open.supplier.name}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {open.supplier.city}, {open.supplier.country} · {open.supplier.lead_time_days}d lead
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {open.supplier.contact_name} · {open.supplier.contact_email}
                    </div>
                  </div>
                )}

                {open.reorder_by_date && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <CalendarClock className="h-3.5 w-3.5" /> Reorder by {formatDateShort(open.reorder_by_date)}
                  </div>
                )}

                {open.notes && (
                  <div>
                    <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground mb-1">Notes</div>
                    <div className="text-foreground/85">{open.notes}</div>
                  </div>
                )}

                <div>
                  <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground mb-1">Lines</div>
                  <div className="rounded-lg border border-border divide-y divide-border">
                    {open.lines.map((l) => (
                      <div key={l.sku_id} className="flex items-center justify-between px-3 py-2">
                        <div className="min-w-0">
                          <div className="text-sm font-medium truncate">{l.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {l.sku_id} · {l.category}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-medium tabular-nums">
                            {num(l.qty)} × {gbp(l.unit_cost)}
                          </div>
                          <div className="text-xs text-muted-foreground tabular-nums">
                            {gbp(l.line_cost)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2">
                  <span className="text-muted-foreground text-sm">Total</span>
                  <span className="font-display text-xl font-semibold tabular-nums">
                    {gbp(open.total_cost)}
                  </span>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  {open.status === "draft" && (
                    <Button onClick={() => updateStatus(open, "sent")} data-testid="po-mark-sent">
                      <Send className="h-4 w-4" /> Mark sent
                    </Button>
                  )}
                  {open.status === "sent" && (
                    <Button onClick={() => updateStatus(open, "received")} data-testid="po-mark-received">
                      <PackageCheck className="h-4 w-4" /> Mark received
                    </Button>
                  )}
                  {["draft", "sent"].includes(open.status) && (
                    <Button
                      variant="secondary"
                      onClick={() => updateStatus(open, "cancelled")}
                      data-testid="po-cancel"
                    >
                      <Ban className="h-4 w-4" /> Cancel
                    </Button>
                  )}
                  {open.status !== "received" && (
                    <Button
                      variant="ghost"
                      onClick={() => remove(open)}
                      className="text-[hsl(var(--risk-high))] hover:text-[hsl(var(--risk-high))]"
                      data-testid="po-delete"
                    >
                      <Trash2 className="h-4 w-4" /> Delete
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function SummaryTile({ label, value }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs uppercase tracking-[0.06em] text-muted-foreground">{label}</div>
        <div className="font-display text-2xl font-semibold tabular-nums mt-1.5">{value}</div>
      </CardContent>
    </Card>
  );
}
