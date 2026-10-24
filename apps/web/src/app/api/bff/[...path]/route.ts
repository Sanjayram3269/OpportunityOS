// /api/bff/[...path] — the only bridge between the browser and FastAPI.
//
// The client calls e.g. GET /api/bff/profiles/1; this handler validates the
// decoded path segments against the strict allowlist in
// src/lib/server/proxy.ts, authenticates the signed session cookie,
// CSRF-checks state-changing methods, and forwards the request upstream
// with the server-side bearer token attached. Anything else is rejected
// before any network call happens.

import { handleBffProxy } from "@/lib/server/proxy";

export async function GET(
  request: Request,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return handleBffProxy(request, path);
}

export async function POST(
  request: Request,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return handleBffProxy(request, path);
}

export async function PATCH(
  request: Request,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return handleBffProxy(request, path);
}

export async function DELETE(
  request: Request,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return handleBffProxy(request, path);
}

// Never statically optimize or cache authenticated proxy responses.
export const dynamic = "force-dynamic";
