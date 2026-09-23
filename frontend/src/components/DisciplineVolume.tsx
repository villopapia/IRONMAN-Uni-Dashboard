import { useState } from "react";
import { BarChart3 } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { fmtWeekRange } from "@/lib/format";
import { SPORT_COLORS, surface } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import { ChartTable, gridProps, legendProps, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const SPORTS = [
  { key: "swim", label: "Swim" },
  { key: "bike", label: "Bike" },
  { key: "run", label: "Run" },
  { key: "gym", label: "Strength" },
] as const;

type Metric = "hours" | "load" | "distance";

// Strength has no meaningful distance - excluded from the stacked bar in
// distance mode rather than always showing a pointless 0km segment.
const SPORTS_BY_METRIC: Record<Metric, typeof SPORTS[number][]> = {
  hours: [...SPORTS],
  load: [...SPORTS],
  distance: SPORTS.filter((s) => s.key !== "gym"),
};

export default function DisciplineVolume() {
  const { data, error } = usePolling(() => api.getDisciplineWeeks(12));
  const [metric, setMetric] = useState<Metric>("hours");
  const sports = SPORTS_BY_METRIC[metric];

  const chartData =
    data?.map((w) => {
      const row: Record<string, string | number> = { week: fmtWeekRange(w.week_start) };
      for (const s of sports) {
        const v = w.sports[s.key];
        row[s.key] =
          metric === "hours"
            ? Math.round((v.minutes / 60) * 10) / 10
            : metric === "distance"
              ? Math.round(v.distance_km * 10) / 10
              : Math.round(v.load);
      }
      return row;
    }) ?? [];

  return (
    <Card
      icon={BarChart3}
      title="Weekly volume by discipline"
      meta={
        <span className="inline-flex rounded-md bg-white/[0.04] p-0.5 text-xs">
          {(["hours", "load", "distance"] as Metric[]).map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className={`rounded px-2 py-0.5 ${metric === m ? "bg-white/[0.1] text-white" : "text-neutral-500 hover:text-neutral-300"}`}
            >
              {m === "hours" ? "Hours" : m === "load" ? "Load" : "Distance"}
            </button>
          ))}
        </span>
      }
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {!data && !error && <Skeleton className="h-60 w-full" />}

      {data && (
        <>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="week" {...xAxisProps} interval="preserveStartEnd" />
                <YAxis {...yAxisProps} unit={metric === "hours" ? "h" : metric === "distance" ? "km" : ""} />
                <Tooltip
                  {...tooltipProps}
                  formatter={(v: number) => (metric === "hours" ? `${v} h` : metric === "distance" ? `${v} km` : v)}
                />
                <Legend {...legendProps} />
                {sports.map((s, i) => (
                  <Bar
                    key={s.key}
                    dataKey={s.key}
                    name={s.label}
                    stackId="v"
                    fill={SPORT_COLORS[s.key]}
                    // 2px surface-colored gap between stacked segments; only the top segment gets the rounded data-end.
                    stroke={surface.card}
                    strokeWidth={2}
                    maxBarSize={22}
                    isAnimationActive={false}
                    radius={i === sports.length - 1 ? [4, 4, 0, 0] : 0}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-neutral-500">
            {metric === "hours"
              ? "Moving time per week, Mon–Sun, from Strava."
              : metric === "distance"
                ? "Moving distance per week, Mon–Sun, from Strava. Strength has no meaningful distance and is left out of this view."
                : "Weekly sum of Strava Relative Effort — the same load unit as the fitness/fatigue chart."}{" "}
            Walks and other activities are left out.
          </p>
          <ChartTable
            columns={["Week", ...SPORTS.map((s) => `${s.label} (min · n)`)]}
            rows={[...data].reverse().map((w) => [
              fmtWeekRange(w.week_start),
              ...SPORTS.map((s) => `${Math.round(w.sports[s.key].minutes)} · ${w.sports[s.key].sessions}`),
            ])}
          />
        </>
      )}
    </Card>
  );
}
