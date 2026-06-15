"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { shopify, sync } from "@/lib/api-client";
import type { ShopifyStatusResponse } from "@threados/shared-types";

// The four milestone states shown in the completion checklist.
// Each maps to a discrete backend condition we can actually poll.
type MilestoneKey = "account" | "connected" | "synced" | "forecast";

interface Milestones {
  account: boolean;
  connected: boolean;
  synced: boolean;
  forecast: boolean;
}

type WizardStep = "connect" | "syncing" | "done";

const POLL_INTERVAL_MS = 4_000;
const POLL_TIMEOUT_MS  = 10 * 60 * 1_000; // 10 min hard cap

function OnboardingPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [step, setStep] = useState<WizardStep>("connect");
  const [shop, setShop] = useState("");
  const [shopError, setShopError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);

  const [milestones, setMilestones] = useState<Milestones>({
    account:   true,   // always true by the time we reach this page (user is signed in)
    connected: false,
    synced:    false,
    forecast:  false,
  });

  // Latest status snapshot from polling (used for progress detail text)
  const [statusSnap, setStatusSnap] = useState<ShopifyStatusResponse | null>(null);

  const pollingRef = useRef(false);

  useEffect(() => {
    // If redirected back from Shopify OAuth with ?shopify=connected, enter syncing step
    if (searchParams.get("shopify") === "connected") {
      setStep("syncing");
      setMilestones((m) => ({ ...m, connected: true }));
      startPolling();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startPolling() {
    if (pollingRef.current) return;
    pollingRef.current = true;

    const deadline = Date.now() + POLL_TIMEOUT_MS;

    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

      try {
        const status = await shopify.status();
        setStatusSnap(status);

        if (!status.connected) continue;
        setMilestones((m) => ({ ...m, connected: true }));

        // "synced" = at least one succeeded run with product data
        const synced = (
          status.sync_state === "synced" &&
          status.products_imported != null &&
          status.products_imported > 0
        );
        if (synced) {
          setMilestones((m) => ({ ...m, synced: true }));
        }

        // "forecast" = check for a succeeded forecast sync run
        if (synced) {
          try {
            const runs = await sync.listRuns({ limit: 20 });
            const hasForecast = runs.items.some(
              (r) => r.kind === "forecast" && r.status === "succeeded"
            );
            if (hasForecast) {
              setMilestones((m) => ({ ...m, forecast: true }));
              setStep("done");
              pollingRef.current = false;
              return;
            }
          } catch {
            // Non-critical — keep polling
          }

          // Synced but no forecast yet — still show "done" after a grace period
          // (forecast job may still be running). We move to done anyway so
          // the user isn't blocked; the forecast milestone shows as pending.
          const allSyncDone = status.sync_state === "synced";
          if (allSyncDone) {
            // Give the forecast job up to 2 more poll cycles before declaring done
            await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS * 2));
            const runsAgain = await sync.listRuns({ limit: 20 }).catch(() => ({ items: [] }));
            const hasForecastNow = runsAgain.items.some(
              (r) => r.kind === "forecast" && r.status === "succeeded"
            );
            setMilestones((m) => ({ ...m, forecast: hasForecastNow }));
            setStep("done");
            pollingRef.current = false;
            return;
          }
        }
      } catch {
        // Transient network error — keep polling
      }
    }

    // Timed out — move to done regardless so the user isn't blocked
    setStep("done");
    pollingRef.current = false;
  }

  function handleConnectShopify(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setShopError(null);

    const raw = shop.trim().toLowerCase();
    if (!raw) {
      setShopError("Enter your Shopify store URL");
      return;
    }

    const normalized = raw.includes(".myshopify.com")
      ? raw
      : `${raw}.myshopify.com`;

    setRedirecting(true);
    window.location.href = shopify.installUrl(normalized);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (step === "syncing") {
    return (
      <OnboardingShell activeStep={2}>
        <div className="py-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="h-8 w-8 rounded-full border-4 border-brand-500 border-t-transparent animate-spin flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-gray-900">Importing your store data</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Pulling products, inventory and 90 days of orders
              </p>
            </div>
          </div>

          <MilestoneList milestones={milestones} statusSnap={statusSnap} />

          {statusSnap?.products_imported != null && statusSnap.products_imported > 0 && (
            <p className="mt-4 text-xs text-gray-400 text-center">
              {statusSnap.products_imported.toLocaleString()} products
              {statusSnap.orders_imported != null ? ` · ${statusSnap.orders_imported.toLocaleString()} orders` : ""} imported so far
            </p>
          )}
        </div>
      </OnboardingShell>
    );
  }

  if (step === "done") {
    const allComplete = milestones.account && milestones.connected && milestones.synced;
    return (
      <OnboardingShell activeStep={3}>
        <div className="py-6">
          <div className="flex items-center justify-center mb-5">
            <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
              <CheckIcon className="h-6 w-6 text-green-600" />
            </div>
          </div>
          <h3 className="text-center text-lg font-semibold text-gray-900 mb-1">
            {allComplete ? "You're ready to go!" : "Almost there"}
          </h3>
          <p className="text-center text-sm text-gray-500 mb-6">
            {allComplete
              ? "Your store is connected and data is syncing in the background."
              : "Your store is connected. Data will finish syncing shortly."}
          </p>

          <MilestoneList milestones={milestones} statusSnap={statusSnap} />

          <button
            onClick={() => router.push("/dashboard")}
            className="mt-6 w-full rounded-md bg-brand-600 px-6 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            Go to dashboard
          </button>
        </div>
      </OnboardingShell>
    );
  }

  // step === "connect"
  return (
    <OnboardingShell activeStep={1}>
      <h3 className="text-lg font-semibold text-gray-900 mb-1">Connect your Shopify store</h3>
      <p className="text-sm text-gray-500 mb-6">
        ThreadOS reads products, inventory, and 90 days of orders. Read-only — we never write to your store.
      </p>

      <form onSubmit={handleConnectShopify} className="space-y-4">
        <div>
          <label htmlFor="shop" className="block text-sm font-medium text-gray-700">
            Shopify store URL
          </label>
          <div className="mt-1 flex rounded-md shadow-sm">
            <input
              id="shop"
              type="text"
              value={shop}
              onChange={(e) => setShop(e.target.value)}
              placeholder="your-store"
              autoComplete="off"
              className="flex-1 min-w-0 rounded-l-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            <span className="inline-flex items-center rounded-r-md border border-l-0 border-gray-300 bg-gray-50 px-3 text-sm text-gray-500">
              .myshopify.com
            </span>
          </div>
          {shopError && (
            <p className="mt-1.5 text-xs text-red-600">{shopError}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={redirecting}
          className="w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {redirecting ? "Redirecting to Shopify…" : "Connect Shopify store"}
        </button>
      </form>

      <div className="mt-6 rounded-md bg-gray-50 border border-gray-200 p-4 text-xs text-gray-500 space-y-1">
        <p className="font-medium text-gray-700">Read-only access requested:</p>
        <p>• Products and variants</p>
        <p>• Inventory levels across all locations</p>
        <p>• Orders — up to 90 days of history</p>
      </div>
    </OnboardingShell>
  );
}

// ── Milestone checklist ────────────────────────────────────────────────────────

const MILESTONE_LABELS: Record<MilestoneKey, string> = {
  account:   "Account created",
  connected: "Shopify connected",
  synced:    "Data imported",
  forecast:  "Forecast generated",
};

function MilestoneList({
  milestones,
  statusSnap,
}: {
  milestones: Milestones;
  statusSnap: ShopifyStatusResponse | null;
}) {
  const keys: MilestoneKey[] = ["account", "connected", "synced", "forecast"];

  function sublabel(key: MilestoneKey): string | null {
    if (key === "synced" && statusSnap) {
      const p = statusSnap.products_imported;
      const o = statusSnap.orders_imported;
      if (p != null && p > 0) {
        return `${p.toLocaleString()} products · ${o != null ? o.toLocaleString() : "—"} orders`;
      }
    }
    return null;
  }

  return (
    <ul className="space-y-3">
      {keys.map((key) => {
        const done = milestones[key];
        const sub = sublabel(key);
        return (
          <li key={key} className="flex items-start gap-3">
            <span className={`mt-0.5 flex-shrink-0 h-5 w-5 rounded-full flex items-center justify-center ${
              done ? "bg-green-500" : "bg-gray-200"
            }`}>
              {done
                ? <CheckIcon className="h-3 w-3 text-white" />
                : <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
              }
            </span>
            <div>
              <span className={`text-sm ${done ? "text-gray-900 font-medium" : "text-gray-400"}`}>
                {MILESTONE_LABELS[key]}
              </span>
              {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// ── Shell ──────────────────────────────────────────────────────────────────────

function OnboardingShell({
  activeStep,
  children,
}: {
  activeStep: number;
  children: React.ReactNode;
}) {
  const steps = ["Connect Shopify", "Importing data", "Ready"];
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-16 px-4">
      <h1 className="text-2xl font-bold text-brand-700 mb-8">ThreadOS</h1>

      <div className="flex items-center mb-10">
        {steps.map((label, i) => {
          const n = i + 1;
          const done   = n < activeStep;
          const active = n === activeStep;
          return (
            <div key={n} className="flex items-center">
              <div className="flex flex-col items-center">
                <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold ${
                  done   ? "bg-brand-600 text-white"
                  : active ? "border-2 border-brand-600 text-brand-600"
                  : "border-2 border-gray-300 text-gray-400"
                }`}>
                  {done
                    ? <CheckIcon className="h-4 w-4" />
                    : n
                  }
                </div>
                <span className={`mt-1 text-xs ${active ? "text-brand-600 font-medium" : "text-gray-400"}`}>
                  {label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div className={`h-0.5 w-16 mx-1 mb-5 ${done ? "bg-brand-600" : "bg-gray-200"}`} />
              )}
            </div>
          );
        })}
      </div>

      <div className="w-full max-w-md bg-white rounded-lg shadow px-8 py-8">{children}</div>
    </div>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2.5" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

export default function OnboardingPage() { return <Suspense><OnboardingPageInner /></Suspense>; }
