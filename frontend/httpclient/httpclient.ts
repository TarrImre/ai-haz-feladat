import { toast } from "sonner";
import { requireEnv } from "@/lib/env";
import type { ApiResponse, ApiSuccess } from "@/network/network.types";

const isServer = typeof window === "undefined";

// Szerveren a backend belső címe, böngészőben a saját proxy.
function baseUrl(): string {
  return isServer ? requireEnv("BACKEND_URL") : "";
}

function fail(message: string): never {
  if (!isServer) toast.error(message);
  throw new Error(message);
}

async function send<T>(url: string, init?: RequestInit): Promise<ApiSuccess<T>> {
  let res: Response;
  let body: ApiResponse<T>;
  try {
    res = await fetch(url, { cache: "no-store", ...init });
    body = (await res.json()) as ApiResponse<T>;
  } catch (err) {
    if (init?.signal?.aborted) throw err;
    return fail("A szerver nem érhető el, vagy hibás választ adott.");
  }
  if (body.status === "error") return fail(body.message);
  if (!res.ok) return fail(`Váratlan szerverválasz (HTTP ${res.status}).`);
  return body;
}

// Szinkron, hogy a hiányzó cím ne vesszen el a hívó .catch-ében.
function request<T>(path: string, init?: RequestInit): Promise<ApiSuccess<T>> {
  return send<T>(`${baseUrl()}${path}`, init);
}

export const httpClient = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: BodyInit) => request<T>(path, { method: "POST", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
