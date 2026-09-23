import { AlertOctagon, Layers } from "lucide-react";
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
import { fmtShortDate } from "@/lib/format";
import { ink, status } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import { ChartTable, gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

// Both charts share these so their week bands line up exactly with each
// other and with the flag row underneath (plot starts at Y_AXIS_W px).
const Y_AXIS_W = 44;
const MARGIN = { top: 6, right: 8, left: 0, bottom: 0 };

type Row = { label: string; actual: number; projected: number; threshold: number; deadlines: number; w: OverlayWeek };

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
        {fmtShortDate(w.week_start)}
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
      <div style={{ color: ink.muted }}>Elevated above: {Math.round(w.elevated_above ?? 0)}</div>
      {w.training_elevated && <div style={{ color: status.warning }}>Training elevated this week</div>}
    </div>
  );
}

export default function LoadDeadlineOverlay() {
  const { data, error } = usePolling(() => api.getOverlay(6, 10));

  const rows =
    data?.weeks.map((w) => ({
      label: fmtShortDate(w.week_start),
      actual: w.actual_load,
      projected: w.projected_load ?? 0,
      threshold: w.elevated_above,
      deadlines: w.deadline_count,
      w,
    })) ?? [];
  const currentLabel = rows.find((r) => r.w.state === "current")?.label;
  const riskCount = data?.risk_weeks.length ?? 0;
  const n = rows.length;

  const trainingFill = (w: OverlayWeek, projected: boolean) =>
    w.training_elevated ? (projected ? `${status.warning}66` : status.warning) : projected ? ink.baseline : ink.secondary;

  return (
    <Card
      icon={Layers}
      title="Training load vs academic deadlines"
      meta={
        data ? (
          riskCount > 0 ? (
            <StatusBadge tone="critical" label={`${riskCount} risk week${riskCount > 1 ? "s" : ""}`} />
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
          <div className="mb-1 flex flex-wrap items-center gap-3">
            <span className="text-xs font-medium text-neutral-300">Training load / week</span>
            <LegendChip color={ink.secondary} label="Actual" />
            <LegendChip color={ink.baseline} label="Planned (projected)" />
            <LegendChip color={status.warning} label="Elevated" />
            <LegendChip color={ink.muted} label={`Elevated above (${data.acwr_threshold}× chronic)`} line />
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
                <Line
                  dataKey="threshold"
                  name="Elevated above"
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
                <XAxis dataKey="label" {...xAxisProps} interval={0} tick={{ fill: ink.secondary, fontSize: 10 }} />
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
                  <span className="text-[10px] text-neutral-600">
                    {r.w.training_elevated ? "T" : ""}
                    {r.w.deadline_elevated ? "D" : ""}
                  </span>
                )}
              </div>
            ))}
          </div>
          <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-neutral-500">
            <span className="inline-flex items-center gap-1">
              <AlertOctagon size={12} style={{ color: status.critical }} /> risk week (both elevated)
            </span>
            <span>T = training elevated only</span>
            <span>D = deadlines elevated only</span>
          </div>

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">
            {data.note} Load/hour used for projection:{" "}
            {Object.entries(data.load_per_hour_by_discipline)
              .filter(([k]) => ["swim", "bike", "run", "gym"].includes(k))
              .map(([k, v]) => `${k} ${v}`)
              .join(", ")}
            .
          </p>

          <ChartTable
            columns={["Week", "Load", "Elevated above", "Ratio", "Planned h", "Deadlines", "Flag"]}
            rows={rows.map((r) => [
              `${r.label}${r.w.state === "current" ? " (now)" : ""}`,
              r.w.total_load != null ? `${Math.round(r.w.total_load)}${r.w.state !== "past" && r.w.projected_load ? " (proj.)" : ""}` : "—",
              r.w.elevated_above != null ? Math.round(r.w.elevated_above) : "—",
              r.w.load_ratio ?? "—",
              r.w.planned_hours || "—",
              r.w.deadlines.length ? r.w.deadlines.map((d) => d.title).join(", ") : "—",
              r.w.risk ? "RISK" : [r.w.training_elevated ? "T" : "", r.w.deadline_elevated ? "D" : ""].join(" ").trim() || "—",
            ])}
          />
        </>
      )}
    </Card>
  );
}
