"use client";

import { useState } from "react";
import Badge from "./Badge";
import { networkInvoices } from "@/network/network.invoices";
import { STATUS_LABEL } from "@/lib/format";
import type { FileResult, UploadStatus } from "@/lib/types";

const CHUNK = 10;
const ORDER: Record<UploadStatus, number> = { hiba: 0, figyelmeztetes: 1, duplikalt: 2, ok: 3 };

export default function UploadPanel({ onUploaded }: { onUploaded: (results: FileResult[]) => Promise<void> }) {
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [results, setResults] = useState<FileResult[]>([]);

  async function upload(list: FileList | null) {
    const files = [...(list ?? [])].filter((f) => f.size > 0);
    if (!files.length || busy) return;
    setBusy(true);
    setResults([]);
    const all: FileResult[] = [];
    for (let i = 0; i < files.length; i += CHUNK) {
      setProgress({ done: i, total: files.length });
      const part = files.slice(i, i + CHUNK);
      try {
        const { data } = await networkInvoices.upload(part);
        all.push(...data.results);
      } catch (err) {
        part.forEach((f) => all.push({ filename: f.name, status: "hiba", message: `Feltöltési hiba: ${(err as Error).message}` }));
        // Az első hibás adag után leáll, így egy értesítés jön, nem adagonként egy.
        files.slice(i + CHUNK).forEach((f) => all.push({ filename: f.name, status: "hiba", message: "Nem lett feltöltve, egy korábbi adag hibája miatt." }));
        break;
      }
    }
    setProgress({ done: files.length, total: files.length });
    all.sort((a, b) => ORDER[a.status] - ORDER[b.status]);
    setResults(all);
    setBusy(false);
    await onUploaded(all);
  }

  const counts = results.reduce<Partial<Record<UploadStatus, number>>>((acc, r) => ({ ...acc, [r.status]: (acc[r.status] ?? 0) + 1 }), {});

  return (
    <div>
      <label
        className={`dropzone${over ? " over" : ""}${busy ? " busy" : ""}`}
        onDragEnter={(e) => { e.preventDefault(); setOver(true); }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); void upload(e.dataTransfer.files); }}
      >
        <input
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          disabled={busy}
          onChange={(e) => { void upload(e.target.files); e.target.value = ""; }}
        />
        <b>{busy ? "Feldolgozás folyamatban…" : "PDF-ek feltöltése"}</b>
        <span>húzd ide vagy kattints, akár a teljes csomagot</span>
      </label>

      {progress && (
        <div className="progress">
          <div className="progress-bar"><span style={{ width: `${(progress.done / progress.total) * 100}%` }} /></div>
          {progress.done} / {progress.total} fájl feldolgozva
        </div>
      )}

      {results.length > 0 && (
        <div className="counts">
          {(Object.keys(STATUS_LABEL) as UploadStatus[]).filter((k) => counts[k]).map((k) => (
            <Badge key={k} kind={k}>{STATUS_LABEL[k]}: {counts[k]}</Badge>
          ))}
        </div>
      )}
    </div>
  );
}
