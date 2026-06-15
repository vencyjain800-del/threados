"use client";

export type RiskTier = "dead" | "stockout" | "reorder" | "overstock" | "healthy";

export function tierLabel(tier: string): string {
  const labels: Record<string, string> = {
    dead: "Dead Stock",
    stockout: "Stockout",
    reorder: "Reorder",
    overstock: "Overstock",
    healthy: "Healthy",
  };
  return labels[tier] ?? tier;
}

export function tierClasses(tier: string): string {
  const map: Record<string, string> = {
    dead: "bg-gray-100 text-gray-700 border-gray-200",
    stockout: "bg-red-100 text-red-700 border-red-200",
    reorder: "bg-amber-100 text-amber-700 border-amber-200",
    overstock: "bg-blue-100 text-blue-700 border-blue-200",
    healthy: "bg-green-100 text-green-700 border-green-200",
  };
  return map[tier] ?? "bg-gray-100 text-gray-600 border-gray-200";
}

export function tierCardClasses(tier: string): {
  bg: string;
  border: string;
  label: string;
  count: string;
} {
  const map: Record<
    string,
    { bg: string; border: string; label: string; count: string }
  > = {
    stockout: {
      bg: "bg-red-50",
      border: "border-red-200",
      label: "text-red-700",
      count: "text-red-600",
    },
    reorder: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      label: "text-amber-700",
      count: "text-amber-600",
    },
    overstock: {
      bg: "bg-blue-50",
      border: "border-blue-200",
      label: "text-blue-700",
      count: "text-blue-600",
    },
    dead: {
      bg: "bg-gray-50",
      border: "border-gray-200",
      label: "text-gray-700",
      count: "text-gray-600",
    },
  };
  return (
    map[tier] ?? {
      bg: "bg-gray-50",
      border: "border-gray-200",
      label: "text-gray-700",
      count: "text-gray-600",
    }
  );
}

interface RiskBadgeProps {
  tier: string;
  size?: "sm" | "md";
}

export function RiskBadge({ tier, size = "sm" }: RiskBadgeProps) {
  const sizeClass = size === "md" ? "px-3 py-1 text-sm" : "px-2.5 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${sizeClass} ${tierClasses(tier)}`}
    >
      {tierLabel(tier)}
    </span>
  );
}
