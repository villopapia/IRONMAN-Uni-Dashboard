import { api } from "@/lib/api";
import { LOAD_COLORS, SPORT_COLORS } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import StatTile from "@/components/ui/StatTile";
import StatusBadge, { FLAG_BADGE } from "@/components/ui/StatusBadge";

const TILE = "rounded-2xl border border-white/[0.08] bg-[#1a1a19] p-4 shadow-lg shadow-black/20";
const SPARK_DAYS = 28;
const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;

/** The four numbers to read first. Each tile fills in as its own request returns. */
export default function KpiStrip() {
  const { data: ready } = usePolling(() => api.getReadiness());
  const { data: pmc } = usePolling(() => api.getPmc({ days: 90 }));
  const { data: run } = usePolling(() => api.getRunRamp());

  // Badge = the worst metric status; the action line itself is the tile's value.
  const statuses = (ready?.metrics ?? []).map((m) => m.status);
  const worst = (["red", "amber", "pass"] as const).find((s) => statuses.includes(s)) ?? "no_data";
  const flagged = [
    ready?.red?.length ? `Red: ${ready.red.join(", ")}` : "",
    ready?.amber?.length ? `Amber: ${ready.amber.join(", ")}` : "",
    ready?.no_data?.length ? `No data: ${ready.no_data.join(", ")}` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const cur = pmc?.current;
  const tail = (pmc?.series ?? []).slice(-SPARK_DAYS);
  const weeks = run?.weeks ?? [];
  const thisWeek = weeks[weeks.length - 1];
  const lastWeek = weeks[weeks.length - 2];

  return (
    <div className="grid grid-cols-2 gap-5 lg:grid-cols-4">
      <div className={TILE}>
        <StatTile
          label="Readiness"
          value={ready?.action ?? null}
          badge={ready && <StatusBadge tone={FLAG_BADGE[worst][0]} label={FLAG_BADGE[worst][1]} compact />}
          sub={ready ? flagged || "All metrics pass" : null}
        />
      </div>
      <div className={TILE}>
        <StatTile
          label="Fitness (CTL)"
          value={cur ? cur.ctl.toFixed(1) : null}
          sub={pmc?.ctl_ramp_7d != null ? `${signed(pmc.ctl_ramp_7d)} / week` : null}
          spark={tail.map((p) => p.ctl)}
          sparkColor={LOAD_COLORS.ctl}
        />
      </div>
      <div className={TILE}>
        <StatTile label="Form (TSB)" value={cur ? signed(cur.tsb) : null} sub="28 days" spark={tail.map((p) => p.tsb)} sparkColor={LOAD_COLORS.tsb} />
      </div>
      <div className={TILE}>
        <StatTile
          label="Run km this week"
          value={thisWeek ? `${thisWeek.km} km` : null}
          sub={lastWeek ? `last week ${lastWeek.km} km` : null}
          spark={weeks.slice(0, -1).map((w) => w.km)}
          sparkColor={SPORT_COLORS.run}
        />
      </div>
    </div>
  );
}
