import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The API lives on a separate origin in all envs.
  // Direct browser calls go through the typed API client in lib/api-client.ts.
  env: {
    NEXT_PUBLIC_API_URL: process.env.API_URL ?? "http://localhost:8000",
  },
  // Security headers (production-grade from day one)
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
