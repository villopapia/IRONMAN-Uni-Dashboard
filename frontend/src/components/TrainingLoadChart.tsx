import { useState } from "react";
import { TrendingUp } from "lucide-react";
import {
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
import { api, PmcPoint } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { ink, LOAD_COLORS, SPORT_COLORS, status } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatTile from "@/components/ui/StatTile";
import StatusBadge from "@/components/ui/StatusBadge";
import { ChartTable, gridProps, legendProps, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

// Season = season start to race day: the x-axis runs past today and carries
// the CTL projected from the calendar plan.
const RANGES = [
  { id: "90d", label: "90d", days: 90 },
  { id: "6m", label: "6m", days: 180 },
  { id: "season", label: "Season", days: 180 },
] as const;
type RangeId = (typeof RANGES)[number]["id"];

// Total = overall fitness and fatigue; By sport = the fitness line split into swim, bike and run.
const VIEWS = [
  { id: "total", label: "Total" },
  { id: "sport", label: "By sport" },
] as const;
const CTL_SPORTS = ["swim", "bike", "run"] as const;

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

// Same margins on both charts so syncId lines the days up; the right margin
// leaves room for the value labels at the end of each line.
const MARGIN = { top: 4, right: 40, left: -8, bottom: 0 };
const SPARK_DAYS = 28;
const DAY_MS = 86_400_000;
const MARKER_LABEL = { position: "insideTopLeft", fill: ink.secondary, fontSize: 10, dy: 12 } as const;
const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

// The current value, written at the end of its line (the last real data point).
type PointLabel = { x?: number; y?: number; index?: number; value?: number | string };
const endLabel = (at: number) => (p: PointLabel) =>
  p.index === at && p.value != null ? (
    <text x={(p.x ?? 0) + 6} y={(p.y ?? 0) + 4} fill={ink.primary} fontSize={11}>
      {Number(p.value).toFixed(1)}
    </text>
  ) : (
    <g />
  );

function Toggle<T extends string>({ options, value, onChange }: { options: readonly { id: T; label: string }[]; value: T; onChange: (id: T) => void }) {
  return (
    <span className="inline-flex rounded-md bg-white/[0.04] p-0.5 text-xs">
      {options.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          aria-pressed={value === o.id}
          className={`rounded px-2 py-0.5 ${value === o.id ? "bg-white/[0.1] text-white" : "text-neutral-500 hover:text-neutral-300"}`}
        >
          {o.label}
        </button>
      ))}
    </span>
  );
}

