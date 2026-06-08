/**
 * Root landing page — Sprint 1 scaffold only.
 * Auth flows and the full dashboard are built in Sprints 4–6.
 */
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-4xl font-bold text-brand-700 mb-4">ThreadOS</h1>
        <p className="text-lg text-gray-600 mb-8">
          AI-powered demand forecasting and inventory management for fashion brands.
        </p>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-6 text-sm text-gray-500">
          <p className="font-medium text-gray-700 mb-2">Sprint 1 — Foundation</p>
          <p>API and database layers are live. UI screens are built in Sprints 4–6.</p>
          <div className="mt-4 space-y-1 text-left font-mono text-xs">
            <p>✅ Authentication API (/auth/*)</p>
            <p>✅ Shopify OAuth (/shopify/*)</p>
            <p>✅ Row-Level Security (RLS)</p>
            <p>✅ Multi-brand tenancy</p>
            <p>⏳ Shopify data sync (Sprint 2)</p>
            <p>⏳ Forecasting models (Sprint 3)</p>
            <p>⏳ Dashboard UI (Sprint 4–6)</p>
          </div>
        </div>
      </div>
    </main>
  );
}
