import { useState } from "react";
import { Bandage, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { fmtShortDate, todayIso } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";

const REGION_SUGGESTIONS = [
  "Left knee (ITB)",
  "Right knee (ITB)",
  "Left hip",
  "Right hip",
  "Left calf / Achilles",
  "Right calf / Achilles",
  "Shin",
  "Foot",
  "Lower back",
  "Shoulder",
];

function painTone(p: number): BadgeTone {
  if (p >= 7) return "critical";
  if (p >= 4) return "serious";
  return "warning";
}

export default function InjuryLog() {
  const { data, error, reload } = usePolling(api.getInjuries);
  const [date, setDate] = useState(todayIso());
  const [region, setRegion] = useState("");
  const [pain, setPain] = useState(3);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const add = async () => {
    setFormError(null);
    if (!region.trim()) return setFormError("Pick or type a body region.");
    try {
      await api.createInjury({ date, body_region: region.trim(), pain_scale: pain, note: note.trim() || null });
      setNote("");
      reload();
    } catch (e) {
      setFormError((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    await api.deleteInjury(id);
    reload();
  };

  // Last 12 weeks of max pain, oldest -> newest, including empty weeks.
  const weekly = (() => {
    if (!data) return [];
    const byWeek = new Map(data.weekly.map((w) => [w.week_start, w]));
    const now = new Date();
    const monday = new Date(now);
    monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
    return Array.from({ length: 12 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() - 7 * (11 - i));
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      return { week: iso, entry: byWeek.get(iso) };
    });
  })();

  const cls = "rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-sm text-white placeholder:text-neutral-600";

  return (
    <Card icon={Bandage} title="Niggle log" meta={data ? `${data.entries.length} entries` : undefined}>
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {!data && !error && <Skeleton className="h-32 w-full" />}

      {data && (
        <>
          <div>
            <div className="mb-1 text-xs text-neutral-500">Worst pain per week, last 12 weeks</div>
            <div className="grid grid-cols-12 gap-1">
              {weekly.map(({ week, entry }) => (
                <div
                  key={week}
                  title={entry ? `${fmtShortDate(week)}: max ${entry.max_pain}/10 · ${entry.regions.join(", ")}` : `${fmtShortDate(week)}: nothing logged`}
                  className="flex h-8 items-center justify-center rounded text-xs tabular-nums"
                  style={{ background: entry ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.02)" }}
                >
                  <span className={entry ? "font-medium text-white" : "text-neutral-700"}>{entry ? entry.max_pain : "·"}</span>
                </div>
              ))}
            </div>
            <div className="mt-0.5 flex justify-between text-[10px] text-neutral-600">
              <span>{weekly[0] && fmtShortDate(weekly[0].week)}</span>
              <span>this week</span>
            </div>
          </div>

          <div className="mt-4 space-y-1.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <input type="date" className={`${cls} w-36`} value={date} onChange={(e) => setDate(e.target.value)} />
              <input className={`${cls} w-44`} list="injury-regions" placeholder="Body region" value={region} onChange={(e) => setRegion(e.target.value)} />
              <datalist id="injury-regions">
                {REGION_SUGGESTIONS.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>
              <label className="flex items-center gap-1.5 text-xs text-neutral-400">
                Pain
                <input type="range" min={1} max={10} value={pain} onChange={(e) => setPain(Number(e.target.value))} className="w-24 accent-neutral-300" />
                <span className="w-8 tabular-nums text-neutral-200">{pain}/10</span>
              </label>
            </div>
            <div className="flex gap-1.5">
              <input className={`${cls} flex-1`} placeholder="What happened / how it feels" value={note} onChange={(e) => setNote(e.target.value)} />
              <button onClick={add} className="rounded-md bg-white/[0.08] px-3 py-1 text-xs font-medium text-neutral-200 hover:bg-white/[0.14]">
                Log
              </button>
            </div>
            {formError && <p className="text-xs text-red-400">{formError}</p>}
          </div>

          <ul className="mt-3 max-h-72 divide-y divide-white/[0.05] overflow-y-auto">
            {data.entries.map((e) => (
              <li key={e.id} className="flex items-start justify-between gap-3 py-2">
                <div className="min-w-0">
                  <div className="text-sm text-neutral-200">
                    {e.body_region} <span className="text-xs text-neutral-500">· {fmtShortDate(e.date)}</span>
                  </div>
                  {e.note && <div className="text-xs text-neutral-400">{e.note}</div>}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge tone={painTone(e.pain_scale)} label={`${e.pain_scale}/10`} compact />
                  <button aria-label="Delete entry" onClick={() => remove(e.id)} className="text-neutral-600 hover:text-red-400">
                    <Trash2 size={12} />
                  </button>
                </div>
              </li>
            ))}
            {data.entries.length === 0 && (
              <li className="py-2 text-sm text-neutral-500">Nothing logged — ITB/knee entries also feed the Phase 1 gate check.</li>
            )}
          </ul>
        </>
      )}
    </Card>
  );
}
