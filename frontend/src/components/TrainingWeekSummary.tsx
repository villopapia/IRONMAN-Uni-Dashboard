import { useEffect, useState } from "react";
import { Activity, TrendingDown, TrendingUp } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, WeekSchedule, WeekSummary } from "@/lib/api";
import { mostRecentMonday } from "@/lib/dates";
import { ink, SPORT_COLORS, status } from "@/lib/palette";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import { gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const WEEKDAY_LETTERS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function TrainingWeekSummary() {
  const [weekStart] = useState(mostRecentMonday());
  const [summary, setSummary] = useState<WeekSummary | null>(null);
  const [schedule, setSchedule] = useState<WeekSchedule | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => {
      api.getWeekSummary(weekStart).then(setSummary).catch((err) => setError(err.message));
      // Calendar is optional (needs Google OAuth creds) - its absence shouldn't
      // block the rest of the panel, so it gets its own error state.
      api
        .getWeekSchedule(weekStart)
        .then(setSchedule)
        .catch((err) => setScheduleError(err.message));
    };

    load();
    const id = setInterval(load, 6 * 60 * 1000); // 10x/hour, matches backend Strava sync cadence
    return () => clearInterval(id);
  }, [weekStart]);

  const chartData =
    summary?.sports.map((s) => ({
      sport: s.sport,
      Target: s.target_minutes ?? 0,
      Actual: s.actual_minutes,
    })) ?? [];

  const restDaySet = new Set(summary?.rest_days ?? []);
  const todayIso = new Date().toISOString().slice(0, 10);

  return (
    <Card icon={Activity} title="Weekly training rollup" meta={summary?.week_label ?? weekStart}>
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!summary && !error && (
        <div className="space-y-2">
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {/* A bar chart only earns its space when there's something to compare
          across - one sport with no target set is better read straight off
          the list below (which also has km and on-track %) than a near-empty
          chart canvas around a single bar. */}
      {summary && chartData.length > 1 && (
        <>
          {/* Custom legend, not Recharts' auto-generated one: "Actual" is
              colored per-sport via <Cell> below, and Recharts can't derive a
              single legend swatch from per-cell colors - it silently falls
              back to black, which read as a broken/missing color. */}
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <LegendChip color={ink.baseline} label="Target" />
            <span className="text-xs text-neutral-500">
              Actual {"—"} colored by sport, see list below
            </span>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="sport" {...xAxisProps} />
                <YAxis {...yAxisProps} unit="m" />
                <Tooltip {...tooltipProps} />
                <Bar dataKey="Target" fill={ink.baseline} radius={[4, 4, 0, 0]} maxBarSize={28} />
                <Bar dataKey="Actual" radius={[4, 4, 0, 0]} maxBarSize={28}>
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.sport}
                      fill={SPORT_COLORS[entry.sport] ?? SPORT_COLORS.other}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {summary && chartData.length === 0 && (
        <p className="text-sm text-neutral-500">
          No activities or targets logged for this week yet.
        </p>
      )}

      {/* Distance is a different scale to minutes, so it's a second measure
          shown as a compact list rather than crammed onto the same chart axis. */}
      {summary && summary.sports.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-3 text-sm">
          {summary.sports.map((s) => {
            const onTrack = s.on_track_pct != null && s.on_track_pct >= 100;
            return (
              <li key={s.sport} className="flex items-center justify-between">
                <span className="flex items-center gap-2 capitalize text-neutral-300">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: SPORT_COLORS[s.sport] ?? SPORT_COLORS.other }}
                  />
                  {s.sport}
                </span>
                <span className="flex items-center gap-1.5 text-neutral-400">
                  {s.actual_distance_km}
                  {s.target_distance_km != null ? ` / ${s.target_distance_km}` : ""} km
                  {s.on_track_pct != null && (
                    <span
                      className="flex items-center gap-0.5 font-medium"
                      style={{ color: onTrack ? status.good : status.warning }}
                    >
                      {onTrack ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                      {s.on_track_pct}%
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {summary && summary.rest_days.length > 0 && (
        <p className="mt-3 text-xs text-neutral-500">
          Rest days:{" "}
          {summary.rest_days
            .map((d) => new Date(d).toLocaleDateString(undefined, { weekday: "short" }))
            .join(", ")}
        </p>
      )}

      <div className="mt-4 border-t border-white/[0.06] pt-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          This week's plan
        </div>
        {scheduleError && (
          <p className="mt-1 text-xs text-neutral-600">
            Calendar not connected ({scheduleError}).
          </p>
        )}
        {schedule && (
          <div className="mt-2 grid grid-cols-7 gap-1 text-center text-xs">
            {Object.entries(schedule.days).map(([dayIso, events], i) => (
              <div
                key={dayIso}
                className={`rounded-lg p-1.5 ${
                  dayIso === todayIso
                    ? "bg-orange-500/10 ring-1 ring-orange-500/40"
                    : "bg-white/[0.03]"
                }`}
              >
                <div className="text-neutral-500">{WEEKDAY_LETTERS[i]}</div>
                <div className="mt-1 truncate text-neutral-300" title={events[0]?.summary}>
                  {events.length > 0
                    ? events[0].summary
                    : restDaySet.has(dayIso)
                      ? "Rest"
                      : "—"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
