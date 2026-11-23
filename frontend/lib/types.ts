export type Direction = "bejovo" | "kimeno";
export type UploadStatus = "ok" | "figyelmeztetes" | "duplikalt" | "hiba";

export interface MonthRow {
  month: string;
  incoming: number;
  outgoing: number;
}

export interface PartnerColumn {
  name: string;
  tax_ids: string[];
  incoming: number;
  outgoing: number;
  names: string[];
}

export interface Invoice {
  id: number;
  invoice_no: string;
  direction: Direction;
  seller_name: string | null;
  seller_tax_ids: string[];
  buyer_name: string | null;
  buyer_tax_ids: string[];
  partner_name: string;
  issue_date: string;
  supply_date: string;
  due_date: string;
  currency: string;
  gross_total: string;
  net_total: string | null;
  vat_total: string | null;
  rate: string | null;
  rate_unit: number | null;
  rate_day: string | null;
  huf_total: number | null;
  warnings: string[];
  method: string;
  source_filename: string;
}

export interface FailedUpload {
  filename: string;
  status: UploadStatus;
  message: string | null;
  created_at: string;
}

export interface Company {
  name: string;
  tax_id: string;
}

export interface Report {
  company: Company;
  months: MonthRow[];
  partners: PartnerColumn[];
  invoice_count: number;
  currencies: string[];
  pending_rates: number;
  failed_uploads: FailedUpload[];
}

export interface InvoicePage {
  items: Invoice[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export type SortKey = "invoice_no" | "seller" | "buyer" | "issue_date" | "supply_date" | "due_date" | "huf_total";

export interface InvoiceQuery {
  page: number;
  q: string;
  direction: Direction | "";
  month: string;
  currency: string;
  flagged: boolean;
  sort: SortKey;
  order: "asc" | "desc";
}

export interface FileResult {
  filename: string;
  status: UploadStatus;
  message: string | null;
  invoice_id?: number | null;
  invoice_no?: string | null;
}
