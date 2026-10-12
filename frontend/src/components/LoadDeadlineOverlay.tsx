import { AlertOctagon, CalendarClock, Flame, Layers, TrendingUp } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  TooltipProps,
  XAxis,
  YAxis,
} from "recharts";
import { api, OverlayWeek } from "@/lib/api";
import { fmtShortDate, fmtWeekRange } from "@/lib/format";
import { ink, status, surface } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import { ChartTable, gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

// Both charts share these so their week bands line up exactly with each
// other and with the flag row underneath (plot starts at Y_AXIS_W px).
const Y_AXIS_W = 44;
const MARGIN = { top: 6, right: 8, left: 0, bottom: 0 };

type Row = {
  label: string;
  actual: number;
  projected: number;
  threshold: number;
  planned: number | null;
  deadlines: number;
  w: OverlayWeek;
};

const pct = (done: number, of: number) => `${Math.round((done / of) * 100)}%`;

// Recharts' default tooltip lists every stacked series regardless of value,
// so a future week (nothing trained yet) shows a bare "Actual load: 0" next
// to "Planned (projected): 974" with no indication *why* actual is 0 - reads
// as "did I really train zero that week?" rather than "hasn't happened yet."
// A custom tooltip states which number is real vs. projected explicitly.
function TrainingLoadTooltip({ active, payload }: TooltipProps<number, string>) {
  const w = (payload?.[0]?.payload as Row | undefined)?.w;
  if (!active || !w) return null;
  const isFuture = w.state === "future";
  const isCurrent = w.state === "current";
  return (
    <div style={tooltipProps.contentStyle} className="px-3 py-2">
      <div style={{ color: ink.primary, marginBottom: 4 }}>
        {fmtWeekRange(w.week_start)}
        {w.state === "current" ? " (this week)" : ""}
      </div>
      {isFuture ? (
        <div style={{ color: ink.secondary }}>
          Hasn't happened yet - planned load: <strong style={{ color: ink.primary }}>{Math.round(w.projected_load ?? 0)}</strong>
        </div>
      ) : (
        <div style={{ color: ink.secondary }}>
          {isCurrent ? "Actual load so far" : "Actual load"}: <strong style={{ color: ink.primary }}>{Math.round(w.actual_load)}</strong>
        </div>
      )}
      {isCurrent && w.planned_load > 0 && (
        <div style={{ color: ink.secondary }}>
          Planned for the week: <strong style={{ color: ink.primary }}>{Math.round(w.planned_load)}</strong> · done{" "}
          {pct(w.actual_load, w.planned_load)}
        </div>
      )}
      {isCurrent && w.planned_to_date > 0 && (
        <div style={{ color: ink.secondary }}>Should be at about {Math.round(w.planned_to_date)} by today</div>
      )}
      <div style={{ color: ink.muted }}>Your usual week: {Math.round(w.chronic_weekly_load)}</div>
      {w.step_up && <div style={{ color: status.warning }}>Big step up on the week before</div>}
      {w.no_deload && <div style={{ color: status.warning }}>4+ hard weeks in a row, no lighter week</div>}
      {w.deload && <div style={{ color: ink.secondary }}>Lighter (deload) week</div>}
    </div>
  );
}

// One plain-English line so the chart doesn't have to be decoded: how big the
// plan is versus what's actually been done, and whether any rest is planned.
function headline(weeks: OverlayWeek[]): string {
  const done = weeks.filter((w) => w.state === "past").map((w) => w.actual_load);
  const ahead = weeks.filter((w) => w.state !== "past" && w.total_load != null);
  if (!done.length || !ahead.length) return "";
  const biggest = Math.max(...done);
  const peak = ahead.reduce((a, b) => (b.total_load! > a.total_load! ? b : a));
  const lighter = ahead.filter((w) => w.deload).length;
  const rest = lighter ? `${lighter} lighter week${lighter > 1 ? "s" : ""} planned` : "no lighter week planned";
  const cur = weeks.find((w) => w.state === "current");
  let thisWeek = "";
  if (cur && cur.planned_load > 0) {
    const gap = Math.round(cur.planned_to_date - cur.actual_load);
    const pace =
      cur.planned_to_date < 1
        ? ""
        : gap > 10
          ? ` — about ${gap} behind where the plan says you should be by today`
          : gap < -10
            ? ` — about ${-gap} ahead of the plan so far`
            : " — on plan so far";
    thisWeek = `This week: ${Math.round(cur.actual_load)} done of ${Math.round(cur.planned_load)} planned (${pct(cur.actual_load, cur.planned_load)})${pace}. `;
  }
  return `${thisWeek}Your biggest completed week is ${Math.round(biggest)}; the plan peaks at ${Math.round(peak.total_load!)} (w/c ${fmtShortDate(peak.week_start)}), ${(peak.total_load! / biggest).toFixed(1)}× that, with ${rest}.`;
}

export default function LoadDeadlineOverlay() {
  const { data, error } = usePolling(() => api.getOverlay(6, 10));

  const rows =
    data?.weeks.map((w) => ({
      label: fmtWeekRange(w.week_start),
      actual: w.actual_load,
      projected: w.projected_load ?? 0,
      threshold: w.chronic_weekly_load,
      // Current week only: earlier weeks had little or nothing in the calendar
      // (summer), so "vs plan" there would read as a huge overshoot.
      planned: w.state === "current" && w.planned_load > 0 ? w.planned_load : null,
      deadlines: w.deadline_count,
      w,
    })) ?? [];
  const currentLabel = rows.find((r) => r.w.state === "current")?.label;
  const riskCount = data?.risk_weeks.length ?? 0;
  const n = rows.length;
  const noDeadlines = !!data && data.weeks.every((w) => w.deadline_count === 0);

  const trainingFill = (w: OverlayWeek, projected: boolean) =>
    w.training_elevated ? (projected ? `${status.warning}a6` : status.warning) : projected ? ink.muted : ink.secondary;

  return (
    <Card
      icon={Layers}
      title="Training load vs academic deadlines"
      meta={
        data ? (
          riskCount > 0 ? (
            <StatusBadge tone="critical" label={`${riskCount} risk week${riskCount > 1 ? "s" : ""}`} />
          ) : noDeadlines ? (
            <StatusBadge tone="neutral" label="No deadlines entered — can't check for overlap" />
          ) : (
            <StatusBadge tone="good" label="No overlapping spikes" />
          )
        ) : undefined
      }
      className="lg:col-span-2"
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && (
        <div className="space-y-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {data && (
        <>
          <p className="mb-3 text-sm text-neutral-200">{headline(data.weeks)}</p>
          <div className="mb-1 flex flex-wrap items-center gap-3">
            <span className="text-xs font-medium text-neutral-300">Training load / week (Strava Relative Effort)</span>
            <LegendChip color={ink.secondary} label="Actual" />
            <LegendChip color={ink.muted} label="Planned (projected)" />
            <LegendChip color={ink.primary} label="Plan for that week" />
            <LegendChip color={status.warning} label="Flagged" />
            <LegendChip color={ink.muted} label="Your usual week" line />
          </div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                {currentLabel && <ReferenceArea x1={currentLabel} x2={currentLabel} fill="rgba(255,255,255,0.04)" />}
                <XAxis dataKey="label" {...xAxisProps} hide />
                <YAxis {...yAxisProps} width={Y_AXIS_W} />
                <Tooltip cursor={tooltipProps.cursor} content={<TrainingLoadTooltip />} />
                <Bar dataKey="actual" name="Actual load" stackId="t" maxBarSize={22} isAnimationActive={false}>
                  {rows.map((r) => (
                    <Cell key={r.label} fill={trainingFill(r.w, false)} />
                  ))}
                </Bar>
                <Bar dataKey="projected" name="Planned (projected)" stackId="t" maxBarSize={22} radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {rows.map((r) => (
                    <Cell key={r.label} fill={trainingFill(r.w, true)} />
                  ))}
                </Bar>
                {/* Past/current weeks: where the plan said the week should land. */}
                <Line
                  dataKey="planned"
                  name="Planned for the week"
                  stroke="none"
                  dot={{ r: 4, fill: ink.primary, stroke: surface.card, strokeWidth: 2 }}
                  activeDot={false}
                  isAnimationActive={false}
                  legendType="none"
                />
                <Line
                  dataKey="threshold"
                  name="Your usual week"
                  type="step"
                  stroke={ink.muted}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="mb-1 mt-3 flex items-center gap-3">
            <span className="text-xs font-medium text-neutral-300">Deadlines due / week</span>
            <LegendChip color={ink.secondary} label="Due" />
            <LegendChip color={status.warning} label={`Elevated (${data.deadline_count_threshold}+ or an exam)`} />
          </div>
          <div className="h-24">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                {currentLabel && <ReferenceArea x1={currentLabel} x2={currentLabel} fill="rgba(255,255,255,0.04)" />}
                <XAxis dataKey="label" {...xAxisProps} interval="preserveStartEnd" tick={{ fill: ink.secondary, fontSize: 10 }} />
                <YAxis
                  {...yAxisProps}
                  width={Y_AXIS_W}
                  allowDecimals={false}
                  interval={0}
                  domain={[0, Math.max(3, ...rows.map((r) => r.deadlines))]}
                  ticks={Array.from({ length: Math.max(3, ...rows.map((r) => r.deadlines)) + 1 }, (_, i) => i)}
                />
                <Tooltip {...tooltipProps} formatter={(v: number) => [v, "Deadlines"]} />
                <Bar dataKey="deadlines" name="Deadlines" maxBarSize={22} radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {rows.map((r) => (
                    <Cell key={r.label} fill={r.w.deadline_elevated ? status.warning : ink.secondary} />
                  ))}
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Flag row aligned to the week bands above. */}
          <div
            className="mt-1 grid"
            style={{
              gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))`,
              paddingLeft: Y_AXIS_W + MARGIN.left,
              paddingRight: MARGIN.right,
            }}
          >
            {rows.map((r) => (
              <div key={r.label} className="flex h-6 items-center justify-center" title={r.w.risk ? "Training AND deadlines elevated" : undefined}>
                {r.w.risk ? (
                  <AlertOctagon size={15} style={{ color: status.critical }} aria-label="risk week" />
                ) : (
                  <span className="flex gap-0.5" style={{ color: status.warning }}>
                    {r.w.step_up && <TrendingUp size={13} aria-label="step up" />}
                    {r.w.no_deload && <Flame size={13} aria-label="no lighter week" />}
                    {r.w.deadline_elevated && <CalendarClock size={13} aria-label="deadlines" />}
                  </span>
                )}
              </div>
            ))}
          </div>
          <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-neutral-500">
            <span className="inline-flex items-center gap-1">
              <AlertOctagon size={12} style={{ color: status.critical }} /> risk week (both elevated)
            </span>
            <span className="inline-flex items-center gap-1"><TrendingUp size={12} style={{ color: status.warning }} /> big step up on the week before</span>
            <span className="inline-flex items-center gap-1"><Flame size={12} style={{ color: status.warning }} /> 4+ hard weeks, no lighter week</span>
            <span className="inline-flex items-center gap-1"><CalendarClock size={12} style={{ color: status.warning }} /> deadlines elevated</span>
          </div>

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">
            {data.note} Load/hour used for projection:{" "}
            {Object.entries(data.load_per_hour_by_discipline)
              .filter(([k]) => ["swim", "bike", "run", "gym"].includes(k))
              .map(([k, v]) => `${k} ${v}${data.load_per_hour_fallback.includes(k) ? "*" : ""}`)
              .join(", ")}
            {" "}RE/h.
            {data.load_per_hour_fallback.some((k) => ["swim", "bike", "run", "gym"].includes(k)) && " * all-history fallback."}
          </p>

          <ChartTable
            columns={["Week", "Load", "Plan", "Usual week", "Planned h", "Deadlines", "Flag"]}
            rows={rows.map((r) => [
              `${r.label}${r.w.state === "current" ? " (now)" : ""}`,
              r.w.total_load != null ? `${Math.round(r.w.total_load)}${r.w.state !== "past" && r.w.projected_load ? " (proj.)" : ""}` : "—",
              r.w.planned_load > 0 ? Math.round(r.w.planned_load) : "—",
              Math.round(r.w.chronic_weekly_load),
              r.w.planned_hours || "—",
              r.w.deadlines.length ? r.w.deadlines.map((d) => d.title).join(", ") : "—",
              r.w.risk
                ? "RISK"
                : [r.w.step_up ? "step up" : "", r.w.no_deload ? "no deload" : "", r.w.deadline_elevated ? "deadlines" : ""]
                    .filter(Boolean)
                    .join(", ") || "—",
            ])}
          />
        </>
      )}
    </Card>
  );
}
