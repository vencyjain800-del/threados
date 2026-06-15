"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { settings, auth } from "@/lib/api-client";
import type { InventorySettingsResponse } from "@threados/shared-types";
import { AppNav } from "@/components/AppNav";

interface FormState {
  default_lead_time: string;
  target_cover_days: string;
  review_period_days: string;
  service_level: string;
  dead_stock_threshold_days: string;
}

const DEFAULTS: FormState = {
  default_lead_time: "14",
  target_cover_days: "30",
  review_period_days: "7",
  service_level: "0.950",
  dead_stock_threshold_days: "90",
};

function toFormState(s: InventorySettingsResponse): FormState {
  return {
    default_lead_time: String(s.default_lead_time),
    target_cover_days: String(s.target_cover_days),
    review_period_days: String(s.review_period_days),
    service_level: s.service_level,
    dead_stock_threshold_days: String(s.dead_stock_threshold_days),
  };
}

const SERVICE_LEVEL_OPTIONS = [
  { value: "0.900", label: "90% — low" },
  { value: "0.950", label: "95% — standard" },
  { value: "0.975", label: "97.5% — high" },
  { value: "0.990", label: "99% — very high" },
] as const;

function InventorySettingsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemoMode = searchParams.get("demo") === "true";
  const [form, setForm] = useState<FormState>(DEFAULTS);
  const [loading, setLoading] = useState(!isDemoMode);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (isDemoMode) return;
    auth.me().catch(() => router.push("/login"));

    settings
      .getInventory()
      .then((s) => {
        setForm(toFormState(s));
      })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [router, isDemoMode]);

  const handleChange = (field: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
    setSaveError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setSaveError(null);

    const lead = parseInt(form.default_lead_time, 10);
    const cover = parseInt(form.target_cover_days, 10);
    const review = parseInt(form.review_period_days, 10);
    const dead = parseInt(form.dead_stock_threshold_days, 10);

    if (isNaN(lead) || isNaN(cover) || isNaN(review) || isNaN(dead)) {
      setSaveError("All fields must be valid numbers.");
      setSaving(false);
      return;
    }

    try {
      await settings.updateInventory({
        default_lead_time: lead,
        target_cover_days: cover,
        review_period_days: review,
        service_level: form.service_level,
        dead_stock_threshold_days: dead,
      });
      setSaved(true);
    } catch {
      setSaveError("Failed to save settings. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !isDemoMode) {
    return (
      <div className="min-h-screen bg-gray-50">
        <AppNav activePath="inventory" />
        <main className="max-w-2xl mx-auto px-6 py-10">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-gray-200 rounded w-48" />
            <div className="h-4 bg-gray-200 rounded w-64" />
            <div className="h-64 bg-gray-200 rounded-lg" />
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <AppNav activePath="inventory" />

      <main className="max-w-2xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link
            href="/inventory"
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Inventory
          </Link>
          <span className="text-gray-300">/</span>
          <span className="text-sm text-gray-700 font-medium">Settings</span>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-1">Inventory Settings</h1>
        <p className="text-sm text-gray-500 mb-8">
          These defaults are used when computing safety stock, reorder points, and recommended
          order quantities. Changes take effect on the next recommendation run.
        </p>

        <form onSubmit={(e) => { void handleSubmit(e); }} className="space-y-6">
          {/* Lead time */}
          <FormSection
            title="Lead Time"
            description="Default number of days from placing an order to receiving stock."
          >
            <NumberInput
              id="lead_time"
              value={form.default_lead_time}
              unit="days"
              min={1}
              max={365}
              onChange={(v) => handleChange("default_lead_time", v)}
            />
          </FormSection>

          {/* Target cover days */}
          <FormSection
            title="Target Cover Days"
            description="How many days of stock you want to hold beyond the safety stock buffer."
          >
            <NumberInput
              id="target_cover"
              value={form.target_cover_days}
              unit="days"
              min={1}
              max={365}
              onChange={(v) => handleChange("target_cover_days", v)}
            />
          </FormSection>

          {/* Review period */}
          <FormSection
            title="Review Period"
            description="How often you review and place orders. Used in the recommended order quantity formula."
          >
            <NumberInput
              id="review_period"
              value={form.review_period_days}
              unit="days"
              min={1}
              max={90}
              onChange={(v) => handleChange("review_period_days", v)}
            />
          </FormSection>

          {/* Service level */}
          <FormSection
            title="Service Level"
            description="Target probability of not stocking out during the lead time. Higher = more safety stock."
          >
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {SERVICE_LEVEL_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleChange("service_level", opt.value)}
                  className={`px-3 py-2 rounded-md border text-sm font-medium transition-colors ${
                    form.service_level === opt.value
                      ? "bg-brand-600 text-white border-brand-600"
                      : "bg-white text-gray-700 border-gray-300 hover:border-brand-400"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </FormSection>

          {/* Dead stock threshold */}
          <FormSection
            title="Dead Stock Threshold"
            description="Variants with no sales for this many days (and stock on hand) are classified as dead stock."
          >
            <NumberInput
              id="dead_stock"
              value={form.dead_stock_threshold_days}
              unit="days"
              min={7}
              max={730}
              onChange={(v) => handleChange("dead_stock_threshold_days", v)}
            />
          </FormSection>

          {/* Safety stock preview */}
          <SsPreview
            z={form.service_level}
            leadTime={parseInt(form.default_lead_time, 10)}
          />

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-md bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Saving…" : "Save settings"}
            </button>
            {saved && (
              <span className="text-sm text-green-600 flex items-center gap-1">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Saved
              </span>
            )}
            {saveError && <span className="text-sm text-red-600">{saveError}</span>}
          </div>
        </form>

        {/* Info box */}
        <div className="mt-10 rounded-md bg-blue-50 border border-blue-200 px-4 py-4 text-sm text-blue-800">
          <p className="font-semibold mb-1">How safety stock is calculated</p>
          <p className="font-mono text-xs bg-blue-100 rounded px-2 py-1 mt-2 inline-block">
            SS = z × σ_d × √(Lead Time)
          </p>
          <p className="mt-2">
            Where <strong>z</strong> is the z-score for your service level, <strong>σ_d</strong>{" "}
            is the daily demand standard deviation, and <strong>Lead Time</strong> is in days.
          </p>
        </div>
      </main>
    </div>
  );
}

export default function InventorySettingsPage() {
  return <Suspense><InventorySettingsPageInner /></Suspense>;
}

function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 px-5 py-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
      </div>
      {children}
    </div>
  );
}

function NumberInput({
  id,
  value,
  unit,
  min,
  max,
  onChange,
}: {
  id: string;
  value: string;
  unit: string;
  min: number;
  max: number;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        id={id}
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value)}
        className="w-24 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      <span className="text-sm text-gray-500">{unit}</span>
    </div>
  );
}

// Show a live safety stock preview at example demand values
function SsPreview({ z, leadTime }: { z: string; leadTime: number }) {
  const zScores: Record<string, number> = {
    "0.900": 1.282,
    "0.950": 1.645,
    "0.975": 1.96,
    "0.990": 2.326,
  };
  const zVal = zScores[z] ?? 1.645;
  const lt = isNaN(leadTime) || leadTime <= 0 ? 14 : leadTime;
  const exampleSigma = 5; // units/day
  const ss = Math.ceil(zVal * exampleSigma * Math.sqrt(lt));

  return (
    <div className="rounded-md bg-gray-50 border border-gray-200 px-4 py-3 text-sm text-gray-600">
      <span className="font-medium text-gray-700">Example: </span>
      With σ_d = {exampleSigma} units/day, lead time = {lt} days, service level z = {zVal} →{" "}
      <span className="font-semibold text-gray-900">safety stock ≈ {ss} units</span>
    </div>
  );
}
