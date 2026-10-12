import { HeartPulse } from "lucide-react";
import { api, GarminDailyMetric, RecoveryTrend } from "@/lib/api";
import { timeAgo, todayIso } from "@/lib/format";
import { status } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import Skeleton from "@/components/ui/Skeleton";

interface Tile {
  label: string;
  value: string | null;
  sub?: string | null;
}

// Garmin enums: "PRODUCTIVE_2" -> "Productive", "NO_STATUS"/"NONE" -> null.
function prettyStatus(s: string | null): string | null {
  if (!s || /^(none|no_status)$/i.test(s)) return null;
  const t = s.replace(/_\d+$/, "").replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

interface Note {
  tone: "good" | "warn" | "bad";
  text: string;
}

// Thresholds are Garmin's published bands (sleep score, body battery, training
// readiness) and its own 8h sleep target; HRV/RHR are judged against YOUR
// baseline, never an absolute number - HRV ms varies too much between people.
function recoveryNotes(m: GarminDailyMetric, trend: RecoveryTrend | null): Note[] {
  const notes: Note[] = [];
  const hrs = m.sleep_duration_min != null ? m.sleep_duration_min / 60 : null;
  if (hrs != null && hrs < 7) {
    notes.push({ tone: "bad", text: `Only ${hrs.toFixed(1)}h sleep — aim for 8h, and an earlier night before hard sessions.` });
  } else if (m.sleep_score != null && m.sleep_score < 60) {
    notes.push({ tone: "bad", text: `Sleep score ${m.sleep_score} is poor — protect tonight's sleep.` });
  } else if (m.sleep_score != null && m.sleep_score < 80) {
    notes.push({ tone: "warn", text: `Sleep score ${m.sleep_score} is only fair — a bit more sleep would help.` });
  } else if (m.sleep_score != null) {
    notes.push({ tone: "good", text: `Sleep was good (${m.sleep_score}).` });
  }

  if (m.training_readiness != null) {
    const r = m.training_readiness;
    if (r < 50) notes.push({ tone: "bad", text: `Readiness ${r} is low — keep today easy or take the rest day.` });
    else if (r < 75) notes.push({ tone: "warn", text: `Readiness ${r} is moderate — fine for steady work, skip the hardest efforts.` });
    else notes.push({ tone: "good", text: `Readiness ${r} is high — good day for quality work.` });
  }

  if (m.body_battery_high != null && m.body_battery_high < 76) {
    notes.push({ tone: "warn", text: `Body battery only peaked at ${m.body_battery_high} — you didn't fully recharge overnight.` });
  }

  const hrv = trend?.metrics.hrv;
  if (m.hrv_value != null && hrv?.rolling_7d != null) {
    const dev = ((m.hrv_value - hrv.rolling_7d) / hrv.rolling_7d) * 100;
    const building = hrv.baseline.value == null ? " (baseline still building)" : "";
    if (hrv.flag === "below_normal" || dev <= -15) {
      notes.push({ tone: "bad", text: `HRV ${Math.round(m.hrv_value)} ms is ${Math.abs(Math.round(dev))}% below your 7-day average (${hrv.rolling_7d} ms)${building} — a sign of accumulated fatigue; ease off.` });
    } else {
      notes.push({ tone: "good", text: `HRV ${Math.round(m.hrv_value)} ms is in line with your 7-day average (${hrv.rolling_7d} ms)${building}.` });
    }
  }

  const rhr = trend?.metrics.rhr;
  if (m.resting_hr != null && rhr?.baseline.value != null) {
    const diff = m.resting_hr - rhr.baseline.value;
    if (diff >= Math.max(3, 2 * (rhr.baseline.sd ?? 0))) {
      notes.push({ tone: "bad", text: `Resting HR ${m.resting_hr} is ${Math.round(diff)} bpm above your usual ${rhr.baseline.value} — possible fatigue, stress or illness.` });
    }
  }
  return notes;
}

const TONE_COLOR = { good: status.good, warn: status.warning, bad: status.critical };

export default function RecoveryMetrics() {
  const { data: metric, error, loaded } = usePolling(() => api.getGarminToday());
  // Trend is optional context for the notes - if it fails there are just fewer notes.
  const { data: trend } = usePolling(() => api.getRecoveryTrend());

  const tiles: Tile[] = metric
    ? [
        { label: "Sleep score", value: metric.sleep_score?.toString() ?? null },
        {
          label: "Sleep duration",
          value:
            metric.sleep_duration_min != null
              ? `${(metric.sleep_duration_min / 60).toFixed(1)}h`
              : null,
        },
        {
          label: "Body battery",
          value:
            metric.body_battery_high != null && metric.body_battery_low != null
              ? `${metric.body_battery_low}-${metric.body_battery_high}`
              : null,
        },
        { label: "Training readiness", value: metric.training_readiness?.toString() ?? null },
        { label: "Resting HR", value: metric.resting_hr != null ? `${metric.resting_hr} bpm` : null },
        {
          label: "HRV",
          value: metric.hrv_value != null ? `${Math.round(metric.hrv_value)} ms` : prettyStatus(metric.hrv_status),
          sub: metric.hrv_value != null ? prettyStatus(metric.hrv_status) : null,
        },
        {
          label: "VO2max (running)",
          value: metric.vo2max_running != null ? metric.vo2max_running.toString() : null,
        },
        { label: "Training status", value: prettyStatus(metric.training_status) },
      ]
    : [];

  const isStale = metric ? metric.date !== todayIso() : false;

  return (
    <Card
      icon={HeartPulse}
      title="Recovery"
      meta={metric ? `synced ${timeAgo(metric.updated_at)}` : "from Garmin"}
    >
      {/* A fetch/network error never clears `metric` above - a transient
          failure keeps showing the last good tiles instead of blanking. */}
      {error && (
        <p className="text-sm text-red-400">
          Couldn't refresh ({error}) — showing last known data.
        </p>
      )}

      {isStale && (
        <p className="mb-3 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-400">
          Last successful sync was for {metric!.date}, not today — the scheduled
          sync may be failing. Try a manual sync.
        </p>
      )}

      {!loaded && !error && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-7 w-12" />
            </div>
          ))}
        </div>
      )}

      {loaded && !metric && (
        <p className="text-sm text-neutral-500">
          No Garmin data yet — run the one-time login script, then a sync.
        </p>
      )}

      {metric && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4">
          {tiles.map((tile) => (
            <StatTile key={tile.label} label={tile.label} value={tile.value} sub={tile.sub} />
          ))}
        </div>
      )}

      {metric && (
        <ul className="mt-5 space-y-2 border-t border-white/[0.06] pt-4 text-sm text-neutral-300">
          {recoveryNotes(metric, trend).map((n) => (
            <li key={n.text} className="flex gap-2">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: TONE_COLOR[n.tone] }} />
              {n.text}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
