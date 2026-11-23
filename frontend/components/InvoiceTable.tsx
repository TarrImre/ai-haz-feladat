"use client";

import { useEffect, useRef, useState } from "react";
import Badge from "./Badge";
import { DEFAULT_QUERY, networkInvoices, PAGE_SIZE } from "@/network/network.invoices";
import { DIRECTION_LABEL, formatAmount, hufFmt, rateFmt } from "@/lib/format";
import type { Direction, Invoice, InvoicePage, InvoiceQuery, SortKey } from "@/lib/types";

function Party({ name, ids }: { name: string | null; ids: string[] }) {
  return (
    <>
      {name ?? ""}
      <span className="sub">{ids.join(", ")}</span>
    </>
  );
}

function Rate({ i }: { i: Invoice }) {
  if (i.currency === "HUF") return <>-</>;
  if (!i.rate || !i.rate_unit) return <>nincs</>;
  return (
    <>
      {rateFmt.format(Number(i.rate) / i.rate_unit)}
      <span className="sub">{i.rate_day}</span>
    </>
  );
}

const DEBOUNCE_MS = 300;

// Oldalszámok: első, utolsó, az aktuális környéke, közte "…".
function pageItems(page: number, pages: number): (number | "gap")[] {
  const out: (number | "gap")[] = [];
  for (let p = 1; p <= pages; p++) {
    const lone = (p === 2 && page === 4) || (p === pages - 1 && page === pages - 3);
    if (p === 1 || p === pages || Math.abs(p - page) <= 1 || lone) out.push(p);
    else if (out[out.length - 1] !== "gap") out.push("gap");
  }
  return out;
}

function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null;
  return (
    <nav className="pager" aria-label="Lapozás">
      <button className="btn" disabled={page === 1} onClick={() => onPage(page - 1)}>Előző</button>
      {pageItems(page, pages).map((p, i) =>
        p === "gap" ? <span key={`gap-${i}`} className="pager-gap">…</span> : (
          <button key={p} className={`btn${p === page ? " current" : ""}`} aria-current={p === page ? "page" : undefined} onClick={() => onPage(p)}>{p}</button>
        ),
      )}
      <button className="btn" disabled={page === pages} onClick={() => onPage(page + 1)}>Következő</button>
    </nav>
  );
}

const SORTABLE: { key: SortKey; label: string; num?: boolean }[] = [
  { key: "invoice_no", label: "Számlaszám" },
  { key: "seller", label: "Kiállító" },
  { key: "buyer", label: "Vevő" },
  { key: "issue_date", label: "Kiállítás" },
  { key: "supply_date", label: "Teljesítés" },
  { key: "due_date", label: "Határidő" },
  { key: "huf_total", label: "Bruttó HUF", num: true },
];
const SORT_LABEL = Object.fromEntries(SORTABLE.map((s) => [s.key, s])) as Record<SortKey, (typeof SORTABLE)[number]>;

function SortTh({ k, query, onSort }: { k: SortKey; query: InvoiceQuery; onSort: (k: SortKey) => void }) {
  const { label, num } = SORT_LABEL[k];
  const active = query.sort === k;
  return (
    <th className={num ? "num" : undefined} aria-sort={active ? (query.order === "asc" ? "ascending" : "descending") : "none"}>
      <button className={`sort${active ? " active" : ""}`} onClick={() => onSort(k)}>
        {label}
        <svg className="sort-icon" viewBox="0 0 8 12" width="8" height="12" aria-hidden="true">
          <path d="M4 1 7.5 5h-7z" className={active && query.order === "asc" ? "on" : undefined} />
          <path d="M4 11 .5 7h7z" className={active && query.order === "desc" ? "on" : undefined} />
        </svg>
      </button>
    </th>
  );
}

type Props = { initial: InvoicePage | null; version: number; totalCount: number; months: string[]; currencies: string[] };

export default function InvoiceTable({ initial, version, totalCount, months, currencies }: Props) {
  const [query, setQuery] = useState<InvoiceQuery>(DEFAULT_QUERY);
  const [input, setInput] = useState("");
  const [data, setData] = useState<InvoicePage | null>(initial);
  const [loading, setLoading] = useState(false);
  // A szerveren betöltött első oldalt nem kérjük le újra.
  const skipFirst = useRef(initial !== null && version === 0);

  useEffect(() => {
    if (input.trim() === query.q.trim()) return;
    const t = setTimeout(() => setQuery((cur) => ({ ...cur, q: input, page: 1 })), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input, query.q]);

  useEffect(() => {
    if (skipFirst.current) {
      skipFirst.current = false;
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    networkInvoices.list(query, ctrl.signal)
      .then(({ data }) => setData(data))
      .catch(() => { /* a httpclient már kiírta */ })
      .finally(() => { if (!ctrl.signal.aborted) setLoading(false); });
    return () => ctrl.abort();
  }, [query, version]);

  const filter = (patch: Partial<InvoiceQuery>) => setQuery((cur) => ({ ...cur, ...patch, page: 1 }));
  const sortBy = (sort: SortKey) => filter({ sort, order: query.sort === sort && query.order === "asc" ? "desc" : "asc" });
  const clearFilters = () => {
    setInput("");
    setQuery((cur) => ({ ...DEFAULT_QUERY, sort: cur.sort, order: cur.order }));
  };

  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const start = data ? (data.page - 1) * PAGE_SIZE : 0;
  const filtered = !!(query.q.trim() || query.direction || query.month || query.currency || query.flagged);

  return (
    <>
      <div className="panel-head">
        <h2>Számlák</h2>
        <div className="filters">
          <input type="search" placeholder="Keresés: számlaszám, partner, fájl" aria-label="Keresés a számlák között" value={input} onChange={(e) => setInput(e.target.value)} />
        </div>
      </div>
      <div className="toolbar">
        <label>
          Irány
          <select className="select" value={query.direction} onChange={(e) => filter({ direction: e.target.value as Direction | "" })}>
            <option value="">Mind</option>
            <option value="bejovo">Bejövő</option>
            <option value="kimeno">Kimenő</option>
          </select>
        </label>
        <label>
          Határidő hónapja
          <select className="select" value={query.month} onChange={(e) => filter({ month: e.target.value })}>
            <option value="">Mind</option>
            {months.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label>
          Pénznem
          <select className="select" value={query.currency} onChange={(e) => filter({ currency: e.target.value })}>
            <option value="">Mind</option>
            {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={query.flagged} onChange={(e) => filter({ flagged: e.target.checked })} />
          Csak figyelmeztetéses vagy árfolyam nélküli
        </label>
        {filtered && <button className="btn" onClick={clearFilters}>Szűrők törlése</button>}
      </div>
      <div className={`scroll${loading ? " loading" : ""}`} aria-busy={loading}>
        <table className="table">
          <thead>
            <tr>
              <SortTh k="invoice_no" query={query} onSort={sortBy} /><th>Irány</th>
              <SortTh k="seller" query={query} onSort={sortBy} /><SortTh k="buyer" query={query} onSort={sortBy} />
              <SortTh k="issue_date" query={query} onSort={sortBy} /><SortTh k="supply_date" query={query} onSort={sortBy} />
              <SortTh k="due_date" query={query} onSort={sortBy} />
              <th className="num">Eredeti összeg</th><th className="num">MNB-árfolyam</th>
              <SortTh k="huf_total" query={query} onSort={sortBy} />
            </tr>
          </thead>
          <tbody>
            {rows.map((i) => (
              <tr key={i.id} className={i.warnings.length ? "warn" : undefined}>
                <td>
                  {i.invoice_no}
                  <span className="sub">{i.source_filename}</span>
                  {i.warnings.map((w) => <span key={w} className="w">{w}</span>)}
                </td>
                <td><Badge kind={i.direction}>{DIRECTION_LABEL[i.direction]}</Badge></td>
                <td><Party name={i.seller_name} ids={i.seller_tax_ids} /></td>
                <td><Party name={i.buyer_name} ids={i.buyer_tax_ids} /></td>
                <td className="date">{i.issue_date}</td>
                <td className="date">{i.supply_date}</td>
                <td className="date">{i.due_date}</td>
                <td className="num">{formatAmount(i.gross_total, i.currency)}</td>
                <td className="num"><Rate i={i} /></td>
                <td className="num"><b>{i.huf_total == null ? "-" : hufFmt.format(i.huf_total)}</b></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && total === 0 && <p className="empty">Nincs a szűrésnek megfelelő számla.</p>}
      <div className="table-foot">
        <span className="panel-note">
          {total > 0 ? `${start + 1}-${start + rows.length}` : "0"} / {total} számla
          {filtered && ` (szűrve, összesen ${totalCount})`}
          {loading && " · betöltés…"}
        </span>
        {data && <Pager page={data.page} pages={data.pages} onPage={(page) => setQuery((cur) => ({ ...cur, page }))} />}
      </div>
    </>
  );
}
