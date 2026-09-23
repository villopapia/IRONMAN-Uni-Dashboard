import { useState } from "react";
import { CalendarClock, Check, Trash2 } from "lucide-react";
import { api, Deadline, DeadlineKind } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";

const KIND_LABEL: Record<DeadlineKind, string> = {
  assignment: "Assignment",
  exam: "Exam",
  test: "Test",
  other: "Other",
};

function proximity(d: Deadline): [BadgeTone, string] {
  if (d.overdue) return ["critical", `${Math.ceil(-d.days_until)}d overdue`];
  if (d.days_until < 1) return ["serious", "Due today"];
  if (d.days_until <= 7) return ["warning", `${Math.ceil(d.days_until)}d`];
  return ["neutral", `${Math.ceil(d.days_until)}d`];
}

function AddDeadline({ academicYear, onAdded }: { academicYear: string; onAdded: () => void }) {
  const { data: modules } = usePolling(() => api.getModules(academicYear), [academicYear]);
  const [title, setTitle] = useState("");
  const [moduleId, setModuleId] = useState<string>("");
  const [assessmentId, setAssessmentId] = useState<string>("");
  const [kind, setKind] = useState<DeadlineKind>("assignment");
  const [due, setDue] = useState("");
  const [weight, setWeight] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const module = modules?.find((m) => m.id === Number(moduleId));

  const submit = async () => {
    setErr(null);
    if (!title.trim() || !due) return setErr("Title and due date/time are required.");
    const w = weight ? Number(weight) : null;
    if (w != null && (!isFinite(w) || w < 0 || w > 100)) return setErr("Weight is a % of the module (0–100).");
    try {
      await api.createDeadline({
        title: title.trim(),
        due_at: due.length === 10 ? `${due}T23:59:00` : due,
        kind,
        module_id: moduleId ? Number(moduleId) : null,
        assessment_id: assessmentId ? Number(assessmentId) : null,
        weight_pct: w,
      });
      setTitle("");
      setDue("");
      setWeight("");
      setAssessmentId("");
      onAdded();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const cls = "rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-sm text-white placeholder:text-neutral-600";
  return (
    <div className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Add a deadline</div>
      <div className="flex flex-wrap gap-1.5">
        <input className={`${cls} min-w-0 flex-1`} placeholder="Title (e.g. PLP coursework 1)" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select className={cls} value={kind} onChange={(e) => setKind(e.target.value as DeadlineKind)}>
          {Object.entries(KIND_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <select className={`${cls} max-w-[14rem]`} value={moduleId} onChange={(e) => { setModuleId(e.target.value); setAssessmentId(""); }}>
          <option value="">Module (optional)</option>
          {modules?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        {module && module.assessments.length > 0 && (
          <select className={cls} value={assessmentId} onChange={(e) => setAssessmentId(e.target.value)}>
            <option value="">Assessment (optional)</option>
            {module.assessments.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.weight_pct}%)
              </option>
            ))}
          </select>
        )}
        <input type="datetime-local" className={cls} value={due} onChange={(e) => setDue(e.target.value)} />
        {!assessmentId && (
          <input className={`${cls} w-20`} placeholder="weight %" value={weight} onChange={(e) => setWeight(e.target.value)} />
        )}
        <button onClick={submit} className="rounded-md bg-white/[0.08] px-3 py-1 text-xs font-medium text-neutral-200 hover:bg-white/[0.14]">
          Add
        </button>
      </div>
      {err && <p className="text-xs text-red-400">{err}</p>}
    </div>
  );
}

export default function DeadlineTracker({ academicYear }: { academicYear: string }) {
  const { data, error, reload } = usePolling(api.getDeadlines);

  const act = async (fn: () => Promise<unknown>) => {
    await fn();
    reload();
  };

  const next14 = data?.filter((d) => !d.overdue && d.days_until <= 14).length ?? 0;

  return (
    <Card
      icon={CalendarClock}
      title="Deadlines"
      meta={data ? `${data.length} open · ${next14} in the next 2 weeks` : undefined}
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {!data && !error && (
        <div className="space-y-2">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-full" />
        </div>
      )}

      {data && data.length === 0 && (
        <p className="text-sm text-neutral-500">
          No deadlines entered. Your calendar only has study blocks ([ASSIGN], [EXAM]), not due dates — so these
          are manual entry.
        </p>
      )}

      {data && data.length > 0 && (
        <ul className="divide-y divide-white/[0.05]">
          {data.map((d) => {
            const [tone, label] = proximity(d);
            return (
              <li key={d.id} className="flex items-start justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <div className="text-sm text-neutral-200">{d.title}</div>
                  <div className="text-xs text-neutral-500">
                    {KIND_LABEL[d.kind]}
                    {d.module_name ? ` · ${d.module_name}` : ""}
                    {d.weight_pct != null ? ` · ${d.weight_pct}% of module` : ""} ·{" "}
                    {fmtShortDate(d.due_at.slice(0, 10))} {d.due_at.slice(11, 16)}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge tone={tone} label={label} compact />
                  <button
                    aria-label="Mark submitted"
                    title="Mark submitted"
                    onClick={() => act(() => api.updateDeadline(d.id, { status: "submitted" }))}
                    className="text-neutral-500 hover:text-green-400"
                  >
                    <Check size={14} />
                  </button>
                  <button
                    aria-label="Delete"
                    title="Delete"
                    onClick={() => act(() => api.deleteDeadline(d.id))}
                    className="text-neutral-600 hover:text-red-400"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <AddDeadline academicYear={academicYear} onAdded={reload} />
    </Card>
  );
}
