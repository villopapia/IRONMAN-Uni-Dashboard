import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

const count = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;

/** Race countdown, current phase and next gate; the plain date until it loads or after the race. */
export default function SeasonHeader({ fallback }: { fallback: string }) {
  const { data } = usePolling(() => api.getSeason());
  if (!data?.race || data.days_to_race < 0) return <span className="text-sm text-neutral-500">{fallback}</span>;

  const gate = data.next_gate;
  const second = [
    data.phase && `${data.phase.name} week ${data.phase.week} of ${data.phase.weeks}`,
    gate && `Next: ${gate.name} ${gate.days === 0 ? "today" : `in ${count(gate.days, "day")}`}`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="text-right">
      <div className="text-sm font-medium text-neutral-200">
        {data.race.name} · {count(data.days_to_race, "day")} · {count(data.weeks_to_race, "week")}
      </div>
      {second && <div className="text-xs text-neutral-500">{second}</div>}
    </div>
  );
}
