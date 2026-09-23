import { useEffect, useState } from "react";
import { HeartPulse } from "lucide-react";
import { api, GarminDailyMetric } from "@/lib/api";
import { timeAgo } from "@/lib/dates";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import Skeleton from "@/components/ui/Skeleton";

interface Tile {
  label: string;
  value: string | null;
}

export default function RecoveryMetrics() {
  const [metric, setMetric] = useState<GarminDailyMetric | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const load = () =>
      api
        .getGarminToday()
        .then((m) => {
          setMetric(m);
          setLoaded(true);
        })
        .catch((err) => setError(err.message));

    load();
    const id = setInterval(load, 6 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

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
          value:
            metric.hrv_value != null
              ? `${Math.round(metric.hrv_value)}ms${metric.hrv_status ? ` · ${metric.hrv_status}` : ""}`
              : metric.hrv_status,
        },
        {
          label: "VO2max (running)",
          value: metric.vo2max_running != null ? metric.vo2max_running.toString() : null,
        },
        { label: "Training status", value: metric.training_status },
      ]
    : [];

  const isStale = metric ? metric.date !== new Date().toISOString().slice(0, 10) : false;

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
            <StatTile key={tile.label} label={tile.label} value={tile.value} />
          ))}
        </div>
      )}
    </Card>
  );
}
