import { ShieldAlert } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, FlagStatus, RampWeek } from "@/lib/api";
import { fmtShortDate, fmtSignedPct, fmtWeekRange } from "@/lib/format";
import { SPORT_COLORS } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";
import { ChartTable, gridProps, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const STATUS: Record<FlagStatus, [BadgeTone, string]> = {
  pass: ["good", "PASS"],
  amber: ["warning", "AMBER"],
  red: ["critical", "RED"],
  no_data: ["neutral", "NO DATA"],
};

// The week in progress has no status and no change: only completed weeks are judged.
const badge = (w: RampWeek): [BadgeTone, string] | null => (w.status === "in_progress" ? null : (STATUS[w.status] ?? STATUS.no_data));
const change = (w: RampWeek) =>
  w.status === "in_progress" ? "in progress" : w.change_pct != null ? fmtSignedPct(w.change_pct) : "no comparison";

export default function RunGuard() {
  const { data, error } = usePolling(() => api.getRunRamp());
  const weeks = data?.weeks ?? [];
  const current = weeks[weeks.length - 1];
  const last = weeks[weeks.length - 2];
  const lastBadge = last ? badge(last) : null;
  const flagged = weeks.filter((w) => w.status === "amber" || w.status === "red");

  return (
    <Card icon={ShieldAlert} title="Run guard" meta="weekly run km, last 8 weeks">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-40 w-full" />}

      {data && current && (
        <>
          <p className="text-sm text-neutral-200">
            <span className="text-lg font-semibold tabular-nums text-white">{current.km} km</span> so far
            {last && <span className="text-neutral-400"> (last week {last.km} km)</span>}
          </p>
          {last && lastBadge && (
            <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-400">
              Last completed week: {change(last)} vs {last.baseline_km} km average
              <StatusBadge tone={lastBadge[0]} label={lastBadge[1]} compact />
            </p>
          )}

          <div className="mt-3 h-36">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeks} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="week_start" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={24} />
                <YAxis {...yAxisProps} unit=" km" width={52} />
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtWeekRange(d)}
                  formatter={(v: number, _n: string, item: { payload?: RampWeek }) => [
                    `${v} km${item.payload ? ` (${change(item.payload)})` : ""}`,
                    "Run",
                  ]}
                />
                <Bar dataKey="km" name="Run km" fill={SPORT_COLORS.run} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {flagged.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-neutral-300">
              {flagged.map((w) => (
                <li key={w.week_start} className="flex items-center justify-between gap-2">
                  <span>
                    {fmtWeekRange(w.week_start)}: {w.km} km, {change(w)}
                  </span>
                  <StatusBadge tone={badge(w)?.[0] ?? "neutral"} label={badge(w)?.[1] ?? "NO DATA"} compact />
                </li>
              ))}
            </ul>
          )}

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">
            Each completed week vs average of the previous {data.baseline_weeks} weeks: AMBER above +{data.amber_above_pct}%, RED
            above +{data.red_above_pct}%. No comparison when that average is under {data.min_baseline_km} km. The week in progress
            is not judged.
          </p>

          <ChartTable
            columns={["Week", "Run km", "4-week average", "Change", "Status"]}
            rows={[...weeks].reverse().map((w) => [fmtWeekRange(w.week_start), w.km, w.baseline_km, change(w), badge(w)?.[1] ?? "—"])}
          />
        </>
      )}
    </Card>
  );
}
