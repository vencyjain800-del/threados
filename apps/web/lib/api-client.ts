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

export { ApiError };
