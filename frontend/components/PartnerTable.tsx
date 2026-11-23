import { hufFmt } from "@/lib/format";
import type { PartnerColumn } from "@/lib/types";

const ROWS = [
  { key: "incoming", label: "Össz bejövő", cls: "in" },
  { key: "outgoing", label: "Össz kimenő", cls: "out" },
] as const;

export default function PartnerTable({ partners }: { partners: PartnerColumn[] }) {
  return (
    <div className="scroll">
      <table className="table pivot">
        <thead>
          <tr>
            <th />
            {partners.map((p) => (
              <th key={p.name} title={`${p.tax_ids.join(", ")}${p.names.length > 1 ? `\nÍrásmódok: ${p.names.join(" | ")}` : ""}`}>
                {p.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.key} className={row.cls}>
              <td>{row.label}</td>
              {partners.map((p) => (
                <td key={p.name} className={`num${p[row.key] ? "" : " zero"}`}>{hufFmt.format(p[row.key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
