import { Gauge } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Intensity } from "@/lib/api";
import { fmtShortDate, fmtWeekRange } from "@/lib/format";
import { INTENSITY_COLORS, SPORT_COLORS, surface } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import { ChartTable, gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const BANDS = [
  { key: "low", label: "Low (Z1-Z2)", color: INTENSITY_COLORS.low },
  { key: "mid", label: "Mid (Z3-Z4)", color: INTENSITY_COLORS.mid },
  { key: "high", label: "High (Z5+)", color: INTENSITY_COLORS.high },
] as const;
const SPORTS = ["bike", "run"] as const;

const pct = (v: number | undefined) => (v == null ? "—" : `${Math.round(v)}%`);

// One chart per sport (small multiples) rather than 16 bars on one axis.
function SportChart({ sport, weeks }: { sport: (typeof SPORTS)[number]; weeks: Intensity["weeks"] }) {
  const rows = weeks.map((w) => ({ week: w.week_start, ...(w[sport] ?? {}) }));
  return (
    <div>
      <div className="mb-1 flex items-center gap-2 text-xs font-medium capitalize text-neutral-300">
        <span className="h-2 w-2 rounded-full" style={{ background: SPORT_COLORS[sport] }} />
        {sport}
      </div>
      <div className="h-36">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="week" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={24} />
            <YAxis {...yAxisProps} domain={[0, 100]} ticks={[0, 50, 100]} unit="%" />
            <Tooltip
              {...tooltipProps}
              labelFormatter={(d: string) => fmtWeekRange(d)}
              formatter={(v: number, name: string) => [`${Math.round(v)}%`, name]}
            />
            {BANDS.map((b) => (
              <Bar key={b.key} dataKey={b.key} name={b.label} stackId="z" fill={b.color} stroke={surface.card} strokeWidth={1} maxBarSize={22} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function IntensityDistribution() {
  const { data, error } = usePolling(() => api.getIntensity());
  const weeks = data?.weeks ?? [];
  const agg = data?.aggregate;

  return (
    <Card icon={Gauge} title="Intensity distribution" meta="last 8 weeks, % of HR-zone time">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-48 w-full" />}

      {data && (
        <>
          <p className="text-sm text-neutral-200">
            8-week low share: <span className="text-lg font-semibold tabular-nums text-white">{pct(agg?.all?.low)}</span>
            <span className="text-neutral-400">
              {" "}
              (bike {pct(agg?.bike?.low)}, run {pct(agg?.run?.low)})
            </span>
          </p>
          <p className="text-xs text-neutral-500">{data.target_note}</p>

          <div className="mb-2 mt-3 flex flex-wrap items-center gap-3">
            {BANDS.map((b) => (
              <LegendChip key={b.key} color={b.color} label={b.label} />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {SPORTS.map((s) => (
              <SportChart key={s} sport={s} weeks={weeks} />
            ))}
          </div>

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">{(data.caveats ?? []).join(". ")}.</p>

          <ChartTable
            columns={["Week", "Bike low / mid / high", "Run low / mid / high"]}
            rows={[...weeks].reverse().map((w) => [
              fmtWeekRange(w.week_start),
              ...SPORTS.map((s) => (w[s] ? `${pct(w[s]!.low)} / ${pct(w[s]!.mid)} / ${pct(w[s]!.high)}` : "—")),
            ])}
          />
        </>
      )}
    </Card>
  );
}
