import { Activity } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { SPORT_COLORS } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import { ChartTable, gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const SPORTS = ["swim", "bike", "run"] as const;
const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

export default function SportFitness() {
  const { data, error } = usePolling(() => api.getSportCtl(180));
  const series = data?.series ?? [];
  const latest = series[series.length - 1];

  return (
    <Card icon={Activity} title="Fitness by sport" meta="CTL per sport, 6 months">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-56 w-full" />}
      {data && !latest && <p className="text-sm text-neutral-500">No intervals.icu activities cached yet.</p>}

      {data && latest && (
        <>
          <div className="mb-2 flex flex-wrap items-center gap-4">
            {SPORTS.map((s) => (
              <span key={s} className="inline-flex items-center gap-1.5">
                <LegendChip color={SPORT_COLORS[s]} label={cap(s)} line />
                <span className="text-sm font-semibold tabular-nums text-white">{latest[s].toFixed(1)}</span>
              </span>
            ))}
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} />
                <YAxis {...yAxisProps} domain={[0, (m: number) => Math.ceil(m / 5) * 5]} />
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number, name: string) => [v.toFixed(1), name]}
                />
                {SPORTS.map((s) => (
                  <Line key={s} type="monotone" dataKey={s} name={cap(s)} stroke={SPORT_COLORS[s]} strokeWidth={2} dot={false} isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <p className="mt-2 text-xs leading-relaxed text-neutral-500">
            42-day fitness (CTL) per sport from intervals.icu training load, same decay as intervals.icu.
            {data.starts_on && ` Each line starts from 0 on ${fmtShortDate(data.starts_on)}, so the first six weeks read low.`}
            {data.check &&
              ` Swim + bike + run is within ${data.check.max_deviation_pct}% of intervals.icu's own CTL over the last ${data.check.days} days (gym and walk load are not included).`}
          </p>

          <ChartTable
            columns={["Week ending", "Swim", "Bike", "Run"]}
            rows={[...series]
              .reverse()
              .filter((_, i) => i % 7 === 0)
              .map((p) => [fmtShortDate(p.date), ...SPORTS.map((s) => p[s].toFixed(1))])}
            summary="Show weekly values as table"
          />
        </>
      )}
    </Card>
  );
}
