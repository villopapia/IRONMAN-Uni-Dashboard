import { useState } from "react";
import { TrendingUp } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { ink, LOAD_COLORS } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatTile from "@/components/ui/StatTile";
import { ChartTable, gridProps, legendProps, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const RANGES = [
  { days: 90, label: "90d" },
  { days: 180, label: "6m" },
  { days: 365, label: "1y" },
];

export default function TrainingLoadChart() {
  const [days, setDays] = useState(180);
  const { data, error } = usePolling(() => api.getPmc(days), [days]);

  const series = data?.series ?? [];
  const cur = data?.current;

  return (
    <Card
      icon={TrendingUp}
      title="Fitness, fatigue & form"
      meta={
        <span className="inline-flex rounded-md bg-white/[0.04] p-0.5 text-xs">
          {RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              className={`rounded px-2 py-0.5 ${days === r.days ? "bg-white/[0.1] text-white" : "text-neutral-500 hover:text-neutral-300"}`}
            >
              {r.label}
            </button>
          ))}
        </span>
      }
      className="lg:col-span-2"
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-1/2" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {data && cur && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Fitness (CTL, 42d)" value={cur.ctl.toFixed(1)} />
            <StatTile label="Fatigue (ATL, 7d)" value={cur.atl.toFixed(1)} />
            <StatTile label="Form (TSB)" value={`${cur.tsb > 0 ? "+" : ""}${cur.tsb.toFixed(1)}`} />
            <StatTile
              label="CTL ramp, last 7d"
              value={data.ctl_ramp_7d != null ? `${data.ctl_ramp_7d > 0 ? "+" : ""}${data.ctl_ramp_7d}` : null}
            />
          </div>

          {/* Small multiples sharing the x-axis: the daily-load spikes (single
              sessions up to ~300) would otherwise set the y-scale and flatten
              the CTL/ATL/TSB lines, which are what this chart is for. */}
          <div className="mt-4 h-60">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} syncId="pmc" margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} hide />
                <YAxis {...yAxisProps} />
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number, name: string) => [v.toFixed(1), name]}
                />
                <Legend {...legendProps} verticalAlign="top" height={28} />
                <ReferenceLine y={0} stroke={ink.baseline} />
                <Line type="monotone" dataKey="ctl" name="Fitness (CTL)" stroke={LOAD_COLORS.ctl} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="atl" name="Fatigue (ATL)" stroke={LOAD_COLORS.atl} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="tsb" name="Form (TSB)" stroke={LOAD_COLORS.tsb} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="text-[11px] text-neutral-500">Daily load</div>
          <div className="h-24">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} syncId="pmc" margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} />
                <YAxis {...yAxisProps} tickCount={3} />
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number) => [v.toFixed(0), "Daily load"]}
                />
                <Bar dataKey="load" name="Daily load" fill={ink.muted} maxBarSize={6} radius={[2, 2, 0, 0]} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <p className="mt-2 text-xs leading-relaxed text-neutral-500">
            {data.methodology_note}
            {data.estimated_sessions > 0 &&
              ` ${data.estimated_sessions} of ${data.total_sessions} sessions use the estimated fallback.`}
            {data.first_load_date &&
              ` History starts ${new Date(data.first_load_date + "T00:00:00").toLocaleDateString(undefined, {
                day: "numeric",
                month: "short",
                year: "numeric",
              })} (CTL starts from 0 there, so the first ~6 weeks read low).`}
          </p>

          <ChartTable
            columns={["Date", "Load", "CTL", "ATL", "TSB"]}
            rows={[...series]
              .reverse()
              .filter((p) => p.load > 0)
              .map((p) => [fmtShortDate(p.date), p.load.toFixed(0), p.ctl.toFixed(1), p.atl.toFixed(1), p.tsb.toFixed(1)])}
            summary="Show training days as table"
          />
        </>
      )}

      {data && !cur && <p className="text-sm text-neutral-500">No activities synced yet.</p>}
    </Card>
  );
}
