import { useState } from "react";
import { AlertTriangle, BookOpen, Trash2 } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { fmtShortDate, todayIso } from "@/lib/format";
import { ink, status } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import { gridProps, legendProps, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

export default function StudyHours({ academicYear }: { academicYear: string }) {
  const { data, error, reload } = usePolling(() => api.getStudy(8));
  const { data: modules } = usePolling(() => api.getModules(academicYear), [academicYear]);
  const [date, setDate] = useState(todayIso());
  const [hours, setHours] = useState("");
  const [moduleId, setModuleId] = useState("");
  const [target, setTarget] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const log = async () => {
    setErr(null);
    const h = Number(hours);
    if (!h || h <= 0 || h > 24) return setErr("Hours between 0 and 24.");
    try {
      await api.logStudy({ date, hours: h, module_id: moduleId ? Number(moduleId) : null });
      setHours("");
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const saveTarget = async () => {
    setErr(null);
    const t = Number(target);
    if (!t || t <= 0) return setErr("Enter weekly hours.");
    try {
      await api.setStudyTarget(t);
      setTarget("");
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const chartData =
    data?.weeks.map((w) => ({
      week: fmtShortDate(w.week_start),
      Target: w.target_hours ?? 0,
      Logged: w.logged_hours,
    })) ?? [];
  const current = data?.weeks[data.weeks.length - 1];
  const moduleName = (id: number | null) => modules?.find((m) => m.id === id)?.name;
  const cls = "rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-sm text-white placeholder:text-neutral-600";

  return (
    <Card
      icon={BookOpen}
      title="Study hours"
      meta={current ? `this week ${current.logged_hours}h${current.target_hours ? ` / ${current.target_hours}h` : ""}` : undefined}
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {!data && !error && <Skeleton className="h-48 w-full" />}

      {data && (
        <>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="week" {...xAxisProps} />
                <YAxis {...yAxisProps} unit="h" />
                <Tooltip {...tooltipProps} formatter={(v: number) => `${v} h`} />
                <Legend {...legendProps} />
                <Bar dataKey="Target" fill={ink.baseline} radius={[4, 4, 0, 0]} maxBarSize={18} isAnimationActive={false} />
                <Bar dataKey="Logged" fill={ink.secondary} radius={[4, 4, 0, 0]} maxBarSize={18} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs tabular-nums">
            {data.weeks.map((w) => (
              <span key={w.week_start} className="inline-flex items-center gap-1 text-neutral-400">
                {fmtShortDate(w.week_start)}:
                {w.pct != null ? (
                  <>
                    {w.flag && <AlertTriangle size={11} style={{ color: status.warning }} aria-label="below target" />}
                    <span className={w.flag ? "font-medium text-white" : ""}>{Math.round(w.pct)}%</span>
                    {w.in_progress && <span className="text-neutral-600">(so far)</span>}
                  </>
                ) : (
                  <span className="text-neutral-600">no target</span>
                )}
              </span>
            ))}
          </div>

          <div className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-3">
            <div className="flex flex-wrap gap-1.5">
              <input type="date" className={`${cls} w-36`} value={date} onChange={(e) => setDate(e.target.value)} />
              <input className={`${cls} w-20`} placeholder="hours" value={hours} onChange={(e) => setHours(e.target.value)} />
              <select className={`${cls} max-w-[13rem]`} value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
                <option value="">Module (optional)</option>
                {modules?.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
              <button onClick={log} className="rounded-md bg-white/[0.08] px-3 py-1 text-xs font-medium text-neutral-200 hover:bg-white/[0.14]">
                Log
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-neutral-500">
              Weekly target:{" "}
              <span className="text-neutral-300">
                {data.manual_target_hours != null ? `${data.manual_target_hours}h (yours)` : "calendar study blocks"}
              </span>
              <input className={`${cls} w-16 py-0.5 text-xs`} placeholder="hours" value={target} onChange={(e) => setTarget(e.target.value)} />
              <button onClick={saveTarget} className="hover:text-neutral-200">
                Set
              </button>
              {data.manual_target_hours != null && (
                <button onClick={() => api.clearStudyTarget().then(reload)} className="hover:text-neutral-200">
                  Use calendar instead
                </button>
              )}
            </div>
            {err && <p className="text-xs text-red-400">{err}</p>}
          </div>

          {data.recent_logs.length > 0 && (
            <ul className="mt-2 max-h-32 divide-y divide-white/[0.04] overflow-y-auto text-xs">
              {data.recent_logs.map((l) => (
                <li key={l.id} className="flex items-center justify-between py-1 text-neutral-400">
                  <span>
                    {fmtShortDate(l.date)} · {l.hours}h{l.module_id ? ` · ${moduleName(l.module_id) ?? ""}` : ""}
                  </span>
                  <button aria-label="Delete log" onClick={() => api.deleteStudyLog(l.id).then(reload)} className="text-neutral-600 hover:text-red-400">
                    <Trash2 size={11} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">{data.note}</p>
        </>
      )}
    </Card>
  );
}
