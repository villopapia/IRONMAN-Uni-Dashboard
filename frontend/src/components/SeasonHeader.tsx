import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

const count = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;
const longDate = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** The header's focal point: days to race, the race and its date, then phase and next gate. */
export default function SeasonHeader() {
  const { data } = usePolling(() => api.getSeason());
  if (!data?.race || data.days_to_race < 0) return null;

  const gate = data.next_gate;
  const detail = [
    data.phase && `${data.phase.name} week ${data.phase.week} of ${data.phase.weeks}`,
    gate && `Next: ${gate.name} ${gate.days === 0 ? "today" : `in ${count(gate.days, "day")}`}`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="text-center">
      <div className="text-4xl font-bold tabular-nums leading-none text-white [text-shadow:0_2px_14px_rgba(0,0,0,0.65)]">{count(data.days_to_race, "day")}</div>
      <div className="mt-1.5 text-sm text-neutral-100">
        {data.race.name} · {longDate(data.race.date)}
      </div>
      {detail && <div className="mt-0.5 text-xs text-neutral-300">{detail}</div>}
    </div>
  );
}
