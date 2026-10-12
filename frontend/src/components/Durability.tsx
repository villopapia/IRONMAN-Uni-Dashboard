import { useState } from "react";
import { Mountain } from "lucide-react";
import { api, Longest } from "@/lib/api";
import { fmtWeekRange } from "@/lib/format";
import { SPORT_COLORS } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";

const SPORTS = [
  { key: "swim", label: "Longest swim" },
  { key: "bike", label: "Longest ride" },
  { key: "run", label: "Longest run" },
] as const;

const DEFAULT_WEEKS = 6;

// Value, % of the race target, and a bar that fills to the target (capped at
// 100% wide; the number carries any overshoot).
function Cell({ longest, unit, color }: { longest: Longest; unit: string; color: string }) {
  if (!longest) return <span className="text-neutral-600">—</span>;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 tabular-nums">
        <span className="text-neutral-200">
          {longest.value.toLocaleString()} {unit}
        </span>
        <span className="text-neutral-400">{longest.pct}%</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, longest.pct)}%`, background: color }} />
      </div>
    </div>
  );
}

export default function Durability() {
  const { data, error } = usePolling(() => api.getDurability());
  const [showAll, setShowAll] = useState(false);
  const all = [...(data?.weeks ?? [])].reverse();
  const weeks = showAll ? all : all.slice(0, DEFAULT_WEEKS);

  return (
    <Card
      icon={Mountain}
      title="Durability"
      info="Longest single session each week as a share of the race distance. Rides are measured in minutes because they are indoor and record no distance. The current week is still in progress."
      meta="longest session per week vs race distance"
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-56 w-full" />}

      {data && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-neutral-500">
                <tr>
                  <th className="pb-1.5 pr-3 font-medium">Week</th>
                  {SPORTS.map((s) => (
                    <th key={s.key} className="pb-1.5 pr-3 font-medium">
                      <span className="inline-flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full" style={{ background: SPORT_COLORS[s.key] }} />
                        {s.label}
                        <span className="font-normal text-neutral-600">
                          / {data.targets?.[s.key]?.target.toLocaleString()} {data.targets?.[s.key]?.unit}
                        </span>
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weeks.map((w, i) => (
                  <tr key={w.week_start} className="border-t border-white/[0.04]">
                    <td className="whitespace-nowrap py-1.5 pr-3 text-neutral-300">
                      {fmtWeekRange(w.week_start)}
                      {i === 0 && <span className="ml-1 text-neutral-500">(now)</span>}
                    </td>
                    {SPORTS.map((s) => (
                      <td key={s.key} className="w-[28%] py-1.5 pr-3">
                        <Cell longest={w[s.key]} unit={data.targets?.[s.key]?.unit ?? ""} color={SPORT_COLORS[s.key]} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {all.length > DEFAULT_WEEKS && (
            <button className="mt-2 text-xs text-neutral-500 hover:text-neutral-300" onClick={() => setShowAll(!showAll)}>
              {showAll ? `Show last ${DEFAULT_WEEKS} weeks` : `Show all ${all.length} weeks`}
            </button>
          )}
        </>
      )}
    </Card>
  );
}