export default function TrainingLoadChart() {
  const [range, setRange] = useState<RangeId>("6m");
  const [view, setView] = useState<(typeof VIEWS)[number]["id"]>("total");
  const { data: season } = usePolling(() => api.getSeason());
  // Until the season config has loaded, "Season" falls back to the 6m window.
  const seasonView = range === "season" && !!season;
  const rangeDays =
    seasonView && season
      ? Math.round((Date.parse(season.today) - Date.parse(season.season_start)) / DAY_MS) + 1
      : RANGES.find((r) => r.id === range)!.days;
  const { data, error } = usePolling(
    () => (seasonView && season ? api.getPmc({ since: season.season_start, projectTo: season.race.date }) : api.getPmc({ days: rangeDays })),
    [range, seasonView],
  );
  const { data: sport } = usePolling(() => api.getSportCtl(rangeDays), [rangeDays]);

  const actual: PmcPoint[] = data?.series ?? [];
  const cur = data?.current;
  const lastIdx = actual.length - 1;
  const projection = seasonView ? (data?.projection ?? []) : [];
  const sportByDate = new Map((sport?.series ?? []).map((p) => [p.date, p]));
  // One row per day; the projection continues the CTL line from today's value.
  const rows = [
    ...actual.map((p, i) => {
      const s = sportByDate.get(p.date);
      return {
        date: p.date,
        ctl: p.ctl,
        atl: p.atl,
        tsb: p.tsb,
        proj: i === lastIdx && projection.length > 0 ? p.ctl : undefined,
        swim: s?.swim,
        bike: s?.bike,
        run: s?.run,
      };
    }),
    ...projection.map((p) => ({ date: p.date, proj: p.ctl })),
  ];

  // Gates, race day and phases only draw where they fall inside the charted range.
  const first = rows[0]?.date;
  const last = rows[rows.length - 1]?.date;
  const inRange = (d: string) => !!first && !!last && d >= first && d <= last;
  const markers = season ? [...season.gates.map((g) => ({ date: g.date, label: g.name })), { date: season.race.date, label: "Race day" }].filter((m) => inRange(m.date)) : [];
  const bands =
    season && first && last
      ? season.phases.filter((p) => p.start <= last && p.end >= first).map((p) => ({ name: p.name, x1: p.start < first ? first : p.start, x2: p.end > last ? last : p.end }))
      : [];

  const tsbMin = Math.min(-35, ...actual.map((p) => p.tsb));
  const tsbMax = Math.max(15, ...actual.map((p) => p.tsb));
  const tail = actual.slice(-SPARK_DAYS);
  const rampSeries = actual.flatMap((p, i) => (i >= 7 ? [p.ctl - actual[i - 7].ctl] : [])).slice(-SPARK_DAYS);
  const rampFlag = data?.ramp_status === "red" ? ("critical" as const) : data?.ramp_status === "amber" ? ("warning" as const) : null;

  const info = data
    ? [
        data.methodology_note,
        data.estimated_sessions > 0 ? `${data.estimated_sessions} of ${data.total_sessions} sessions use the estimated fallback.` : "",
        data.first_load_date
          ? `History starts ${new Date(data.first_load_date + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })} (CTL starts from 0 there, so the first six weeks read low).`
          : "",
        `CTL ramp: normal ${data.ramp_normal_from} to ${data.ramp_amber_above} a week, amber above ${data.ramp_amber_above}, red above ${data.ramp_red_above}.`,
        "The dotted line in the Season view is fitness projected from the calendar plan: planned session length x your current load per hour for that sport.",
        sport?.starts_on ? `By sport: 42-day fitness per sport, same decay as intervals.icu, each line starting from 0 on ${fmtShortDate(sport.starts_on)}.` : "",
        sport?.check ? `Swim + bike + run is within ${sport.check.max_deviation_pct}% of the total over the last ${sport.check.days} days (gym and walk load are not in the per-sport lines).` : "",
      ]
        .filter(Boolean)
        .join(" ")
    : undefined;

  return (
    <Card
      icon={TrendingUp}
      title="Fitness, fatigue & form"
      info={info}
      meta={
        <span className="inline-flex flex-wrap items-center justify-end gap-2">
          <Toggle options={VIEWS} value={view} onChange={setView} />
          <Toggle options={RANGES} value={range} onChange={setRange} />
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
            <StatTile label="Fitness (CTL, 42d)" value={cur.ctl.toFixed(1)} spark={tail.map((p) => p.ctl)} sparkColor={LOAD_COLORS.ctl} />
            <StatTile label="Fatigue (ATL, 7d)" value={cur.atl.toFixed(1)} spark={tail.map((p) => p.atl)} sparkColor={LOAD_COLORS.atl} />
            <StatTile label="Form (TSB)" value={signed(cur.tsb)} spark={tail.map((p) => p.tsb)} sparkColor={LOAD_COLORS.tsb} />
            <StatTile
              label="CTL ramp, last 7d"
              value={data.ctl_ramp_7d != null ? signed(data.ctl_ramp_7d) : null}
              accent={rampFlag ? status[rampFlag] : undefined}
              badge={rampFlag && <StatusBadge tone={rampFlag} label={rampFlag === "critical" ? "RED" : "AMBER"} compact />}
              spark={rampSeries}
            />
          </div>
          <p className="mt-3 text-sm text-neutral-200">{formNote(cur.tsb, data.ctl_ramp_7d)}</p>

          {/* Two small multiples sharing the x-axis: form swings around 0 and
              needs its own scale and zones. */}
          <div className="mt-4 h-60">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} syncId="pmc" margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} hide />
                <YAxis {...yAxisProps} domain={[0, (m: number) => Math.ceil(m / (view === "sport" ? 5 : 20)) * (view === "sport" ? 5 : 20)]} tickCount={5} />
                {bands.map((b) => (
                  <ReferenceArea key={b.name} x1={b.x1} x2={b.x2} fill="rgba(255,255,255,0.05)" label={{ value: b.name, position: "insideTop", fill: ink.muted, fontSize: 10 }} />
                ))}
                {markers.map((m) => (
                  <ReferenceLine key={m.date} x={m.date} stroke={ink.muted} strokeDasharray="4 3" label={{ ...MARKER_LABEL, value: m.label }} />
                ))}
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number, name: string) => [v.toFixed(1), name]}
                />
                <Legend {...legendProps} verticalAlign="top" height={28} />
                {view === "total" && (
                  <Line type="monotone" dataKey="ctl" name="Fitness (CTL)" stroke={LOAD_COLORS.ctl} strokeWidth={2} dot={false} isAnimationActive={false} label={endLabel(lastIdx)} />
                )}
                {view === "total" && (
                  <Line type="monotone" dataKey="atl" name="Fatigue (ATL)" stroke={LOAD_COLORS.atl} strokeWidth={2} dot={false} isAnimationActive={false} label={endLabel(lastIdx)} />
                )}
                {view === "total" && projection.length > 0 && (
                  <Line
                    type="monotone"
                    dataKey="proj"
                    name="Fitness, projected from calendar plan"
                    stroke={LOAD_COLORS.ctl}
                    strokeWidth={2}
                    strokeDasharray="2 4"
                    dot={false}
                    isAnimationActive={false}
                    label={endLabel(rows.length - 1)}
                  />
                )}
                {view === "sport" &&
                  CTL_SPORTS.map((s) => (
                    <Line key={s} type="monotone" dataKey={s} name={`${cap(s)} fitness (CTL)`} stroke={SPORT_COLORS[s]} strokeWidth={2} dot={false} isAnimationActive={false} label={endLabel(lastIdx)} />
                  ))}
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
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} syncId="pmc" margin={MARGIN}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={40} />
                <YAxis {...yAxisProps} domain={[Math.floor(tsbMin / 10) * 10, Math.ceil(tsbMax / 10) * 10]} tickCount={5} />
                {FORM_ZONES.map((z) => (
                  <ReferenceArea key={z.label} y1={z.from} y2={z.to} fill={`${z.color}${z.alpha}`} ifOverflow="hidden" />
                ))}
                {markers.map((m) => (
                  <ReferenceLine key={m.date} x={m.date} stroke={ink.muted} strokeDasharray="4 3" label={{ ...MARKER_LABEL, value: m.label }} />
                ))}
                <Tooltip
                  {...tooltipProps}
                  labelFormatter={(d: string) => fmtShortDate(d)}
                  formatter={(v: number) => [v.toFixed(1), "Form (TSB)"]}
                />
                <ReferenceLine y={0} stroke={ink.baseline} />
                <Line type="monotone" dataKey="tsb" name="Form (TSB)" stroke={LOAD_COLORS.tsb} strokeWidth={2} dot={false} isAnimationActive={false} label={endLabel(lastIdx)} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <ChartTable
            columns={["Date", "Load", "CTL", "ATL", "TSB"]}
            rows={[...actual]
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
