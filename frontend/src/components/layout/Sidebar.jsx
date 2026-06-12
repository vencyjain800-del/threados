import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Boxes,
  LineChart,
  ShoppingBag,
  ShieldAlert,
  Building2,
  FileText,
  Plug,
} from "lucide-react";
import { cn } from "@/lib/utils";

const OPS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "sidebar-nav-dashboard" },
  { to: "/inventory", label: "Inventory", icon: Boxes, testid: "sidebar-nav-inventory" },
  { to: "/forecasting", label: "Forecasting", icon: LineChart, testid: "sidebar-nav-forecasting" },
  { to: "/recommendations", label: "Recommendations", icon: ShoppingBag, testid: "sidebar-nav-recommendations" },
  { to: "/risks", label: "Risk centre", icon: ShieldAlert, testid: "sidebar-nav-risks" },
];

const BUYING = [
  { to: "/suppliers", label: "Suppliers", icon: Building2, testid: "sidebar-nav-suppliers" },
  { to: "/purchase-orders", label: "Purchase orders", icon: FileText, testid: "sidebar-nav-purchase-orders" },
];

const SETUP = [
  { to: "/integrations", label: "Integrations", icon: Plug, testid: "sidebar-nav-integrations" },
];

function Section({ title, items }) {
  return (
    <div className="space-y-1">
      <div className="px-3 pb-1 pt-3 text-[10px] tracking-[0.12em] uppercase text-muted-foreground/70">{title}</div>
      {items.map(({ to, label, icon: Icon, testid }) => (
        <NavLink
          key={to}
          to={to}
          data-testid={testid}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/70 transition-colors",
              isActive && "bg-muted text-foreground border border-border"
            )
          }
        >
          <Icon className="h-4 w-4" />
          <span>{label}</span>
        </NavLink>
      ))}
    </div>
  );
}

export default function Sidebar() {
  return (
    <aside className="hidden md:flex w-[264px] shrink-0 border-r border-border bg-card flex-col">
      <div className="h-14 flex items-center px-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-md bg-primary text-primary-foreground grid place-items-center font-display font-semibold">
            T
          </div>
          <div className="font-display text-base font-semibold tracking-tight">ThreadOS</div>
        </div>
      </div>
      <nav className="px-3 py-3 space-y-2 flex-1 overflow-y-auto scroll-fade" data-testid="sidebar-nav">
        <Section title="Operations" items={OPS} />
        <Section title="Buying" items={BUYING} />
        <Section title="Setup" items={SETUP} />
      </nav>
      <div className="p-4 border-t border-border">
        <div className="rounded-lg border border-border bg-muted/40 p-3">
          <div className="text-xs font-medium text-foreground">Demo workspace</div>
          <div className="text-xs text-muted-foreground mt-1">
            Realistic data for founder demos and validation.
          </div>
        </div>
      </div>
    </aside>
  );
}
