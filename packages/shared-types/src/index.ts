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

// ── Catalogue ─────────────────────────────────────────────────────────────────

export interface VariantResponse {
  id: string;
  shopify_id: number;
  sku: string | null;
  title: string | null;
  option_color: string | null;
  option_size: string | null;
  price: string | null; // Decimal serialised as string
  barcode: string | null;
  inventory_available: number | null;
}

export interface ProductResponse {
  id: string;
  shopify_id: number;
  title: string;
  product_type: string | null;
  vendor: string | null;
  status: string | null;
  variants: VariantResponse[];
}

export interface CollectionResponse {
  id: string;
  shopify_id: number;
  title: string;
}

export interface ProductListResponse {
  items: ProductResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface CollectionListResponse {
  items: CollectionResponse[];
  total: number;
  page: number;
  page_size: number;
}

// ── Orders ────────────────────────────────────────────────────────────────────

export interface LineItemResponse {
  id: string;
  variant_id: string | null;
  quantity: number;
  unit_price: string | null;
  discount: string;
  refunded_qty: number;
}

export interface OrderResponse {
  id: string;
  shopify_id: number;
  ordered_at: string; // ISO datetime
  financial_status: string | null;
  channel: string | null;
  discount_total: string;
  line_items: LineItemResponse[];
}

export interface OrderListResponse {
  items: OrderResponse[];
  total: number;
  page: number;
  page_size: number;
}

// ── Inventory ─────────────────────────────────────────────────────────────────

export interface InventoryLevelResponse {
  variant_id: string;
  location_id: number;
  available: number;
  updated_at: string; // ISO datetime
}

export interface InventoryLevelListResponse {
  items: InventoryLevelResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface InventorySummaryItemResponse {
  variant_id: string;
  sku: string | null;
  variant_title: string | null;
  product_title: string | null;
  total_available: number;
}

export interface InventorySummaryResponse {
  items: InventorySummaryItemResponse[];
  total: number;
  page: number;
  page_size: number;
}

// ── Sync ──────────────────────────────────────────────────────────────────────

export interface SyncRunResponse {
  id: string;
  kind: string;
  status: SyncStatus;
  entities: Record<string, number>;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface SyncRunListResponse {
  items: SyncRunResponse[];
  total: number;
}

export interface SyncTriggerResponse {
  triggered: boolean;
  sync_run_id: string | null;
  message: string;
}

// ── API error shape ───────────────────────────────────────────────────────────

export interface ApiErrorDetail {
  detail: string | { loc: (string | number)[]; msg: string; type: string }[];
}
