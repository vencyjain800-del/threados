import { useLocation, useNavigate } from "react-router-dom";
import { Moon, Sun, LogOut, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/context/ThemeContext";
import { useAuth } from "@/context/AuthContext";

const TITLES = {
  "/dashboard": { title: "Dashboard", sub: "Inventory health at a glance" },
  "/inventory": { title: "Inventory", sub: "Every SKU, sorted and filterable" },
  "/forecasting": { title: "Forecasting", sub: "30 / 60 / 90 day demand outlook" },
  "/recommendations": { title: "Buy recommendations", sub: "What to order and when" },
  "/risks": { title: "Risk centre", sub: "Stockout and overstock signals" },
};

export default function Topbar() {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const loc = useLocation();
  const navigate = useNavigate();
  const meta =
    TITLES[loc.pathname] ||
    (loc.pathname.startsWith("/products/") ? { title: "Product detail", sub: "SKU performance + forecast" } : { title: "", sub: "" });

  const initials = (user?.name || "AC")
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("");

  return (
    <header className="sticky top-0 z-30 h-14 border-b border-border bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/65">
      <div className="h-full px-4 sm:px-6 lg:px-8 max-w-[1280px] mx-auto flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold truncate font-display">{meta.title}</div>
          <div className="text-xs text-muted-foreground truncate">{meta.sub}</div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            data-testid="topbar-theme-toggle"
            onClick={toggle}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-9 px-2 gap-2" data-testid="topbar-user-menu">
                <div className="h-7 w-7 rounded-full bg-secondary text-secondary-foreground grid place-items-center text-xs font-semibold">
                  {initials}
                </div>
                <div className="hidden sm:flex flex-col items-start leading-tight">
                  <span className="text-xs font-medium">{user?.name}</span>
                  <span className="text-[10px] text-muted-foreground">{user?.brand}</span>
                </div>
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="text-xs text-muted-foreground">
                {user?.email}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={logout}
                data-testid="topbar-logout-button"
                className="text-sm gap-2"
              >
                <LogOut className="h-4 w-4" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
