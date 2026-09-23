import { useState } from "react";
import { Gauge, Trash2 } from "lucide-react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, GoalGap, Phase, ThresholdHistory, ThresholdTest } from "@/lib/api";
import { fmtMetric, fmtShortDate, parseDuration, todayIso } from "@/lib/format";
import { ink, SPORT_COLORS, surface } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import { ChartTable, gridProps, LegendChip, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

interface Panel {
  id: string;
  title: string;
  discipline: "swim" | "bike" | "run";
  metrics: string[]; // metrics plotted on this (single-unit) chart
  unit: string;
  lowerIsBetter: boolean;
  always: boolean; // show an empty placeholder even with no data
  required?: (g: GoalGap) => number;
}

const PANELS: Panel[] = [
  { id: "css", title: "Swim CSS", discipline: "swim", metrics: ["css_pace"], unit: "s/100m", lowerIsBetter: true, always: true, required: (g) => g.required.css_pace_s_per_100m },
  { id: "ftp", title: "Bike FTP", discipline: "bike", metrics: ["ftp", "np_proxy"], unit: "W", lowerIsBetter: false, always: true, required: (g) => g.required.ftp_w },
  { id: "lthr_bike", title: "Bike LTHR", discipline: "bike", metrics: ["lthr_bike"], unit: "bpm", lowerIsBetter: false, always: false },
  { id: "hm", title: "Half marathon", discipline: "run", metrics: ["hm_time", "hm_prediction"], unit: "s", lowerIsBetter: true, always: true, required: (g) => g.required.hm_standalone_s },
  { id: "tpace", title: "Run threshold pace", discipline: "run", metrics: ["threshold_pace"], unit: "s/km", lowerIsBetter: true, always: false },
  { id: "lthr_run", title: "Run LTHR", discipline: "run", metrics: ["lthr_run"], unit: "bpm", lowerIsBetter: false, always: false },
];

const METRIC_OPTIONS = [
  { value: "css_pace", label: "Swim CSS (m:ss per 100m)", unit: "s/100m" },
  { value: "ftp", label: "Bike FTP (W)", unit: "W" },
  { value: "np_proxy", label: "Bike NP proxy (W)", unit: "W" },
  { value: "lthr_bike", label: "Bike LTHR (bpm)", unit: "bpm" },
  { value: "threshold_pace", label: "Run threshold pace (m:ss per km)", unit: "s/km" },
  { value: "lthr_run", label: "Run LTHR (bpm)", unit: "bpm" },
  { value: "hm_time", label: "Half-marathon time (h:mm:ss)", unit: "s" },
];

const toTs = (iso: string) => new Date(iso + "T00:00:00").getTime();

/** First-of-month ticks across the domain (every 2nd month on long spans). */
function monthTicks([start, end]: [number, number]): number[] {
  const d = new Date(start);
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  d.setMonth(d.getMonth() + 1);
  const ticks: number[] = [];
  while (d.getTime() <= end) {
    ticks.push(d.getTime());
    d.setMonth(d.getMonth() + 1);
  }
  return ticks.length > 7 ? ticks.filter((_, i) => i % 2 === 0) : ticks;
}

const STEPS: Record<string, number[]> = {
  s: [60, 120, 300, 600, 900, 1800],
  "s/100m": [1, 2, 5, 10, 15, 30],
  "s/km": [5, 10, 15, 30, 60],
  W: [5, 10, 20, 25, 50, 100],
  bpm: [1, 2, 5, 10, 20],
};

/** Round-number ticks (<= 5) so time/pace axes read 1:45:00, not 1:08:19. */
function niceTicks(lo: number, hi: number, unit: string): number[] {
  const steps = STEPS[unit] ?? [1, 2, 5, 10, 20, 50, 100];
  const step = steps.find((s) => (hi - lo) / s <= 4) ?? steps[steps.length - 1];
  const first = Math.floor(lo / step) * step;
  const ticks: number[] = [];
  for (let v = first; v <= hi + step * 0.001; v += step) ticks.push(v);
  if (ticks[ticks.length - 1] < hi) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}
const monthTick = (ts: number) =>
  new Date(ts).toLocaleDateString(undefined, { month: "short", year: "2-digit" });

function PanelChart({
  panel,
  tests,
  phases,
  domain,
  raceTs,
  required,
}: {
  panel: Panel;
  tests: ThresholdTest[];
  phases: Phase[];
  domain: [number, number];
  raceTs: number | null;
  required: number | null;
}) {
  const color = SPORT_COLORS[panel.discipline];
  // Pull the panel's start back to its latest pre-Phase-1 point, so a value
  // that's still in use (e.g. Garmin's May FTP) isn't hidden by the window.
  const before = tests.filter((t) => toTs(t.test_date) < domain[0]);
  const lastBefore = before.length ? Math.max(...before.map((t) => toTs(t.test_date))) : null;
  if (lastBefore != null) domain = [lastBefore, domain[1]];
  const inWindow = tests.filter((t) => toTs(t.test_date) >= domain[0]);
  const real = inWindow.filter((t) => t.source !== "garmin").map((t) => ({ t: toTs(t.test_date), v: t.value, row: t }));
  const est = inWindow.filter((t) => t.source === "garmin").map((t) => ({ t: toTs(t.test_date), v: t.value, row: t }));
  // An estimate still stands until replaced - extend the latest one to today as a step.
  const todayTs = toTs(todayIso());
  if (est.length && est[est.length - 1].t < todayTs) est.push({ ...est[est.length - 1], t: todayTs });
  const values = [...real, ...est].map((p) => p.v).concat(required != null ? [required] : []);
  const pad = values.length ? (Math.max(...values) - Math.min(...values)) * 0.15 || Math.max(...values) * 0.05 : 1;
  const yTicks = values.length
    ? niceTicks(Math.max(0, Math.min(...values) - pad), Math.max(...values) + pad, panel.unit)
    : undefined;
  const yDomain: [number, number] | undefined = yTicks ? [yTicks[0], yTicks[yTicks.length - 1]] : undefined;

  return (
    <div className="rounded-xl bg-white/[0.02] p-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-neutral-200">{panel.title}</div>
        <div className="flex gap-3">
          {real.length > 0 && <LegendChip color={color} label="Test" />}
          {est.length > 0 && <LegendChip color={ink.muted} label="Garmin estimate" line />}
          {required != null && <LegendChip color={ink.secondary} label="Race-goal need" line />}
        </div>
      </div>
      {real.length === 0 && est.length === 0 ? (
        <div className="mt-1 flex h-40 flex-col items-center justify-center rounded-lg border border-dashed border-white/[0.06] text-xs text-neutral-500">
          <span>No tests logged yet</span>
          {required != null && <span className="mt-1 text-neutral-600">Race goal needs {fmtMetric(required, panel.unit)}</span>}
        </div>
      ) : (
      <div className="mt-1 h-40">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart margin={{ top: 14, right: 8, left: 4, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            {phases.map((p, i) => (
              <ReferenceArea
                key={p.number}
                x1={Math.max(toTs(p.start_date), domain[0])}
                x2={p.end_date ? toTs(p.end_date) : domain[1]}
                fill={i % 2 === 0 ? "rgba(255,255,255,0.025)" : "rgba(255,255,255,0.0)"}
                ifOverflow="hidden"
                label={{ value: `P${p.number}`, position: "insideTop", fill: ink.muted, fontSize: 10 }}
              />
            ))}
            <XAxis
              type="number"
              dataKey="t"
              domain={domain}
              scale="time"
              tickFormatter={monthTick}
              ticks={monthTicks(domain)}
              {...xAxisProps}
              allowDuplicatedCategory={false}
            />
            <YAxis
              type="number"
              dataKey="v"
              domain={yDomain ?? ["auto", "auto"]}
              ticks={yTicks}
              reversed={panel.lowerIsBetter}
              tickFormatter={(v: number) => fmtMetric(v, panel.unit).replace("/100m", "").replace("/km", "")}
              {...yAxisProps}
              width={52}
            />
            <Tooltip
              {...tooltipProps}
              labelFormatter={(ts: number) => fmtShortDate(new Date(ts).toISOString().slice(0, 10))}
              formatter={(v: number) => [fmtMetric(v, panel.unit), panel.title]}
            />
            {required != null && (
              <ReferenceLine y={required} stroke={ink.secondary} strokeWidth={1} ifOverflow="extendDomain" />
            )}
            {raceTs && <ReferenceLine x={raceTs} stroke={ink.baseline} />}
            {est.length > 0 && (
              <Line data={est} dataKey="v" stroke={ink.muted} strokeWidth={2} dot={false} isAnimationActive={false} type="stepAfter" />
            )}
            {real.length > 0 && (
              <Line
                data={real}
                dataKey="v"
                stroke={color}
                strokeWidth={2}
                dot={{ r: 4, fill: color, stroke: surface.card, strokeWidth: 2 }}
                activeDot={{ r: 6 }}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      )}
    </div>
  );
}

function AddTestForm({ onAdded }: { onAdded: () => void }) {
  const [metric, setMetric] = useState("css_pace");
  const [value, setValue] = useState("");
  const [on, setOn] = useState(todayIso());
  const [protocol, setProtocol] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const unit = METRIC_OPTIONS.find((m) => m.value === metric)!.unit;

  const submit = async () => {
    setErr(null);
    const parsed = unit === "W" || unit === "bpm" ? Number(value) : parseDuration(value);
    if (!parsed || !isFinite(parsed) || parsed <= 0) {
      setErr(unit === "W" || unit === "bpm" ? "Enter a number." : "Enter a time like 1:45 or 1:52:30.");
      return;
    }
    try {
      await api.createThreshold({ test_date: on, metric, value: parsed, protocol: protocol || null });
      setValue("");
      setProtocol("");
      onAdded();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const cls = "rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-sm text-white placeholder:text-neutral-600";
  return (
    <div className="mt-4 border-t border-white/[0.06] pt-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Log a test / estimate</div>
      <div className="flex flex-wrap items-center gap-1.5">
        <select className={cls} value={metric} onChange={(e) => setMetric(e.target.value)}>
          {METRIC_OPTIONS.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
        <input className={`${cls} w-24`} placeholder="value" value={value} onChange={(e) => setValue(e.target.value)} />
        <input type="date" className={`${cls} w-36`} value={on} onChange={(e) => setOn(e.target.value)} />
        <input className={`${cls} w-40`} placeholder="protocol (optional)" value={protocol} onChange={(e) => setProtocol(e.target.value)} />
        <button onClick={submit} className="rounded-md bg-white/[0.08] px-2.5 py-1 text-xs font-medium text-neutral-200 hover:bg-white/[0.14]">
          Add
        </button>
      </div>
      {err && <p className="mt-1 text-xs text-red-400">{err}</p>}
    </div>
  );
}

export default function ThresholdTrends() {
  const { data, error, reload } = usePolling(api.getThresholds);
  const { data: gap } = usePolling(api.getGoalGap);

  const history: ThresholdHistory | null = data;
  const phase1 = history?.phases[0];
  const start = phase1 ? toTs(phase1.start_date) : Date.now() - 90 * 864e5;
  const raceTs = history?.race_date ? toTs(history.race_date) : null;
  const end = raceTs ?? Date.now() + 300 * 864e5;
  const domain: [number, number] = [start, end];

  const visible = PANELS.filter(
    (p) => p.always || history?.tests.some((t) => p.metrics.includes(t.metric))
  );
  const manual = history?.tests.filter((t) => t.source === "manual") ?? [];

  const remove = async (id: number) => {
    await api.deleteThreshold(id);
    reload();
  };

  return (
    <Card icon={Gauge} title="Threshold trends" meta={phase1 ? `Phase 1 → race day` : undefined} className="lg:col-span-2">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {!history && !error && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full" />
          ))}
        </div>
      )}

      {history && (
        <>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {visible.map((p) => (
              <PanelChart
                key={p.id}
                panel={p}
                tests={history.tests.filter((t) => p.metrics.includes(t.metric))}
                phases={history.phases}
                domain={domain}
                raceTs={raceTs}
                required={gap && p.required ? p.required(gap) : null}
              />
            ))}
          </div>
          <p className="mt-2 text-xs text-neutral-500">
            Shaded bands are training phases from your calendar ({history.phases.map((p) => `P${p.number} ${p.name}`).join(" · ")}).
            Pace/time axes are inverted so faster is up. Gate results (HM TT, CSS, LTHR) land here automatically.
          </p>

          <ChartTable
            columns={["Date", "Metric", "Value", "Source", ""]}
            rows={[...history.tests].reverse().map((t) => [
              fmtShortDate(t.test_date),
              t.metric,
              fmtMetric(t.value, t.unit),
              t.source === "garmin" ? "Garmin estimate" : t.source === "phase_gate" ? "Phase gate" : "Manual",
              t.source === "manual" ? (
                <button aria-label="Delete" className="text-neutral-500 hover:text-red-400" onClick={() => remove(t.id)}>
                  <Trash2 size={12} />
                </button>
              ) : (
                ""
              ),
            ])}
            summary={`Show all ${history.tests.length} entries as table${manual.length ? ` (${manual.length} manual)` : ""}`}
          />

          <AddTestForm onAdded={reload} />
        </>
      )}
    </Card>
  );
}
