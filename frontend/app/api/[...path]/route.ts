import type { NextRequest } from "next/server";

import { requireEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const backend = requireEnv("BACKEND_URL");
  const { path } = await ctx.params;
  const target = `${backend}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  try {
    const res = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      cache: "no-store",
      // A stream-törzs továbbításához kötelező.
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
    return new Response(res.body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    return Response.json({ status: "error", message: `A backend nem érhető el: ${(err as Error).message}` }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE };
