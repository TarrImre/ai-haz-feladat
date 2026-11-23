"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { toast } from "sonner";
import CashflowChart from "./CashflowChart";
import InvoiceTable from "./InvoiceTable";
import PartnerTable from "./PartnerTable";
import UploadPanel from "./UploadPanel";
import UploadResults from "./UploadResults";
import { networkInvoices } from "@/network/network.invoices";
import { formatHuf } from "@/lib/format";
import type { FileResult, InvoicePage, Report } from "@/lib/types";

const color = (c: string) => ({ "--c": c }) as CSSProperties;
const SIDE_KEY = "side-collapsed";

export default function Dashboard({ initial, initialInvoices }: { initial: Report | null; initialInvoices: InvoicePage | null }) {
  const [report, setReport] = useState<Report | null>(initial);
  const [error, setError] = useState<string | null>(initial ? null : "A backend nem érhető el, a kimutatás nem tölthető be.");
  const [results, setResults] = useState<FileResult[]>([]);
  const [version, setVersion] = useState(0);
  const [collapsed, setCollapsed] = useState(false);

  // Csak a betöltés után olvassuk, hogy a szerveres HTML egyezzen.
  useEffect(() => {
    try { setCollapsed(localStorage.getItem(SIDE_KEY) === "1"); } catch { /* tiltott tároló */ }
  }, []);

  function toggleSide() {
    setCollapsed((c) => {
      try { localStorage.setItem(SIDE_KEY, c ? "0" : "1"); } catch { /* tiltott tároló */ }
      return !c;
    });
  }

  const reload = useCallback(async () => {
    try {
      const { data } = await networkInvoices.report();
      setReport(data);
      setVersion((v) => v + 1);
      setError(null);
    } catch {
      // A hibát a httpclient már kiírta.
    }
  }, []);

  const uploaded = useCallback(async (r: FileResult[]) => {
    setResults(r);
    await reload();
  }, [reload]);

  async function retryRates() {
    try {
      const { message } = await networkInvoices.retryRates();
      toast.success(message);
    } catch {
      return;
    }
    await reload();
  }

  async function reset() {
    const n = report?.invoice_count ?? 0;
    if (!confirm(`Biztosan törlöd mind a ${n} feldolgozott számlát és a feltöltési naplót? A tárolt MNB-árfolyamok megmaradnak.`)) return;
    try {
      await networkInvoices.reset();
    } catch {
      return;
    }
    setResults([]);
    await reload();
  }

  const has = (report?.invoice_count ?? 0) > 0;
  const inSum = report?.months.reduce((s, m) => s + m.incoming, 0) ?? 0;
  const outSum = report?.months.reduce((s, m) => s + m.outgoing, 0) ?? 0;

  return (
    <div className={`app${collapsed ? " collapsed" : ""}`}>
      <aside className="side">
        <div className="side-head">
          <div className="side-title">
            <h1>Számlafeldolgozó</h1>
            {report && <div className="co">{report.company.name}<br />{report.company.tax_id}</div>}
          </div>
          <button className="side-toggle" onClick={toggleSide} aria-expanded={!collapsed} aria-controls="side-body" title={collapsed ? "Oldalsáv kinyitása" : "Oldalsáv becsukása"}>
            <svg className="icon-side" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
              <rect x="1.5" y="2.5" width="13" height="11" fill="none" stroke="currentColor" />
              <path d="M6 2.5v11" stroke="currentColor" />
              <path d={collapsed ? "M9 6l2 2-2 2" : "M11 6l-2 2 2 2"} fill="none" stroke="currentColor" />
            </svg>
            <svg className="icon-top" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
              <rect x="1.5" y="2.5" width="13" height="11" fill="none" stroke="currentColor" />
              <path d="M1.5 6h13" stroke="currentColor" />
              <path d={collapsed ? "M6 9l2 2 2-2" : "M6 11l2-2 2 2"} fill="none" stroke="currentColor" />
            </svg>
            <span className="sr-only">{collapsed ? "Oldalsáv kinyitása" : "Oldalsáv becsukása"}</span>
          </button>
        </div>
        <div className="side-body" id="side-body">
          <UploadPanel onUploaded={uploaded} />
          {has && (
            <>
              <div className="stat" style={color("var(--in)")}><span>Bejövő, bruttó</span><b>{formatHuf(inSum)}</b></div>
              <div className="stat" style={color("var(--out)")}><span>Kimenő, bruttó</span><b>{formatHuf(outSum)}</b></div>
              <div className="stat plain"><span>Számlák / partnerek</span><b>{report?.invoice_count} / {report?.partners.length}</b></div>
            </>
          )}
          <div className="side-actions">
            {!!report?.pending_rates && <button className="side-btn" onClick={() => void retryRates()}>Árfolyamok újrapróbálása</button>}
            {has && <button className="side-btn danger" onClick={() => void reset()}>Adatok törlése</button>}
          </div>
        </div>
      </aside>

      <main className="main">
        {error && <div className="panel alert">{error}</div>}
        {results.length > 0 && <UploadResults results={results} onClose={() => setResults([])} />}

        {report && !has && <div className="panel empty">Még nincs feldolgozott számla. Tölts fel PDF-eket a bal oldali sávban.</div>}

        {report && has && (
          <>
            <section className="panel">
              <div className="panel-head">
                <h2>Havi bruttó összeg, fizetési határidő szerint</h2>
                <div className="key">
                  <span style={color("var(--in)")}>Bejövő</span>
                  <span style={color("var(--out)")}>Kimenő</span>
                </div>
              </div>
              <div className="panel-body"><CashflowChart months={report.months} /></div>
              {report.pending_rates > 0 && (
                <p className="panel-foot">{report.pending_rates} számla árfolyama még hiányzik, ezek nincsenek az összesítésben.</p>
              )}
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>Cégenkénti összesítő</h2>
                <span className="panel-note">bruttó HUF</span>
              </div>
              <PartnerTable partners={report.partners} />
            </section>

            <section className="panel">
              <InvoiceTable
                initial={initialInvoices}
                version={version}
                totalCount={report.invoice_count}
                months={report.months.map((m) => m.month)}
                currencies={report.currencies}
              />
            </section>
          </>
        )}

        {report && report.failed_uploads.length > 0 && (
          <section className="panel">
            <div className="panel-head"><h2>Fel nem dolgozható fájlok</h2></div>
            <div className="scroll">
              <table className="table">
                <thead><tr><th>Fájl</th><th>Hiba</th><th>Időpont</th></tr></thead>
                <tbody>
                  {report.failed_uploads.map((u, i) => (
                    <tr key={`${u.filename}-${i}`}><td>{u.filename}</td><td>{u.message}</td><td className="date">{u.created_at}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
