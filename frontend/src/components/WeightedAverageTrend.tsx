import { useState } from "react";
import { LineChart as LineIcon } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ModuleOut, WeightedHistory } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { ink, status, surface } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import { ChartTable, gridProps, tooltipProps, xAxisProps, yAxisProps } from "@/components/ui/chart";

function LevelCreditsForm({ module, onSaved }: { module: ModuleOut; onSaved: () => void }) {
  const [level, setLevel] = useState<string>(module.fheq_level?.toString() ?? "");
  const [credits, setCredits] = useState<string>(module.credits?.toString() ?? "");
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    const l = Number(level);
    const c = Number(credits);
    if (![1, 2, 3].includes(l) || !c || c <= 0) return setErr("Level 1–3 and a credit value.");
    try {
      await api.updateModule(module.id, { fheq_level: l, credits: c });
      onSaved();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const cls = "rounded-md border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-xs text-white";
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-1.5">
      <span className="text-xs text-neutral-300">{module.name}</span>
      <span className="flex items-center gap-1.5">
        <select className={cls} value={level} onChange={(e) => setLevel(e.target.value)} aria-label="FHEQ level">
          <option value="">Level</option>
          <option value="1">L1</option>
          <option value="2">L2</option>
          <option value="3">L3</option>
        </select>
        <input className={`${cls} w-16`} placeholder="credits" value={credits} onChange={(e) => setCredits(e.target.value)} />
        <button className="rounded-md bg-white/[0.08] px-2 py-0.5 text-[11px] text-neutral-200 hover:bg-white/[0.14]" onClick={save}>
          Save
        </button>
      </span>
      {err && <span className="w-full text-[11px] text-red-400">{err}</span>}
    </li>
  );
}

export default function WeightedAverageTrend({ academicYear }: { academicYear: string }) {
  const { data, error, reload } = usePolling(() => api.getWeightedHistory(academicYear), [academicYear]);
  const { data: modules, reload: reloadModules } = usePolling(() => api.getModules(academicYear), [academicYear]);

  const history: WeightedHistory | null = data;
  const series = history?.snapshots ?? [];
  const missing = modules?.filter((m) => m.fheq_level == null || m.credits == null) ?? [];
  const threshold = history?.first_threshold_pct ?? 70;
  const latest = series.length ? series[series.length - 1] : null;
  const gap = latest ? latest.weighted_average_pct - threshold : null;

  const refresh = () => {
    reload();
    reloadModules();
  };

  return (
    <Card icon={LineIcon} title="Weighted average trajectory" meta={academicYear}>
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error})</p>}
      {!history && !error && <Skeleton className="h-48 w-full" />}

      {history && (
        <>
          {series.length > 0 ? (
            <>
              <div className="flex items-baseline gap-3">
                <span className="text-3xl font-bold text-white">{latest!.weighted_average_pct.toFixed(1)}%</span>
                <span className="text-sm text-neutral-400">
                  {gap! >= 0 ? `${gap!.toFixed(1)} pts above` : `${Math.abs(gap!).toFixed(1)} pts below`} the {threshold}% First line
                </span>
              </div>
              <div className="mt-3 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={series} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                    <CartesianGrid {...gridProps} />
                    <XAxis dataKey="recorded_on" {...xAxisProps} tickFormatter={fmtShortDate} minTickGap={30} />
                    <YAxis {...yAxisProps} domain={[40, 100]} ticks={[40, 50, 60, 70, 80, 90, 100]} unit="%" />
                    <Tooltip
                      {...tooltipProps}
                      labelFormatter={(d: string) => fmtShortDate(d)}
                      formatter={(v: number) => [`${v.toFixed(1)}%`, "Weighted average"]}
                    />
                    <ReferenceLine
                      y={threshold}
                      stroke={status.good}
                      label={{ value: "First (70%)", fill: ink.secondary, fontSize: 10, position: "insideTopRight" }}
                    />
                    <ReferenceLine y={60} stroke={ink.baseline} label={{ value: "2:1", fill: ink.muted, fontSize: 10, position: "insideTopRight" }} />
                    <Line
                      type="monotone"
                      dataKey="weighted_average_pct"
                      stroke={ink.primary}
                      strokeWidth={2}
                      dot={{ r: 4, fill: ink.primary, stroke: surface.card, strokeWidth: 2 }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <ChartTable
                columns={["Date", "Weighted avg", "Band", "Modules counted"]}
                rows={[...series].reverse().map((s) => [
                  fmtShortDate(s.recorded_on),
                  `${s.weighted_average_pct.toFixed(1)}%`,
                  s.classification_estimate ?? "—",
                  s.modules_counted,
                ])}
              />
            </>
          ) : (
            <div className="flex h-32 flex-col items-center justify-center rounded-lg border border-dashed border-white/[0.06] text-center text-xs text-neutral-500">
              <span>No weighted average yet — needs at least one mark on a module with a confirmed level + credits.</span>
              <span className="mt-1 text-neutral-600">The line starts from the first mark and moves whenever one changes.</span>
            </div>
          )}

          {missing.length > 0 && (
            <div className="mt-4 rounded-lg bg-amber-500/[0.06] px-3 py-2">
              <div className="text-xs font-medium text-amber-300/90">
                {missing.length} module{missing.length > 1 ? "s" : ""} excluded — FHEQ level and credits not confirmed yet
              </div>
              <ul className="mt-1 divide-y divide-white/[0.04]">
                {missing.map((m) => (
                  <LevelCreditsForm key={m.id} module={m} onSaved={refresh} />
                ))}
              </ul>
            </div>
          )}

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">{history.note}</p>
        </>
      )}
    </Card>
  );
}
