import type { NextConfig } from "next";

// The Atria FastAPI backend (backend/main.py). Proxied so the browser only talks to
// this origin, which also keeps a single cloudflared tunnel enough for judges.
const ATRIA_API_URL = process.env.ATRIA_API_URL ?? "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${ATRIA_API_URL}/:path*` }];
  },
};

export default nextConfig;
