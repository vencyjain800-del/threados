"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { auth, shopify, sync } from "@/lib/api-client";
import type { ShopifyStatusResponse, SyncRunResponse } from "@threados/shared-types";

function DashboardPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [me, setMe] = useState<{ email: string; active_brand_id?: string | null } | null>(null);
  const [shopifyStatus, setShopifyStatus] = useState<ShopifyStatusResponse | null>(null);
  const [recentRuns, setRecentRuns] = useState<SyncRunResponse[]>([]);
  const [banner, setBanner] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("shopify") === "connected") {
      setBanner("Shopify connected! Your data is syncing in the background.");
    }

    auth.me()
      .then((data) => setMe({ email: data.email, active_brand_id: data.active_brand_id }))
      .catch(() => router.push("/login"));

    shopify.status()
      .then(setShopifyStatus)
      .catch(() => null);

    sync.listRuns({ limit: 5 })
      .then((res) => setRecentRuns(res.items))
      .catch(() => null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <span className="text-lg font-bold text-brand-700">ThreadOS</span>
        <div className="flex items-center gap-4">
          <Link href="/settings" className="text-sm text-gray-600 hover:text-gray-900">
            Settings
          </Link>
          <button
            onClick={async () => { await auth.logout(); router.push("/login"); }}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Sign out
          </button>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-10">
        {banner && (
          <div className="mb-6 rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800 flex items-center justify-between">
            <span>{banner}</span>
            <button onClick={() => setBanner(null)} className="text-green-600 hover:text-green-800">×</button>
          </div>
        )}

        <h2 className="text-2xl font-bold text-gray-900 mb-1">Dashboard</h2>
        <p className="text-sm text-gray-500 mb-8">{me?.email}</p>

        {/* Connection status card */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Shopify connection</h3>
          {shopifyStatus?.connected ? (
            <div className="flex items-center gap-3">
              <span className="h-2.5 w-2.5 rounded-full bg-green-500 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-900">{shopifyStatus.shop_domain}</p>
                <p className="text-xs text-gray-500">
                  Connected · Scopes: {shopifyStatus.scopes}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <span className="h-2.5 w-2.5 rounded-full bg-gray-300 flex-shrink-0" />
              <div>
                <p className="text-sm text-gray-700">No store connected</p>
                <Link href="/onboarding" className="text-xs text-brand-600 hover:text-brand-700 font-medium">
                  Connect Shopify →
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Recent sync runs */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Recent syncs</h3>
          {recentRuns.length === 0 ? (
            <p className="text-sm text-gray-400">No sync runs yet.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {recentRuns.map((run) => (
                <li key={run.id} className="py-3 flex items-center justify-between">
                  <div>
                    <span className="text-sm text-gray-800 capitalize">{run.kind}</span>
                    <span className="ml-2 text-xs text-gray-400">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                  <StatusBadge status={run.status} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const classes: Record<string, string> = {
    succeeded: "bg-green-100 text-green-700",
    running: "bg-blue-100 text-blue-700",
    queued: "bg-yellow-100 text-yellow-700",
    failed: "bg-red-100 text-red-700",
    partial: "bg-orange-100 text-orange-700",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

export default function DashboardPage() { return <Suspense><DashboardPageInner /></Suspense>; }
