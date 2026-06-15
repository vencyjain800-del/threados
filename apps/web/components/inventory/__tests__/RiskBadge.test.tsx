import { render, screen } from "@testing-library/react";
import { RiskBadge, tierLabel, tierClasses } from "../RiskBadge";

describe("tierLabel", () => {
  it("returns human-readable label for known tiers", () => {
    expect(tierLabel("dead")).toBe("Dead Stock");
    expect(tierLabel("stockout")).toBe("Stockout");
    expect(tierLabel("reorder")).toBe("Reorder");
    expect(tierLabel("overstock")).toBe("Overstock");
    expect(tierLabel("healthy")).toBe("Healthy");
  });

  it("returns the raw value for unknown tiers", () => {
    expect(tierLabel("unknown-tier")).toBe("unknown-tier");
  });
});

describe("tierClasses", () => {
  it("returns tailwind classes for each known tier", () => {
    expect(tierClasses("stockout")).toContain("text-red-700");
    expect(tierClasses("reorder")).toContain("text-amber-700");
    expect(tierClasses("healthy")).toContain("text-green-700");
  });

  it("falls back to gray classes for unknown tier", () => {
    expect(tierClasses("unknown")).toContain("text-gray-600");
  });
});

describe("RiskBadge", () => {
  it("renders the tier label as visible text", () => {
    render(<RiskBadge tier="healthy" />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders stockout label", () => {
    render(<RiskBadge tier="stockout" />);
    expect(screen.getByText("Stockout")).toBeInTheDocument();
  });

  it("applies sm size classes by default", () => {
    render(<RiskBadge tier="reorder" />);
    const badge = screen.getByText("Reorder");
    expect(badge.className).toContain("text-xs");
  });

  it("applies md size classes when size=md", () => {
    render(<RiskBadge tier="reorder" size="md" />);
    const badge = screen.getByText("Reorder");
    expect(badge.className).toContain("text-sm");
  });

  it("renders unknown tier with its raw value", () => {
    render(<RiskBadge tier="custom-tier" />);
    expect(screen.getByText("custom-tier")).toBeInTheDocument();
  });
});
