import { useState } from "react";
import { Activity as Pulse } from "lucide-react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, RecoveryMetricTrend, RecoveryTrendPoint } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { ink, surface } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";
import { gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const META = {
  hrv: { title: "HRV (overnight avg)", daily: "hrv", rolling: "hrv_7d", badDir: "below" },
  rhr: { title: "Resting HR", daily: "rhr", rolling: "rhr_7d", badDir: "above" },
} as const;

const METHOD_LABEL: Record<string, string> = {
  manual: "your saved value",
  snapshot_28d: "saved snapshot",
  auto_28d: "auto, days 8–35 back",
  insufficient_history: "not enough history yet",
};

function flagBadge(m: RecoveryMetricTrend): [BadgeTone, string] {
  if (m.flag === "normal") return ["good", "Within normal range"];
  if (m.flag === "below_normal") return ["warning", "Below normal range"];
  if (m.flag === "above_normal") return ["warning", "Above normal range"];
  return ["neutral", "Building baseline"];
}

function MetricPanel({
  metric,
  trend,
  series,
  onChanged,
}: {
  metric: "hrv" | "rhr";
  trend: RecoveryMetricTrend;
  series: RecoveryTrendPoint[];
  onChanged: () => void;
}) {
  const meta = META[metric];
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const base = trend.baseline;
  const [tone, label] = flagBadge(trend);
  const hasData = series.some((p) => p[meta.daily] != null);
  const latest = [...series].reverse().find((p) => p[meta.daily] != null)?.[meta.daily] ?? null;

  const act = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try {
      await fn();
      setEditing(false);
      setVal("");
      onChanged();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <div className="rounded-xl bg-white/[0.02] p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-neutral-200">{meta.title}</div>
          <div className="mt-0.5 text-2xl font-semibold text-white">
            {trend.rolling_7d != null ? (
              <>
                {trend.rolling_7d} {trend.unit}
                <span className="ml-1.5 text-xs font-normal text-neutral-500">7-day avg</span>
              </>
            ) : latest != null ? (
              <>
                {latest} {trend.unit}
                <span className="ml-1.5 text-xs font-normal text-neutral-500">latest · 7-day avg needs 3+ readings</span>
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="text-xs text-neutral-400">
            Baseline {base.value != null ? `${base.value} ${trend.unit}` : "—"}
            {base.sd != null && ` ± ${base.sd}`} · {METHOD_LABEL[base.method]}
            {trend.deviation_pct != null && ` · ${trend.deviation_pct > 0 ? "+" : ""}${trend.deviation_pct}%`}
          </div>
        </div>
        <StatusBadge tone={tone} label={label} compact />
      </div>

      {hasData ? (
        <div className="mt-2 h-32">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={series} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
              <CartesianGrid {...gridProps} />
              {base.value != null && base.sd != null && (
                <ReferenceArea y1={base.value - base.sd} y2={base.value + base.sd} fill="rgba(255,255,255,0.05)" ifOverflow="extendDomain" />
              )}
              {base.value != null && <ReferenceLine y={base.value} stroke={ink.muted} ifOverflow="extendDomain" />}
              <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={30} />
              <YAxis {...yAxisProps} domain={["dataMin - 3", "dataMax + 3"]} allowDecimals={false} />
              <Tooltip {...tooltipProps} labelFormatter={(d: string) => fmtShortDate(d)} />
              <Line
                dataKey={meta.daily}
                name="Daily"
                stroke="transparent"
                dot={{ r: 3, fill: ink.muted, stroke: surface.card, strokeWidth: 1 }}
                isAnimationActive={false}
                connectNulls={false}
              />
              <Line dataKey={meta.rolling} name="7-day avg" stroke={ink.secondary} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="mt-2 flex h-32 items-center justify-center rounded-lg border border-dashed border-white/[0.06] text-xs text-neutral-500">
          No readings in this window
        </div>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-3">
        <LegendChip color={ink.muted} label="Daily" />
        <LegendChip color={ink.secondary} label="7-day avg" line />
        <LegendChip color="rgba(255,255,255,0.25)" label="Baseline ± 1 SD" />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-neutral-500">
        {trend.readings < 14 && trend.first_reading && (
          <span>
            Readings since {fmtShortDate(trend.first_reading)} ({trend.readings}) — baseline needs 14+ in its window.
          </span>
        )}
        {base.method === "auto_28d" && (
          <button className="hover:text-neutral-200" onClick={() => act(() => api.setRecoveryBaseline(metric))}>
            Save current as baseline
          </button>
        )}
        {!editing && (
          <button className="hover:text-neutral-200" onClick={() => setEditing(true)}>
            Set baseline…
          </button>
        )}
        {(base.method === "manual" || base.method === "snapshot_28d") && (
          <button className="hover:text-neutral-200" onClick={() => act(() => api.clearRecoveryBaseline(metric))}>
            Reset to automatic
          </button>
        )}
      </div>
      {editing && (
        <div className="mt-1.5 flex items-center gap-1.5">
          <input
            className="w-20 rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-xs text-white"
            placeholder={trend.unit}
            value={val}
            onChange={(e) => setVal(e.target.value)}
          />
          <button
            className="rounded-md bg-white/[0.08] px-2 py-0.5 text-[11px] text-neutral-200"
            onClick={() => {
              const n = Number(val);
              if (!n || n <= 0) return setErr("Enter a number.");
              act(() => api.setRecoveryBaseline(metric, n));
            }}
          >
            Save
          </button>
          <button className="text-[11px] text-neutral-500" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      )}
      {err && <p className="mt-1 text-xs text-red-400">{err}</p>}
    </div>
  );
}

export default function RecoveryTrend() {
  const { data, error, reload } = usePolling(() => api.getRecoveryTrend(42));

  return (
    <Card icon={Pulse} title="HRV & resting HR trend" meta="7-day rolling vs baseline">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && (
        <div className="space-y-3">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}
      {data && (
        <>
          <div className="space-y-3">
            <MetricPanel metric="hrv" trend={data.metrics.hrv} series={data.series} onChanged={reload} />
            <MetricPanel metric="rhr" trend={data.metrics.rhr} series={data.series} onChanged={reload} />
          </div>
          <p className="mt-3 text-xs leading-relaxed text-neutral-500">
            Flags when the 7-day average leaves baseline ± 1 SD in the unhelpful direction (HRV down, RHR up) —
            a heuristic, not a diagnosis. HRV history on Garmin only starts 22 Sep 2026, so its baseline needs a few
            weeks to form.
          </p>
        </>
      )}
    </Card>
  );
}
