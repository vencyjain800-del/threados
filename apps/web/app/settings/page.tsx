"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth, shopify, sync } from "@/lib/api-client";
import type { ShopifyStatusResponse, SyncRunResponse } from "@threados/shared-types";

export default function SettingsPage() {
  const router = useRouter();
  const [me, setMe] = useState<{ email: string; active_brand_id?: string | null } | null>(null);
  const [shopifyStatus, setShopifyStatus] = useState<ShopifyStatusResponse | null>(null);
  const [recentRuns, setRecentRuns] = useState<SyncRunResponse[]>([]);
  const [disconnecting, setDisconnecting] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    auth.me()
      .then((data) => setMe({ email: data.email, active_brand_id: data.active_brand_id }))
      .catch(() => router.push("/login"));

    shopify.status().then(setShopifyStatus).catch(() => null);
    sync.listRuns({ limit: 10 }).then((res) => setRecentRuns(res.items)).catch(() => null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleDisconnect() {
    if (!confirm("Disconnect your Shopify store? Syncing will stop. Your existing data will remain in ThreadOS.")) return;
    setDisconnecting(true);
    try {
      await shopify.disconnect();
      setShopifyStatus({ connected: false });
      setMessage({ type: "success", text: "Shopify store disconnected." });
    } catch {
      setMessage({ type: "error", text: "Failed to disconnect. Please try again." });
    } finally {
      setDisconnecting(false);
    }
  }

  async function handleTriggerSync() {
    setTriggering(true);
    try {
      const result = await sync.trigger();
      if (result.triggered) {
        setMessage({ type: "success", text: "Sync triggered. Check sync history below." });
        const updated = await sync.listRuns({ limit: 10 });
        setRecentRuns(updated.items);
        // Refresh status to pick up syncing state
        shopify.status().then(setShopifyStatus).catch(() => null);
      } else {
        setMessage({ type: "error", text: result.message });
      }
    } catch {
      setMessage({ type: "error", text: "Could not trigger sync. Please try again." });
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <Link href="/dashboard" className="text-lg font-bold text-brand-700">ThreadOS</Link>
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-gray-900">Settings</span>
          <button
            onClick={async () => { await auth.logout(); router.push("/login"); }}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Sign out
          </button>
        </div>
      </nav>

      <main className="max-w-2xl mx-auto px-6 py-10 space-y-8">
        {message && (
          <div className={`rounded-md px-4 py-3 text-sm flex items-center justify-between ${
            message.type === "success"
              ? "bg-green-50 border border-green-200 text-green-800"
              : "bg-red-50 border border-red-200 text-red-800"
          }`}>
            <span>{message.text}</span>
            <button onClick={() => setMessage(null)} className="ml-4 font-bold">×</button>
          </div>
        )}

        {/* Brand profile */}
        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Brand profile</h3>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Email</dt>
              <dd className="font-medium text-gray-900">{me?.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Brand ID</dt>
              <dd className="font-medium text-gray-900 font-mono text-xs truncate max-w-[220px]">
                {me?.active_brand_id ?? "—"}
              </dd>
            </div>
          </dl>
        </section>

        {/* Shopify connection */}
        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Shopify store</h3>

          {shopifyStatus?.connected ? (
            <div className="space-y-5">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Status</dt>
                  <dd className="flex items-center gap-1.5">
                    <SyncStateDot state={shopifyStatus.sync_state} />
                    <span className="font-medium text-gray-900 capitalize">
                      {shopifyStatus.sync_state === "syncing" ? "Syncing…" : "Connected"}
                    </span>
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-gray-500">Store</dt>
                  <dd className="font-medium text-gray-900">{shopifyStatus.shop_domain}</dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-gray-500">Last sync</dt>
                  <dd className="font-medium text-gray-900">
                    {shopifyStatus.last_sync_at
                      ? new Date(shopifyStatus.last_sync_at).toLocaleString()
                      : "Not yet synced"}
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-gray-500">Products imported</dt>
                  <dd className="font-medium text-gray-900">
                    {shopifyStatus.products_imported != null
                      ? shopifyStatus.products_imported.toLocaleString()
                      : "—"}
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-gray-500">Orders imported</dt>
                  <dd className="font-medium text-gray-900">
                    {shopifyStatus.orders_imported != null
                      ? shopifyStatus.orders_imported.toLocaleString()
                      : "—"}
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-gray-500">Scopes</dt>
                  <dd className="font-medium text-gray-900 text-right text-xs max-w-xs break-all">
                    {shopifyStatus.scopes}
                  </dd>
                </div>
              </dl>

              <div className="flex gap-3 pt-1">
                <button
                  onClick={handleTriggerSync}
                  disabled={triggering || shopifyStatus.sync_state === "syncing"}
                  className="rounded-md border border-brand-500 px-4 py-1.5 text-sm font-medium text-brand-600 hover:bg-brand-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {triggering ? "Queuing…" : "Sync now"}
                </button>
                <button
                  onClick={handleDisconnect}
                  disabled={disconnecting}
                  className="rounded-md border border-red-300 px-4 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-40"
                >
                  {disconnecting ? "Disconnecting…" : "Disconnect store"}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-1.5 text-sm text-gray-500">
                <span className="h-2 w-2 rounded-full bg-gray-300" />
                No store connected
              </div>
              <Link
                href="/onboarding"
                className="inline-block rounded-md bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
              >
                Connect Shopify store
              </Link>
            </div>
          )}
        </section>

        {/* Sync history */}
        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Sync history</h3>
          {recentRuns.length === 0 ? (
            <p className="text-sm text-gray-400">No sync runs yet.</p>
          ) : (
            <ul className="divide-y divide-gray-100 text-sm">
              {recentRuns.map((run) => (
                <li key={run.id} className="py-3 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <span className="capitalize text-gray-800 font-medium">{run.kind}</span>
                    <span className="ml-2 text-xs text-gray-400">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                    {run.entities && Object.keys(run.entities).length > 0 && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {Object.entries(run.entities)
                          .filter(([, v]) => (v as number) > 0)
                          .map(([k, v]) => `${(v as number).toLocaleString()} ${k}`)
                          .join(" · ")}
                      </p>
                    )}
                    {run.error && (
                      <p className="text-xs text-red-500 mt-0.5 truncate max-w-xs">{run.error}</p>
                    )}
                  </div>
                  <StatusBadge status={run.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}

function SyncStateDot({ state }: { state?: "idle" | "syncing" | "synced" | undefined }) {
  if (state === "syncing") return <span className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />;
  if (state === "synced") return <span className="h-2 w-2 rounded-full bg-green-500" />;
  return <span className="h-2 w-2 rounded-full bg-gray-400" />;
}

function StatusBadge({ status }: { status: string }) {
  const classes: Record<string, string> = {
    succeeded: "bg-green-100 text-green-700",
    running:   "bg-blue-100 text-blue-700",
    queued:    "bg-yellow-100 text-yellow-700",
    failed:    "bg-red-100 text-red-700",
    partial:   "bg-orange-100 text-orange-700",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium flex-shrink-0 ${classes[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}
