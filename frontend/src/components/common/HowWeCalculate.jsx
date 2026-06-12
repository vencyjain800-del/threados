import { useState } from "react";
import { Info } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function HowWeCalculateButton({ className = "" }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className={className}
          data-testid="how-we-calculate-button"
        >
          <Info className="h-4 w-4" /> How we calculate
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl" data-testid="how-we-calculate-modal">
        <DialogHeader>
          <DialogTitle className="font-display">How ThreadOS calculates recommendations</DialogTitle>
          <DialogDescription>
            Designed to be transparent. Every recommendation comes from these signals.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm leading-relaxed">
          <Section title="1. Sales velocity">
            We compute a daily run-rate using an exponential moving average over the last 60 days
            (weighted toward recent days) plus a comparison of the last 30 days against the
            preceding 30 days to capture trend.
          </Section>
          <Section title="2. Forecast demand (30 / 60 / 90)">
            Daily run-rate is projected forward and adjusted by the recent trend. We do not over-fit
            to single spikes — the EMA keeps the line stable.
          </Section>
          <Section title="3. Confidence score">
            Confidence drops as variability rises. Low-volume SKUs are penalised because the signal
            is thin. Treat anything below 60% as “review before committing capital”.
          </Section>
          <Section title="4. Stockout / overstock risk">
            We compare days-of-cover against the supplier lead time. If you can’t cover the lead
            time, you’re at stockout risk. If days-of-cover exceeds 120, it’s overstock territory.
          </Section>
          <Section title="5. Recommended buy">
            We size the order so that, when goods arrive, you have your target days of cover plus a
            safety stock proportional to forecast uncertainty (lower confidence → bigger buffer).
            Reorder date works backwards: place the order before coverage falls below lead time + 7
            day buffer.
          </Section>
          <Section title="Plain English">
            The number we suggest answers one question: “How many units do I need to order today so
            that, after the lead time, I land at my target stock level, without burning cash on
            excess?”
          </Section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div className="font-medium text-foreground">{title}</div>
      <div className="text-muted-foreground mt-1">{children}</div>
    </div>
  );
}
