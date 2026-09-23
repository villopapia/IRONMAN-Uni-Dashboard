import { useState } from "react";
import { Bike, Check } from "lucide-react";
import { api, Milestone } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { status } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";

function dueLabel(m: Milestone) {
  if (m.done) return <StatusBadge tone="good" label={m.done_on ? `Done ${fmtShortDate(m.done_on)}` : "Done"} compact />;
  if (m.target_date == null) return <StatusBadge tone="warning" label="No date set" compact />;
  if (m.overdue) return <StatusBadge tone="critical" label={`${-m.days_remaining!}d overdue`} compact />;
  return <span className="text-xs text-neutral-400">{m.days_remaining}d · {fmtShortDate(m.target_date)}</span>;
}

export default function EquipmentMilestones() {
  const { data: milestones, error, setData } = usePolling(api.getMilestones);
  const [editing, setEditing] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const patch = async (id: number, update: Parameters<typeof api.updateMilestone>[1]) => {
    setSaveError(null);
    try {
      const updated = await api.updateMilestone(id, update);
      setData((prev) => prev?.map((m) => (m.id === id ? updated : m)) ?? prev);
    } catch (e) {
      setSaveError((e as Error).message);
    }
  };

  const doneCount = milestones?.filter((m) => m.done).length ?? 0;

  return (
    <Card
      icon={Bike}
      title="Equipment & milestones"
      meta={milestones ? `${doneCount}/${milestones.length} done` : undefined}
    >
      <p className="-mt-2 mb-3 text-xs text-neutral-500">
        These gate Phase 2+ bike specificity — all Sheffield riding is trainer-only until the bike lands.
      </p>
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {saveError && <p className="mb-2 text-sm text-red-400">Save failed: {saveError}</p>}

      {!milestones && !error && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
      )}

      {milestones && (
        <ul className="divide-y divide-white/[0.06]">
          {milestones.map((m) => (
            <li key={m.id} className="py-2.5">
              <div className="flex items-start gap-3">
                <button
                  aria-label={m.done ? `Mark ${m.title} not done` : `Mark ${m.title} done`}
                  onClick={() => patch(m.id, { done: !m.done })}
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-white/20"
                  style={m.done ? { background: status.good, borderColor: status.good } : undefined}
                >
                  {m.done && <Check size={12} className="text-white" strokeWidth={3} />}
                </button>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-sm ${m.done ? "text-neutral-500 line-through" : "text-neutral-200"}`}>
                      {m.title}
                    </span>
                    {dueLabel(m)}
                  </div>
                  {m.note && <p className="mt-0.5 text-xs leading-relaxed text-neutral-500">{m.note}</p>}
                  {editing === m.id ? (
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <input
                        type="date"
                        defaultValue={m.target_date ?? ""}
                        className="rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-xs text-white"
                        onChange={(e) => patch(m.id, { target_date: e.target.value || null })}
                      />
                      <button className="text-[11px] text-neutral-400 hover:text-neutral-200" onClick={() => setEditing(null)}>
                        Done
                      </button>
                    </div>
                  ) : (
                    <button
                      className="mt-0.5 text-[11px] text-neutral-500 hover:text-neutral-300"
                      onClick={() => setEditing(m.id)}
                    >
                      {m.target_date ? "Change target date" : "Set target date"}
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
