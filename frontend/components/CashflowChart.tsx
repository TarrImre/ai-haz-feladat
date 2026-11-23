"use client";

import { CategoryScale, Chart as ChartJS, Filler, LinearScale, LineElement, PointElement, Tooltip } from "chart.js";
import { Line } from "react-chartjs-2";
import { publicSans } from "@/lib/fonts";
import { formatHuf, hufFmt } from "@/lib/format";
import type { MonthRow } from "@/lib/types";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip);

const IN = "#d9480f";
const OUT = "#2b6cb0";
const MUTED = "#66707c";
const font = { family: publicSans.style.fontFamily, size: 11 };

const millions = (v: number): string => (v === 0 ? "0" : `${hufFmt.format(v / 1e6)} M`);

export default function CashflowChart({ months }: { months: MonthRow[] }) {
  return (
    <div className="chart-box">
      <Line
        aria-label="Havi bejövő és kimenő bruttó összeg forintban"
        role="img"
        data={{
          labels: months.map((m) => m.month),
          datasets: [
            { label: "Bejövő", data: months.map((m) => m.incoming), borderColor: IN, backgroundColor: IN, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4 },
            { label: "Kimenő", data: months.map((m) => m.outgoing), borderColor: OUT, backgroundColor: "rgba(43,108,176,.08)", fill: true, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4 },
          ],
        }}
        options={{
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            tooltip: { titleFont: font, bodyFont: font, callbacks: { label: (c) => `${c.dataset.label}: ${formatHuf(c.parsed.y ?? 0)}` } },
          },
          scales: {
            x: {
              grid: { display: false },
              border: { color: "#d6dade" },
              ticks: { color: MUTED, font },
              title: { display: true, text: "Fizetési határidő (hónap)", color: MUTED, font },
            },
            y: {
              beginAtZero: true,
              grid: { color: "#eceef0" },
              border: { display: false },
              ticks: { color: MUTED, font, callback: (v) => millions(Number(v)) },
              title: { display: true, text: "Bruttó összeg (millió Ft)", color: MUTED, font },
            },
          },
        }}
      />
    </div>
  );
}
