/**
 * @threados/shared-types
 *
 * TypeScript types that mirror the FastAPI request/response schemas.
 * These are kept in sync with the backend — in CI, the OpenAPI spec is
 * generated from FastAPI and diffed against these types to catch drift.
 *
 * Sprint 1: auth + shopify types.
 * Later sprints add forecast, replenishment, buy-plan, and analytics types.
 */

// ── Enums ─────────────────────────────────────────────────────────────────────

export type UserRole = "owner" | "admin" | "member" | "viewer";

export type SyncStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "partial";

// ── Auth request/response ────────────────────────────────────────────────────

export interface SignUpRequest {
  email: string;
  password: string;
  name?: string;
  brand_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface MeResponse {
  id: string;
  email: string;
  name: string | null;
  created_at: string;
  active_brand_id: string | null;
}

export interface BrandResponse {
  id: string;
  name: string;
  country: string;
  currency: string;
  plan: string;
}

export interface SwitchBrandRequest {
  brand_id: string;
}

// ── Shopify ──────────────────────────────────────────────────────────────────

export interface ShopifyStatusResponse {
  connected: boolean;
  shop_domain?: string;
  scopes?: string;
  installed_at?: string;
}

// ── API error shape ───────────────────────────────────────────────────────────

export interface ApiErrorDetail {
  detail: string | { loc: (string | number)[]; msg: string; type: string }[];
}
