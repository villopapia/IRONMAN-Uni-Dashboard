import { useState } from "react";
import { TrendingUp } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { ink, LOAD_COLORS, SPORT_COLORS, status } from "@/lib/palette";
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

// Form bands as TrainingPeaks defines them (for its TSS scale; Relative Effort
// is a different scale, so treat them as a guide, not a verdict).
const FORM_ZONES = [
  { from: 5, to: 200, label: "Fresh (> +5)", color: status.good, alpha: "1f" },
  { from: -10, to: 5, label: "Neutral", color: ink.muted, alpha: "14" },
  { from: -30, to: -10, label: "Productive (−10 to −30)", color: LOAD_COLORS.tsb, alpha: "1f" },
  { from: -200, to: -30, label: "Overreaching (< −30)", color: status.critical, alpha: "29" },
];

function formNote(tsb: number, ramp: number | null): string {
  const t = `${tsb > 0 ? "+" : ""}${tsb.toFixed(0)}`;
  const form =
    tsb > 5
      ? `Form ${t}: fresh — good for a race or a test, but you're not building much fitness.`
      : tsb > -10
        ? `Form ${t}: balanced — neither fatigued nor fresh.`
        : tsb >= -30
          ? `Form ${t}: carrying fatigue, which is the normal zone while building. Fine as long as you recover between sessions.`
          : `Form ${t}: heavy fatigue — higher injury and illness risk; take lighter days.`;
  if (ramp == null) return form;
  const r = ramp > 8 ? "Fitness is rising very fast (about +8 a week is the most usually sustainable)." : ramp >= 3 ? "Fitness is building at a solid pace." : ramp >= 0 ? "Fitness is rising slowly." : "Fitness is falling.";
  return `${form} ${r}`;
}

// Same margins on all three charts so syncId lines the days up; the right
// margin leaves room for the last date label, which was being clipped.
const MARGIN = { top: 4, right: 20, left: -8, bottom: 0 };

export default function TrainingLoadChart() {
  const [days, setDays] = useState(180);
  const { data, error } = usePolling(() => api.getPmc(days), [days]);

  // Flatten per-sport load into columns (undefined when absent so the tooltip
  // only lists sports trained that day).
  const series = (data?.series ?? []).map((p) => ({ ...p, ...p.by_sport }));
  const cur = data?.current;
  const SPORTS = ["swim", "bike", "run", "gym", "walk", "other"];
  const tsbMin = Math.min(-35, ...series.map((p) => p.tsb));
  const tsbMax = Math.max(15, ...series.map((p) => p.tsb));

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
          <p className="mt-3 text-sm text-neutral-200">{formNote(cur.tsb, data.ctl_ramp_7d)}</p>

          {/* Small multiples sharing the x-axis: daily-load spikes (single
              sessions up to ~300) would otherwise set the y-scale and flatten
              the fitness/fatigue lines, and form (which swings around 0) needs
              its own scale and zones. */}
          <div className="mt-4 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} syncId="pmc" margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} hide />
                <YAxis {...yAxisProps} domain={[0, (m: number) => Math.ceil(m / 20) * 20]} tickCount={5} />
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number, name: string) => [v.toFixed(1), name]}
                />
                <Legend {...legendProps} verticalAlign="top" height={28} />
                <Line type="monotone" dataKey="ctl" name="Fitness (CTL)" stroke={LOAD_COLORS.ctl} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="atl" name="Fatigue (ATL)" stroke={LOAD_COLORS.atl} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-neutral-500">
            <span className="font-medium text-neutral-300">Form (TSB)</span>
            {FORM_ZONES.map((z) => (
              <span key={z.label} className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-sm" style={{ background: `${z.color}80` }} />
                {z.label}
              </span>
            ))}
          </div>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} syncId="pmc" margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} hide />
                <YAxis {...yAxisProps} domain={[Math.floor(tsbMin / 10) * 10, Math.ceil(tsbMax / 10) * 10]} tickCount={5} />
                {FORM_ZONES.map((z) => (
                  <ReferenceArea key={z.label} y1={z.from} y2={z.to} fill={`${z.color}${z.alpha}`} ifOverflow="hidden" />
                ))}
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number) => [v.toFixed(1), "Form (TSB)"]}
                />
                <ReferenceLine y={0} stroke={ink.baseline} />
                <Line type="monotone" dataKey="tsb" name="Form (TSB)" stroke={LOAD_COLORS.tsb} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-1 text-[11px] text-neutral-500">Daily load, by sport</div>
          <div className="h-24">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} syncId="pmc" margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} />
                <YAxis {...yAxisProps} tickCount={3} />
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number, name: string) => [v.toFixed(0), name]}
                />
                {SPORTS.map((s, i) => (
                  <Bar
                    key={s}
                    dataKey={s}
                    name={s[0].toUpperCase() + s.slice(1)}
                    stackId="d"
                    fill={SPORT_COLORS[s]}
                    maxBarSize={6}
                    radius={i === SPORTS.length - 1 ? [2, 2, 0, 0] : 0}
                    isAnimationActive={false}
                  />
                ))}
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
