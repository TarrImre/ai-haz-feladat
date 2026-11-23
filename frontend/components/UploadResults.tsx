import Badge from "./Badge";
import { STATUS_LABEL } from "@/lib/format";
import type { FileResult } from "@/lib/types";

function ResultTable({ rows }: { rows: FileResult[] }) {
  return (
    <div className="scroll">
      <table className="table">
        <thead><tr><th>Fájl</th><th>Állapot</th><th>Számlaszám</th><th>Megjegyzés</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.filename}-${i}`}>
              <td>{r.filename}</td>
              <td><Badge kind={r.status}>{STATUS_LABEL[r.status]}</Badge></td>
              <td>{r.invoice_no ?? ""}</td>
              <td>{r.message ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function UploadResults({ results, onClose }: { results: FileResult[]; onClose: () => void }) {
  const problems = results.filter((r) => r.status === "hiba" || r.status === "figyelmeztetes");
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Utolsó feltöltés: {results.length} fájl</h2>
        <button className="btn" onClick={onClose}>Bezárás</button>
      </div>
      {problems.length > 0 ? <ResultTable rows={problems} /> : <p className="panel-foot">Minden fájl feldolgozva, hiba és figyelmeztetés nélkül.</p>}
      <details>
        <summary>Minden fájl eredménye ({results.length})</summary>
        <ResultTable rows={results} />
      </details>
    </section>
  );
}
