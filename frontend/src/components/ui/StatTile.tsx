import { ReactNode } from "react";
import { ink } from "@/lib/palette";

interface StatTileProps {
  label: string;
  value: string | null;
  sub?: string | null;
  accent?: string;
  /** Status badge beside the value, so a colored value is never the only signal. */
  badge?: ReactNode;
  /** Recent values, oldest first, drawn as a small trend line under the value. */
  spark?: number[];
  sparkColor?: string;
}

const SPARK_W = 100;
const SPARK_H = 22;

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const points = values
    .map((v, i) => `${((i / (values.length - 1)) * SPARK_W).toFixed(1)},${(SPARK_H - 2 - ((v - min) / span) * (SPARK_H - 4)).toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} preserveAspectRatio="none" className="mt-1 h-[22px] w-full max-w-[9rem]" aria-hidden="true">
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function StatTile({ label, value, sub, accent, badge, spark, sparkColor }: StatTileProps) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-neutral-500">{label}</div>
      <div className="mt-0.5 flex flex-wrap items-center gap-2">
        <span className="break-words text-xl font-semibold text-white" style={accent ? { color: accent } : undefined}>
          {value ?? "—"}
        </span>
        {badge}
      </div>
      {sub && <div className="text-xs text-neutral-500">{sub}</div>}
      {spark && spark.length > 1 && <Sparkline values={spark} color={sparkColor ?? ink.secondary} />}
    </div>
  );
}
