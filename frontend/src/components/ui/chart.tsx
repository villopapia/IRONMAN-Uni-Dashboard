import { ReactNode } from "react";
import { ink, surface } from "@/lib/palette";

// Shared Recharts chrome so every chart reads as one system: solid hairline
// grid (never dashed), recessive axes, text in ink tokens only.
export const gridProps = { stroke: ink.gridline, vertical: false } as const;

export const xAxisProps = {
  stroke: ink.muted,
  tickLine: false,
  axisLine: { stroke: ink.baseline },
  tick: { fill: ink.secondary, fontSize: 11 },
} as const;

export const yAxisProps = {
  stroke: ink.muted,
  tickLine: false,
  axisLine: false,
  tick: { fill: ink.muted, fontSize: 11 },
  width: 40,
} as const;

export const tooltipProps = {
  contentStyle: {
    background: surface.cardHover,
    border: `1px solid ${ink.gridline}`,
    borderRadius: 8,
    fontSize: 12,
  },
  labelStyle: { color: ink.primary, marginBottom: 4 },
  itemStyle: { color: ink.secondary, padding: 0 },
  cursor: { fill: "rgba(255,255,255,0.04)", stroke: ink.baseline },
} as const;

export const legendProps = {
  wrapperStyle: { fontSize: 12, color: ink.secondary },
  iconSize: 10,
  // Recharts colors legend text with the series color by default - text
  // stays in ink tokens; the swatch beside it carries identity.
  formatter: (value: string) => <span style={{ color: ink.secondary }}>{value}</span>,
};

/** Legend chip for hand-built legends: colored mark + ink-colored text. */
export function LegendChip({ color, label, line = false }: { color: string; label: string; line?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-neutral-400">
      <span
        className={line ? "h-0.5 w-3.5 rounded" : "h-2 w-2 rounded-full"}
        style={{ background: color }}
      />
      {label}
    </span>
  );
}

/** Table-view twin for a chart - every value stays reachable without hover. */
export function ChartTable({
  columns,
  rows,
  summary = "Show as table",
}: {
  columns: string[];
  rows: ReactNode[][];
  summary?: string;
}) {
  return (
    <details className="mt-3 text-xs">
      <summary className="cursor-pointer select-none text-neutral-500 hover:text-neutral-300">
        {summary}
      </summary>
      <div className="mt-2 max-h-64 overflow-auto">
        <table className="w-full text-left tabular-nums">
          <thead className="sticky top-0 bg-[#1a1a19] text-neutral-500">
            <tr>
              {columns.map((c) => (
                <th key={c} className="py-1 pr-3 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-neutral-300">
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-white/[0.04]">
                {r.map((cell, j) => (
                  <td key={j} className="py-1 pr-3">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
