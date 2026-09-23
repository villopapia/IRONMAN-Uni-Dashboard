import { useState } from "react";
import { AlertTriangle, CalendarCheck, Link2, RefreshCw } from "lucide-react";
import { api, ComplianceRollup, PlannedSlot, SlotStatus, WeekCompliance } from "@/lib/api";
import { fmtShortDate, todayIso } from "@/lib/format";
import { timeAgo } from "@/lib/dates";
import { SPORT_COLORS, status as statusColors } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";

const COLUMNS = [
  { key: "swim", label: "Swim" },
  { key: "bike", label: "Bike" },
  { key: "run", label: "Run" },
  { key: "gym", label: "Strength" },
] as const;

const SLOT_TONE: Record<SlotStatus, [BadgeTone, string]> = {
  done: ["good", "Done"],
  moved: ["good", "Moved"],
  manual_done: ["good", "Done (manual)"],
  skipped: ["serious", "Skipped"],
  missed: ["critical", "Missed"],
  pending: ["neutral", "Planned"],
};

const BRICK_TONE: Record<string, [BadgeTone, string]> = {
  done: ["good", "Brick done"],
  split: ["warning", "Both legs, not back-to-back"],
  partial: ["serious", "One leg only"],
  missed: ["critical", "Brick missed"],
  pending: ["neutral", "Brick planned"],
  in_progress: ["neutral", "In progress"],
};

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

function SessionRow({ s, onSet }: { s: PlannedSlot; onSet: (ids: number[], v: "done" | "skipped" | null) => void }) {
  const [tone, label] = SLOT_TONE[s.status];
  const canOverride = s.status !== "done" && s.status !== "moved";
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className="flex min-w-0 items-start gap-2">
        <span
          className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
          style={{ background: SPORT_COLORS[s.discipline] ?? SPORT_COLORS.other }}
        />
        <div className="min-w-0">
          <div className="truncate text-sm text-neutral-200" title={s.titles.join(" / ")}>
            {s.is_brick && <Link2 size={12} className="mr-1 inline text-neutral-400" aria-label="brick" />}
            {s.titles[0]}
            {s.titles.length > 1 && <span className="text-neutral-500"> (+{s.titles.length - 1} overlapping)</span>}
          </div>
          <div className="text-xs text-neutral-500">
            {new Date(s.date + "T00:00:00").toLocaleDateString(undefined, { weekday: "short" })}
            {s.start_at ? ` ${s.start_at.slice(11, 16)}` : ""}
            {s.activity_name ? ` · ${s.activity_name}` : ""}
            {s.status === "moved" && s.activity_date ? ` (${fmtShortDate(s.activity_date.slice(0, 10))})` : ""}
          </div>
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <StatusBadge tone={tone} label={label} compact />
        {canOverride && (
          <div className="flex gap-2 text-[11px] text-neutral-500">
            {s.manual_status !== "done" && (
              <button className="hover:text-neutral-200" onClick={() => onSet(s.ids, "done")}>
                Mark done
              </button>
            )}
            {s.manual_status !== "skipped" && s.status !== "pending" && (
              <button className="hover:text-neutral-200" onClick={() => onSet(s.ids, "skipped")}>
                Skipped
              </button>
            )}
            {s.manual_status && (
              <button className="hover:text-neutral-200" onClick={() => onSet(s.ids, null)}>
                Clear
              </button>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

function WeekDetail({ week, onSet }: { week: WeekCompliance; onSet: (ids: number[], v: "done" | "skipped" | null) => void }) {
  const strength = Object.values(week.strength);
  return (
    <div className="mt-4 border-t border-white/[0.06] pt-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Week of {fmtShortDate(week.week_start)}
        </div>
        {week.overall.pct != null && (
          <span className="text-xs text-neutral-400">
            {week.overall.completed}/{week.overall.due} done{week.overall.pending ? ` · ${week.overall.pending} to go` : ""}
          </span>
        )}
      </div>

      {week.bricks.days.map((b) => {
        const [tone, label] = BRICK_TONE[b.status] ?? ["neutral", b.status];
        return (
          <div key={b.date} className="mt-2 flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-sm">
            <span className="flex items-center gap-1.5 text-neutral-300">
              <Link2 size={14} className="text-neutral-400" />
              Saturday brick · {fmtShortDate(b.date)}
              {b.bike_activity && b.run_activity && (
                <span className="text-xs text-neutral-500">
                  {" "}
                  ({b.bike_activity} → {b.run_activity})
                </span>
              )}
            </span>
            <StatusBadge tone={tone} label={label} compact />
          </div>
        );
      })}

      {strength.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-400">
          {strength.map((st) => (
            <span key={st.label}>
              {st.label}: {st.completed}/{st.planned}
              {st.flag && <AlertTriangle size={11} className="ml-1 inline" style={{ color: statusColors.warning }} />}
            </span>
          ))}
        </div>
      )}

      {week.sessions.length === 0 ? (
        <p className="mt-2 text-sm text-neutral-500">No tagged training sessions in the calendar this week.</p>
      ) : (
        <ul className="mt-1 divide-y divide-white/[0.05]">
          {week.sessions.map((s) => (
            <SessionRow key={s.ids.join("-")} s={s} onSet={onSet} />
          ))}
        </ul>
      )}

      {week.extras.length > 0 && (
        <p className="mt-2 text-xs text-neutral-500">
          Unplanned: {week.extras.map((e) => `${e.name} (${Math.round(e.duration_min)}m)`).join(", ")}
        </p>
      )}
    </div>
  );
}

export default function ComplianceTracker() {
  const { data, error, reload } = usePolling(() => api.getCompliance(6, 1));
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const today = todayIso();
  const weeks = data?.weeks ?? [];
  const currentWeek = [...weeks].reverse().find((w) => w.week_start <= today);
  const selectedWeek = weeks.find((w) => w.week_start === selected) ?? currentWeek;
  const threshold = data?.weeks[0]?.flag_threshold_pct ?? 80;

  const setStatus = async (ids: number[], v: "done" | "skipped" | null) => {
    setActionError(null);
    try {
      await api.setSessionStatus(ids, v);
      await reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  };

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
        <>
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
                {[...weeks].reverse().map((w) => {
                  const isSel = selectedWeek?.week_start === w.week_start;
                  return (
                    <tr
                      key={w.week_start}
                      onClick={() => setSelected(w.week_start)}
                      className={`cursor-pointer border-t border-white/[0.04] ${isSel ? "bg-white/[0.05]" : "hover:bg-white/[0.02]"}`}
                    >
                      <td className="py-1.5 pr-2 text-neutral-300">
                        {fmtShortDate(w.week_start)}
                        {w.week_start === currentWeek?.week_start && <span className="ml-1 text-neutral-500">(now)</span>}
                      </td>
                      {COLUMNS.map((c) => (
                        <td key={c.key} className="py-1.5 pr-2">
                          <PctCell r={w.by_discipline[c.key]} threshold={threshold} />
                        </td>
                      ))}
                      <td className="py-1.5 pr-2">
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
                      <td className="py-1.5">
                        <PctCell r={w.overall} threshold={threshold} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {selectedWeek && <WeekDetail week={selectedWeek} onSet={setStatus} />}

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">{data.note}</p>
        </>
      )}
    </Card>
  );
}
