import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { ShieldCheck, ArrowRight, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("demo@threados.com");
  const [password, setPassword] = useState("demo1234");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr("");
  }, [email, password]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      toast.success("Welcome back");
      navigate("/dashboard", { replace: true });
    } catch (e) {
      const msg = e?.response?.data?.detail || "Sign in failed. Check your credentials.";
      setErr(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = () => {
    setEmail("demo@threados.com");
    setPassword("demo1234");
  };

  return (
    <div className="min-h-screen w-full bg-background grid grid-cols-1 lg:grid-cols-[1.05fr_1fr]">
      {/* Left brand panel */}
      <div className="relative hidden lg:flex flex-col justify-between p-10 border-r border-border bg-card overflow-hidden">
        <div className="absolute inset-0 texture-noise opacity-50" />
        <div className="relative z-10 flex items-center gap-2">
          <div className="h-9 w-9 rounded-md bg-primary text-primary-foreground grid place-items-center font-display font-semibold">
            T
          </div>
          <div className="font-display text-lg font-semibold">ThreadOS</div>
        </div>

        <div className="relative z-10 max-w-md">
          <div className="inline-flex items-center gap-2 text-xs px-2.5 py-1 rounded-full border border-border bg-muted text-muted-foreground mb-5">
            <Sparkles className="h-3.5 w-3.5" /> Inventory Decision Intelligence
          </div>
          <h2 className="font-display text-3xl sm:text-4xl font-semibold leading-tight tracking-tight">
            Inventory decisions you can defend.
          </h2>
          <p className="text-sm text-muted-foreground mt-3 leading-relaxed">
            Forecast demand, spot risks, and order with confidence — built for founder-led fashion brands.
          </p>
          <ul className="mt-8 space-y-3 text-sm">
            {[
              "Reduce stockouts with per-SKU forecasts",
              "Avoid overbuying with risk-aware recommendations",
              "Protect cash flow with clear order quantities and dates",
            ].map((line) => (
              <li key={line} className="flex items-start gap-2 text-foreground/85">
                <ShieldCheck className="h-4 w-4 mt-0.5 text-[hsl(var(--success))]" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative z-10 text-xs text-muted-foreground">
          Trusted by founders running £250k–£10m fashion brands.
        </div>
      </div>

      {/* Right login card */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <Card className="w-full max-w-md border-border shadow-sm">
          <CardContent className="p-8">
            <div className="mb-6">
              <div className="font-display text-xl font-semibold">Sign in</div>
              <div className="text-sm text-muted-foreground mt-1">
                Use your demo workspace credentials.
              </div>
            </div>

            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs font-medium text-muted-foreground">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  data-testid="login-email-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@brand.com"
                  autoComplete="email"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs font-medium text-muted-foreground">
                  Password
                </Label>
                <Input
                  id="password"
                  type="password"
                  data-testid="login-password-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
              </div>

              {err && (
                <div
                  data-testid="login-error"
                  className="text-sm text-[hsl(var(--risk-high))] bg-[hsl(var(--risk-high)/0.08)] border border-[hsl(var(--risk-high)/0.25)] rounded-md px-3 py-2"
                >
                  {err}
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                disabled={loading}
                data-testid="login-submit-button"
              >
                {loading ? "Signing in…" : (
                  <>
                    Sign in <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>

            <div
              data-testid="login-demo-credentials-hint"
              className="mt-6 rounded-md border border-dashed border-border bg-muted/40 p-3 text-xs text-muted-foreground"
            >
              <div className="flex items-center justify-between">
                <span>Demo account</span>
                <button
                  type="button"
                  onClick={fillDemo}
                  className="text-foreground hover:underline"
                >
                  Fill in
                </button>
              </div>
              <div className="mt-1 font-mono text-[11px] text-foreground/80">
                demo@threados.com / demo1234
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
