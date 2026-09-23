import { useState } from "react";
import { Check, ChevronDown, ChevronRight, ListChecks, Trash2 } from "lucide-react";
import { api, ModulePrep } from "@/lib/api";
import { ink, status } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";

function ModuleRow({ m, onChange }: { m: ModulePrep; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"topic" | "past_paper">("topic");

  const add = async () => {
    if (!title.trim()) return;
    await api.addPrepItem({ module_id: m.module_id, title: title.trim(), kind });
    setTitle("");
    onChange();
  };

  const pct = m.pct ?? 0;
  return (
    <li className="py-2.5">
      <button className="flex w-full items-center justify-between gap-3 text-left" onClick={() => setOpen(!open)}>
        <span className="flex min-w-0 items-center gap-1.5 text-sm text-neutral-200">
          {open ? <ChevronDown size={14} className="text-neutral-500" /> : <ChevronRight size={14} className="text-neutral-500" />}
          <span className="truncate">{m.module_name}</span>
        </span>
        <span className="shrink-0 text-xs tabular-nums text-neutral-400">
          {m.total > 0 ? `${m.done}/${m.total} · ${Math.round(pct)}%` : "no checklist yet"}
        </span>
      </button>
      {/* Meter: fill on a lighter track of the same neutral ramp. */}
      <div className="mt-1.5 h-1.5 rounded-full" style={{ background: ink.gridline }}>
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: pct >= 100 ? status.good : ink.secondary }}
        />
      </div>
      {m.total > 0 && (
        <div className="mt-1 text-[11px] text-neutral-500">
          Topics {m.topics_done}/{m.topics_total} · Past papers {m.papers_done}/{m.papers_total}
        </div>
      )}

      {open && (
        <div className="mt-2 pl-5">
          <ul className="space-y-1">
            {m.items.map((it) => (
              <li key={it.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="flex min-w-0 items-center gap-2">
                  <button
                    aria-label={it.done ? `Mark ${it.title} not done` : `Mark ${it.title} done`}
                    onClick={() => api.togglePrepItem(it.id, !it.done).then(onChange)}
                    className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border border-white/20"
                    style={it.done ? { background: status.good, borderColor: status.good } : undefined}
                  >
                    {it.done && <Check size={10} className="text-white" strokeWidth={3} />}
                  </button>
                  <span className={`truncate ${it.done ? "text-neutral-500 line-through" : "text-neutral-300"}`}>{it.title}</span>
                  <span className="shrink-0 text-[10px] uppercase tracking-wide text-neutral-600">
                    {it.kind === "past_paper" ? "paper" : "topic"}
                  </span>
                </span>
                <button aria-label="Delete item" onClick={() => api.deletePrepItem(it.id).then(onChange)} className="text-neutral-700 hover:text-red-400">
                  <Trash2 size={11} />
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-2 flex gap-1.5">
            <input
              className="min-w-0 flex-1 rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-xs text-white placeholder:text-neutral-600"
              placeholder="Add a topic or past paper"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
            />
            <select
              className="rounded-md border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-xs text-white"
              value={kind}
              onChange={(e) => setKind(e.target.value as "topic" | "past_paper")}
            >
              <option value="topic">Topic</option>
              <option value="past_paper">Past paper</option>
            </select>
            <button onClick={add} className="rounded-md bg-white/[0.08] px-2 py-0.5 text-xs text-neutral-200 hover:bg-white/[0.14]">
              Add
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

export default function ExamPrepCoverage({ academicYear }: { academicYear: string }) {
  const { data, error, reload } = usePolling(() => api.getPrep(academicYear), [academicYear]);
  return (
    <Card icon={ListChecks} title="Exam prep coverage" meta="topics + past papers">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {!data && !error && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-6 w-full" />
          ))}
        </div>
      )}
      {data && (
        <>
          <ul className="divide-y divide-white/[0.05]">
            {data.map((m) => (
              <ModuleRow key={m.module_id} m={m} onChange={reload} />
            ))}
          </ul>
          <p className="mt-3 text-xs text-neutral-500">
            Coverage = ticked items / all items on the module's checklist — the same topics + past-papers
            pattern as your COM1009 prep. Click a module to build its list.
          </p>
        </>
      )}
    </Card>
  );
}
