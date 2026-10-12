import { HeartPulse } from "lucide-react";
import { Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ReadinessMetric } from "@/lib/api";
import { fmtShortDate } from "@/lib/format";
import { ink } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";
import { ChartTable, tooltipProps } from "@/components/ui/chart";

const STATUS: Record<ReadinessMetric["status"], [BadgeTone, string]> = {
  pass: ["good", "PASS"],
  amber: ["warning", "AMBER"],
  red: ["critical", "RED"],
  no_data: ["neutral", "NO DATA"],
};

// One neutral line per metric: the badge carries the status, so the sparkline
// stays in ink rather than repeating it in color.
function Spark({ m }: { m: ReadinessMetric }) {
  const series = m.series ?? [];
  if (!series.some((p) => p.value != null)) {
    return <div className="flex h-10 items-center text-xs text-neutral-600">No readings in the last 28 days</div>;
  }
  return (
    <div className="h-10">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 4, right: 2, left: 2, bottom: 4 }}>
          <XAxis dataKey="date" hide />
          <YAxis hide domain={["dataMin", "dataMax"]} />
          {m.band && <ReferenceArea y1={m.band[0]} y2={m.band[1]} fill="rgba(255,255,255,0.07)" ifOverflow="extendDomain" />}
          <Tooltip
            {...tooltipProps}
            allowEscapeViewBox={{ x: false, y: true }}
            wrapperStyle={{ zIndex: 10 }}
            labelFormatter={(d: string) => fmtShortDate(d)}
            formatter={(v: number) => [`${v} ${m.unit}`, m.label]}
          />
          <Line dataKey="value" stroke={ink.secondary} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function Readiness() {
  const { data, error } = usePolling(() => api.getReadiness());
  const metrics = data?.metrics ?? [];
  const lists: [string, string[]][] = [
    ["Red", data?.red ?? []],
    ["Amber", data?.amber ?? []],
    ["No data", data?.no_data ?? []],
  ];

  return (
    <Card icon={HeartPulse} title="Readiness" meta={data ? fmtShortDate(data.date) : undefined} className="lg:col-span-2">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-40 w-full" />}

      {data && (
        <>
          <p className="text-lg font-semibold text-white">{data.action}</p>
          <p className="mt-0.5 text-xs text-neutral-400">
            {lists
              .filter(([, names]) => names.length > 0)
              .map(([name, names]) => `${name}: ${names.join(", ")}`)
              .join(" · ") || "All metrics pass."}
          </p>

          <ul className="mt-3 divide-y divide-white/[0.05]">
            {metrics.map((m) => {
              const [tone, label] = STATUS[m.status] ?? ["neutral", "NO DATA"];
              return (
                <li key={m.key} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto] items-center gap-4 py-2">
                  <div className="min-w-0">
                    <div className="text-sm text-neutral-200">{m.label}</div>
                    <div className="text-lg font-semibold tabular-nums text-white">
                      {m.value != null ? m.value : "—"}
                      {m.value != null && <span className="ml-1 text-xs font-normal text-neutral-500">{m.unit}</span>}
                    </div>
                    <div className="text-xs text-neutral-500">{m.basis}</div>
                  </div>
                  <Spark m={m} />
                  <StatusBadge tone={tone} label={label} compact />
                </li>
              );
            })}
          </ul>

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">Sparklines: daily readings, last 28 days. {data.note}</p>

          <ChartTable
            columns={["Date", ...metrics.map((m) => `${m.label} (${m.unit})`)]}
            rows={[...(metrics[0]?.series ?? [])]
              .map((p, i) => [fmtShortDate(p.date), ...metrics.map((m) => m.series?.[i]?.value ?? "—")])
              .reverse()}
            summary="Show daily readings as table"
          />
        </>
      )}
    </Card>
  );
}
