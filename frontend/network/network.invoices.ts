import { httpClient } from "@/httpclient/httpclient";
import type { FileResult, InvoicePage, InvoiceQuery, Report } from "@/lib/types";
import type { ApiSuccess } from "@/network/network.types";

export const PAGE_SIZE = 25;

export const DEFAULT_QUERY: InvoiceQuery = { page: 1, q: "", direction: "", month: "", currency: "", flagged: false, sort: "due_date", order: "asc" };

function invoicesPath(query: InvoiceQuery): string {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(PAGE_SIZE) });
  if (query.q.trim()) params.set("q", query.q.trim());
  for (const key of ["direction", "month", "currency"] as const) if (query[key]) params.set(key, query[key]);
  if (query.flagged) params.set("flagged", "true");
  if (query.sort !== DEFAULT_QUERY.sort || query.order !== DEFAULT_QUERY.order) {
    params.set("sort", query.sort);
    params.set("order", query.order);
  }
  return `/api/invoices?${params}`;
}

const report = (): Promise<ApiSuccess<Report>> => httpClient.get<Report>("/api/report");

const list = (query: InvoiceQuery, signal?: AbortSignal): Promise<ApiSuccess<InvoicePage>> => httpClient.get<InvoicePage>(invoicesPath(query), signal);

const upload = (files: File[]): Promise<ApiSuccess<{ results: FileResult[] }>> => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));
  return httpClient.post<{ results: FileResult[] }>("/api/upload", form);
};

const retryRates = (): Promise<ApiSuccess<{ updated: number }>> => httpClient.post<{ updated: number }>("/api/retry-rates");

const reset = (): Promise<ApiSuccess<{ deleted: number }>> => httpClient.delete<{ deleted: number }>("/api/data");

export const networkInvoices = { report, list, upload, retryRates, reset };
