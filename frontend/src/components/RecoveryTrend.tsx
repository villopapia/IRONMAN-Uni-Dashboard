import { ReactNode } from "react";
import { Activity as Pulse } from "lucide-react";
import { CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, TrendMetric } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { ink, status, surface } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { FLAG_BADGE } from "@/components/ui/StatusBadge";
import { gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

const MARGIN = { top: 4, right: 4, left: -8, bottom: 0 };
const DOT = { r: 2.5, fill: ink.muted, stroke: surface.card, strokeWidth: 1 };

// Status, value and basis are the Readiness service's, shown over a longer window.
function Panel({ title, metric, legend, children }: { title: string; metric: TrendMetric; legend: ReactNode; children: ReactNode }) {
  const [tone, label] = FLAG_BADGE[metric.status] ?? FLAG_BADGE.no_data;
  return (
    <div>
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="text-sm font-medium text-neutral-200">{title}</span>
          <span className="ml-2 text-lg font-semibold tabular-nums text-white">{metric.value ?? "—"}</span>
          {metric.value != null && <span className="ml-1 text-xs text-neutral-500">{metric.unit}</span>}
          <div className="text-xs text-neutral-500">{metric.basis}</div>
        </div>
        <StatusBadge tone={tone} label={label} compact />
      </div>
      <div className="mt-1 h-28">{children}</div>
      <div className="mt-1 flex flex-wrap items-center gap-3">{legend}</div>
    </div>
  );
}

export default function RecoveryTrend() {
  const { data, error } = usePolling(() => api.getRecoveryTrend(42));
  const series = data?.series ?? [];

  return (
    <Card icon={Pulse} title="Recovery trends" info={data?.note} meta="HRV and resting HR, 6 weeks">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-56 w-full" />}

      {data && (
        <div className="space-y-4">
          <Panel
            title="HRV"
            metric={data.hrv}
            legend={
              <>
                <LegendChip color={ink.muted} label="Daily" />
                <LegendChip color="rgba(255,255,255,0.25)" label="Baseline band (mean ± 1 SD, prior 30 days)" />
              </>
            }
          >
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} syncId="recovery" margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                {data.hrv.band && <ReferenceArea y1={data.hrv.band[0]} y2={data.hrv.band[1]} fill="rgba(255,255,255,0.07)" ifOverflow="extendDomain" />}
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={30} hide />
                <YAxis {...yAxisProps} domain={["dataMin - 3", "dataMax + 3"]} allowDecimals={false} />
                <Tooltip {...tooltipProps} labelFormatter={(d: string) => fmtShortDate(d)} formatter={(v: number) => [`${v} ms`, "HRV"]} />
                <Line dataKey="hrv" name="HRV" stroke="transparent" dot={DOT} isAnimationActive={false} connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </Panel>

          <Panel
            title="Resting HR"
            metric={data.rhr}
            legend={
              <>
                <LegendChip color={ink.muted} label="Daily" />
                <LegendChip color={ink.secondary} label="7-day average" line />
                <LegendChip color={status.warning} label={`Amber from ${data.rhr_amber_from}`} line />
                <LegendChip color={status.critical} label={`Red from ${data.rhr_red_from}`} line />
              </>
            }
          >
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} syncId="recovery" margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                <ReferenceLine y={data.rhr_amber_from} stroke={status.warning} strokeDasharray="4 3" ifOverflow="extendDomain" />
                <ReferenceLine y={data.rhr_red_from} stroke={status.critical} strokeDasharray="4 3" ifOverflow="extendDomain" />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={30} />
                <YAxis {...yAxisProps} domain={["dataMin - 2", "dataMax + 2"]} allowDecimals={false} />
                <Tooltip {...tooltipProps} labelFormatter={(d: string) => fmtShortDate(d)} formatter={(v: number, name: string) => [`${v} bpm`, name]} />
                <Line dataKey="rhr" name="Daily" stroke="transparent" dot={DOT} isAnimationActive={false} connectNulls={false} />
                <Line dataKey="rhr_7d" name="7-day average" stroke={ink.secondary} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </Panel>
        </div>
      )}
    </Card>
  );
}
