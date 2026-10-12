import { useState } from "react";
import { AlertTriangle, CalendarCheck, RefreshCw } from "lucide-react";
import { api, ComplianceRollup } from "@/lib/api";
import { fmtShortDate, timeAgo, todayIso } from "@/lib/format";
import { SPORT_COLORS, status as statusColors } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";

const COLUMNS = [
  { key: "swim", label: "Swim" },
  { key: "bike", label: "Bike" },
  { key: "run", label: "Run" },
  { key: "gym", label: "Strength" },
] as const;

function PctCell({ r, threshold }: { r: ComplianceRollup | undefined; threshold: number }) {
  if (!r || r.planned === 0) return <span className="text-neutral-600">—</span>;
  if (r.pct == null) return <span className="text-neutral-500">{r.pending} planned</span>;
  const flagged = r.pct < threshold;
  return (
    <span className="inline-flex items-center gap-1">
      {flagged && <AlertTriangle size={12} style={{ color: statusColors.warning }} aria-label="below target" />}
      <span className={flagged ? "font-medium text-white" : "text-neutral-300"}>{Math.round(r.pct)}%</span>
      <span className="text-neutral-600">
        {r.completed}/{r.due}
      </span>
    </span>
  );
}

/** Week-by-week history only; the current week's sessions are the This week card on Overview. */
export default function ComplianceTracker() {
  const { data, error, reload } = usePolling(() => api.getCompliance(7, 0));
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const today = todayIso();
  const weeks = data?.weeks ?? [];
  const currentWeek = [...weeks].reverse().find((w) => w.week_start <= today);
  const threshold = data?.weeks[0]?.flag_threshold_pct ?? 80;

  const sync = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await api.syncPlan();
      await reload();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      icon={CalendarCheck}
      title="Session compliance"
      info={data?.note}
      meta={
        <span className="inline-flex items-center gap-2 text-xs">
          {data?.plan_synced_at && <span>plan synced {timeAgo(data.plan_synced_at + "Z")}</span>}
          <button onClick={sync} disabled={busy} aria-label="Re-sync plan from calendar" className="text-neutral-500 hover:text-neutral-200 disabled:opacity-40">
            <RefreshCw size={13} className={busy ? "animate-spin" : ""} />
          </button>
        </span>
      }
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {actionError && <p className="mb-2 text-sm text-red-400">{actionError}</p>}
      {!data && !error && (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
      )}

      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs tabular-nums">
            <thead className="text-neutral-500">
              <tr>
                <th className="pb-1.5 pr-2 font-medium">Week</th>
                {COLUMNS.map((c) => (
                  <th key={c.key} className="pb-1.5 pr-2 font-medium">
                    <span className="inline-flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: SPORT_COLORS[c.key] }} />
                      {c.label}
                    </span>
                  </th>
                ))}
                <th className="pb-1.5 pr-2 font-medium">Brick</th>
                <th className="pb-1.5 font-medium">All</th>
              </tr>
            </thead>
            <tbody>
              {[...weeks].reverse().map((w) => (
                <tr key={w.week_start} className="border-t border-white/[0.04]">
                  <td className="py-2 pr-2 text-neutral-300">
                    {fmtShortDate(w.week_start)}
                    {w.week_start === currentWeek?.week_start && <span className="ml-1 text-neutral-500">(now)</span>}
                  </td>
                  {COLUMNS.map((c) => (
                    <td key={c.key} className="py-2 pr-2">
                      <PctCell r={w.by_discipline[c.key]} threshold={threshold} />
                    </td>
                  ))}
                  <td className="py-2 pr-2">
                    {w.bricks.planned === 0 ? (
                      <span className="text-neutral-600">—</span>
                    ) : w.bricks.pct == null ? (
                      <span className="text-neutral-500">planned</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-neutral-300">
                        {w.bricks.flag && <AlertTriangle size={12} style={{ color: statusColors.warning }} />}
                        {w.bricks.completed}/{w.bricks.planned}
                      </span>
                    )}
                  </td>
                  <td className="py-2">
                    <PctCell r={w.overall} threshold={threshold} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
