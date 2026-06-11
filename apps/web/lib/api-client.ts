/**
 * Typed API client for ThreadOS.
 *
 * Uses the shared-types package for request/response shapes, keeping the
 * frontend and backend in sync via the generated OpenAPI types.
 *
 * Sprint 1: client is wired up and typed; route handlers use it in Sprints 4–6.
 */
import type {
  MeResponse,
  SignUpRequest,
  LoginRequest,
  BrandResponse,
  SwitchBrandRequest,
  ShopifyStatusResponse,
  ProductListResponse,
  ProductResponse,
  CollectionListResponse,
  OrderListResponse,
  OrderResponse,
  InventoryLevelListResponse,
  InventorySummaryResponse,
  SyncRunListResponse,
  SyncRunResponse,
  SyncTriggerResponse,
} from "@threados/shared-types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    credentials: "include", // send session cookie cross-origin
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...options,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, `API error ${res.status}`, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export const auth = {
  signUp: (body: SignUpRequest) =>
    request<MeResponse>("POST", "/auth/signup", body),

  login: (body: LoginRequest) =>
    request<MeResponse>("POST", "/auth/login", body),

  logout: () => request<void>("POST", "/auth/logout"),

  me: () => request<MeResponse>("GET", "/auth/me"),

  listBrands: () => request<BrandResponse[]>("GET", "/auth/brands"),

  switchBrand: (body: SwitchBrandRequest) =>
    request<MeResponse>("POST", "/auth/switch-brand", body),
};

// ── Shopify ───────────────────────────────────────────────────────────────────

export const shopify = {
  status: () => request<ShopifyStatusResponse>("GET", "/shopify/status"),
};

// ── Catalogue ─────────────────────────────────────────────────────────────────

export const catalogue = {
  listProducts: (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    search?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    if (params?.status) qs.set("status", params.status);
    if (params?.search) qs.set("search", params.search);
    const query = qs.toString();
    return request<ProductListResponse>(
      "GET",
      `/catalogue/products${query ? `?${query}` : ""}`,
    );
  },

  getProduct: (productId: string) =>
    request<ProductResponse>("GET", `/catalogue/products/${productId}`),

  listCollections: (params?: { page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const query = qs.toString();
    return request<CollectionListResponse>(
      "GET",
      `/catalogue/collections${query ? `?${query}` : ""}`,
    );
  },

  listCollectionProducts: (
    collectionId: string,
    params?: { page?: number; page_size?: number },
  ) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const query = qs.toString();
    return request<ProductListResponse>(
      "GET",
      `/catalogue/collections/${collectionId}/products${query ? `?${query}` : ""}`,
    );
  },
};

// ── Orders ────────────────────────────────────────────────────────────────────

export const orders = {
  list: (params?: {
    page?: number;
    page_size?: number;
    financial_status?: string;
    from_date?: string;
    to_date?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    if (params?.financial_status) qs.set("financial_status", params.financial_status);
    if (params?.from_date) qs.set("from_date", params.from_date);
    if (params?.to_date) qs.set("to_date", params.to_date);
    const query = qs.toString();
    return request<OrderListResponse>(
      "GET",
      `/orders${query ? `?${query}` : ""}`,
    );
  },

  get: (orderId: string) =>
    request<OrderResponse>("GET", `/orders/${orderId}`),
};

// ── Inventory ─────────────────────────────────────────────────────────────────

export const inventory = {
  list: (params?: {
    page?: number;
    page_size?: number;
    variant_id?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    if (params?.variant_id) qs.set("variant_id", params.variant_id);
    const query = qs.toString();
    return request<InventoryLevelListResponse>(
      "GET",
      `/inventory${query ? `?${query}` : ""}`,
    );
  },

  summary: (params?: { page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const query = qs.toString();
    return request<InventorySummaryResponse>(
      "GET",
      `/inventory/summary${query ? `?${query}` : ""}`,
    );
  },
};

// ── Sync ──────────────────────────────────────────────────────────────────────

export const sync = {
  listRuns: (params?: { limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    const query = qs.toString();
    return request<SyncRunListResponse>(
      "GET",
      `/sync/runs${query ? `?${query}` : ""}`,
    );
  },

  getRun: (runId: string) =>
    request<SyncRunResponse>("GET", `/sync/runs/${runId}`),

  trigger: () =>
    request<SyncTriggerResponse>("POST", "/sync/trigger"),
};

export { ApiError };
