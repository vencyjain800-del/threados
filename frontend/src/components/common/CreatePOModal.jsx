import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { gbp, num } from "@/lib/format";
import { api } from "@/lib/api";
import { toast } from "sonner";

/**
 * Modal: Create draft PO from a recommendation item.
 * Item should expose: sku_id, name, recommended_qty, cost, supplier_id, supplier_name, reorder_by_date.
 */
export function CreatePOModal({ open, onOpenChange, item, onCreated }) {
  const [qty, setQty] = useState(item?.recommended_qty || 1);
  const [unitCost, setUnitCost] = useState(item?.cost || 0);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);

  if (!item) return null;
  const total = (Number(qty) || 0) * (Number(unitCost) || 0);

  const submit = async () => {
    setLoading(true);
    try {
      const payload = {
        supplier_id: item.supplier_id,
        reorder_by_date: item.reorder_by_date,
        notes,
        lines: [{ sku_id: item.sku_id, qty: Number(qty), unit_cost: Number(unitCost) }],
      };
      const r = await api.post("/purchase-orders", payload);
      toast.success(`Draft ${r.data.number} created`);
      onCreated?.(r.data);
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to create PO");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="create-po-modal">
        <DialogHeader>
          <DialogTitle className="font-display">Create purchase order</DialogTitle>
          <DialogDescription>
            {item.name} · {item.supplier_name || "No supplier assigned"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs text-muted-foreground">Quantity</Label>
              <Input
                type="number"
                min="1"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                data-testid="create-po-qty"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Unit cost (£)</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={unitCost}
                onChange={(e) => setUnitCost(e.target.value)}
                data-testid="create-po-cost"
              />
            </div>
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">Notes</Label>
            <Textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes for the supplier…"
              data-testid="create-po-notes"
            />
          </div>
          <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
            <span className="text-muted-foreground">Total order value</span>
            <span className="font-display text-lg font-semibold tabular-nums">{gbp(total)}</span>
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={loading || qty <= 0} data-testid="create-po-submit">
            {loading ? "Creating…" : "Create draft PO"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
