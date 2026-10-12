import { HeartPulse } from "lucide-react";
import { Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, GarminDailyMetric, ReadinessMetric } from "@/lib/api";
import { fmtShortDate, timeAgo, todayIso } from "@/lib/format";
import { ink, status } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { FLAG_BADGE } from "@/components/ui/StatusBadge";
import { ChartTable, tooltipProps } from "@/components/ui/chart";

// One neutral line per metric: the badge carries the status, so the sparkline
// stays in ink rather than repeating it in color.
function Spark({ m }: { m: ReadinessMetric }) {
  const series = m.series ?? [];
  if (!series.some((p) => p.value != null)) {
    return <div className="flex h-10 items-center text-xs text-neutral-600">No readings in the last 28 days</div>;
  }
  return (
    <div className="h-10">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 4, right: 2, left: 2, bottom: 4 }}>
          <XAxis dataKey="date" hide />
          <YAxis hide domain={["dataMin", "dataMax"]} />
          {m.band && <ReferenceArea y1={m.band[0]} y2={m.band[1]} fill="rgba(255,255,255,0.07)" ifOverflow="extendDomain" />}
          <Tooltip
            {...tooltipProps}
            allowEscapeViewBox={{ x: false, y: true }}
            wrapperStyle={{ zIndex: 10 }}
            labelFormatter={(d: string) => fmtShortDate(d)}
            formatter={(v: number) => [`${v} ${m.unit}`, m.label]}
          />
          <Line dataKey="value" stroke={ink.secondary} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// Garmin enums: "PRODUCTIVE_2" -> "Productive", "NO_STATUS"/"NONE" -> null.
function prettyStatus(s: string | null): string | null {
  if (!s || /^(none|no_status)$/i.test(s)) return null;
  const t = s.replace(/_\d+$/, "").replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// Advice on the Garmin-only numbers, using Garmin's published bands. Nothing here
// about sleep duration, HRV or resting HR: the rows above already judge those.
function garminNotes(m: GarminDailyMetric): { tone: keyof typeof NOTE_COLOR; text: string }[] {
  const notes: { tone: keyof typeof NOTE_COLOR; text: string }[] = [];
  if (m.sleep_score != null && m.sleep_score < 60) notes.push({ tone: "bad", text: `Sleep score ${m.sleep_score} is poor: protect tonight's sleep.` });
  else if (m.sleep_score != null && m.sleep_score < 80) notes.push({ tone: "warn", text: `Sleep score ${m.sleep_score} is only fair.` });
  const r = m.training_readiness;
  if (r != null && r < 50) notes.push({ tone: "bad", text: `Training readiness ${r} is low: keep today easy or take the rest day.` });
  else if (r != null && r < 75) notes.push({ tone: "warn", text: `Training readiness ${r} is moderate: fine for steady work, skip the hardest efforts.` });
  else if (r != null) notes.push({ tone: "good", text: `Training readiness ${r} is high: a good day for quality work.` });
  if (m.body_battery_high != null && m.body_battery_high < 76) notes.push({ tone: "warn", text: `Body Battery only peaked at ${m.body_battery_high}: you did not fully recharge overnight.` });
  return notes;
}

const NOTE_COLOR = { good: status.good, warn: status.warning, bad: status.critical };

// The Garmin numbers that have no row above, as one compact line of small tiles.
function GarminRow() {
  const { data: m } = usePolling(() => api.getGarminToday());
  if (!m) return null;
  const tiles: [string, string | null][] = [
    ["Sleep score", m.sleep_score?.toString() ?? null],
    ["Body Battery", m.body_battery_high != null && m.body_battery_low != null ? `${m.body_battery_low}-${m.body_battery_high}` : null],
    ["Training readiness", m.training_readiness?.toString() ?? null],
    ["VO2max (running)", m.vo2max_running?.toString() ?? null],
    ["Training status", prettyStatus(m.training_status)],
  ];
  const stale = m.date !== todayIso();
  return (
    <div className="mt-2 border-t border-white/[0.06] pt-3">
      <div className={`mb-2 text-[11px] ${stale ? "text-amber-400" : "text-neutral-500"}`}>
        Garmin, {stale ? `last synced for ${fmtShortDate(m.date)}, not today` : `synced ${timeAgo(m.updated_at)}`}
      </div>
      <div className="grid grid-cols-3 gap-x-3 gap-y-2 sm:grid-cols-5">
        {tiles.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <div className="truncate text-[11px] text-neutral-500" title={label}>
              {label}
            </div>
            <div className="truncate text-sm font-semibold tabular-nums text-white">{value ?? "—"}</div>
          </div>
        ))}
      </div>
      <ul className="mt-3 space-y-1.5 text-xs text-neutral-300">
        {garminNotes(m).map((n) => (
          <li key={n.text} className="flex gap-2">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: NOTE_COLOR[n.tone] }} />
            {n.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The per-metric detail; the action line that sums it up is the Readiness tile in the KPI strip. */
export default function Readiness() {
  const { data, error } = usePolling(() => api.getReadiness());
  const metrics = data?.metrics ?? [];

  return (
    <Card
      icon={HeartPulse}
      title="Readiness detail"
      info={data ? `Sparklines: daily readings, last 28 days. ${data.note}` : undefined}
      meta={data ? fmtShortDate(data.date) : undefined}
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-40 w-full" />}

      {data && (
        <>
          <ul className="divide-y divide-white/[0.05]">
            {metrics.map((m) => {
              const [tone, label] = FLAG_BADGE[m.status] ?? FLAG_BADGE.no_data;
              return (
                <li key={m.key} className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto] items-center gap-3 py-2">
                  <div className="min-w-0">
                    <div className="text-sm text-neutral-200">{m.label}</div>
                    <div className="text-lg font-semibold tabular-nums text-white">
                      {m.value != null ? m.value : "—"}
                      {m.value != null && <span className="ml-1 text-xs font-normal text-neutral-500">{m.unit}</span>}
                    </div>
                    <div className="text-xs text-neutral-500">{m.basis}</div>
                  </div>
                  <Spark m={m} />
                  <StatusBadge tone={tone} label={label} compact />
                </li>
              );
            })}
          </ul>

          <GarminRow />

          <ChartTable
            columns={["Date", ...metrics.map((m) => `${m.label} (${m.unit})`)]}
            rows={[...(metrics[0]?.series ?? [])]
              .map((p, i) => [fmtShortDate(p.date), ...metrics.map((m) => m.series?.[i]?.value ?? "—")])
              .reverse()}
            summary="Show daily readings as table"
          />
        </>
      )}
    </Card>
  );
}
