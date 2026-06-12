import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

export function Pagination({ page, pageCount, onChange, total, pageSize }) {
  if (!pageCount || pageCount <= 1) {
    return (
      <div className="text-xs text-muted-foreground mt-3">{total ? `${total} items` : ""}</div>
    );
  }
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
      <div>
        Showing <span className="tabular-nums">{from}-{to}</span> of <span className="tabular-nums">{total}</span>
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          data-testid="pagination-prev"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Prev
        </Button>
        <div className="px-2 tabular-nums">
          Page {page} / {pageCount}
        </div>
        <Button
          variant="ghost"
          size="sm"
          disabled={page >= pageCount}
          onClick={() => onChange(page + 1)}
          data-testid="pagination-next"
        >
          Next <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
