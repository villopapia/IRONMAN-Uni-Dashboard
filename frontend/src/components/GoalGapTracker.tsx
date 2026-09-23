import { Target } from "lucide-react";
import { api, GoalLeg } from "@/lib/api";
import { fmtDuration, fmtShortDate } from "@/lib/format";
import { ink, SPORT_COLORS } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";

const LEG_LABEL = { swim: "Swim 1.9 km", bike: "Bike 90 km", run: "Run 21.1 km" };

function signed(seconds: number) {
  return `${seconds > 0 ? "+" : seconds < 0 ? "−" : "±"}${fmtDuration(Math.abs(seconds))}`;
}

/** Bullet bar: projected time as the bar, budget as a tick. */
function LegBar({ leg, scale }: { leg: GoalLeg; scale: number }) {
  const budgetPct = (leg.budget_s / scale) * 100;
  const projPct = leg.projected_s != null ? (leg.projected_s / scale) * 100 : null;
  return (
    <div className="relative mt-1.5 h-2.5 rounded-full bg-white/[0.05]">
      {projPct != null && (
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${projPct}%`, background: SPORT_COLORS[leg.leg] }}
        />
      )}
      <div
        className="absolute -inset-y-1 w-0.5 rounded"
        style={{ left: `calc(${budgetPct}% - 1px)`, background: ink.primary }}
        title={`Budget ${fmtDuration(leg.budget_s)}`}
      />
    </div>
  );
}

export default function GoalGapTracker() {
  const { data, error } = usePolling(api.getGoalGap);

  const over = data?.delta_to_target_high_s ?? 0;
  const tone = !data ? "neutral" : over <= 0 ? "good" : over <= 5 * 60 ? "warning" : "serious";
  const scale = data
    ? Math.max(...data.legs.map((l) => Math.max(l.budget_s, l.projected_s ?? 0))) * 1.05
    : 1;

  return (
    <Card
      icon={Target}
      title="Race goal gap"
      meta={data?.race_date ? `70.3 Jönköping · ${data.days_to_race}d` : undefined}
    >
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && (
        <div className="space-y-3">
          <Skeleton className="h-12 w-40" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </div>
      )}

      {data && (
        <>
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-xs text-neutral-500">Projected finish (directional)</div>
              <div className="text-4xl font-bold text-white">{fmtDuration(data.projected_total_s)}</div>
              <div className="mt-1 text-sm text-neutral-400">
                Target {fmtDuration(data.target_low_s)}–{fmtDuration(data.target_high_s)} ·{" "}
                {over > 0 ? `${signed(over)} over the upper bound` : "inside the target range"}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <StatusBadge
                tone={tone}
                label={over <= 0 ? "On target" : over <= 300 ? "Close" : "Behind target"}
              />
              {!data.complete && (
                <StatusBadge tone="neutral" label={`No ${data.missing_legs.join(", ")} estimate`} compact />
              )}
            </div>
          </div>

          <ul className="mt-4 space-y-3.5">
            {data.legs.map((leg) => (
              <li key={leg.leg}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="flex items-center gap-2 text-neutral-200">
                    <span className="h-2 w-2 rounded-full" style={{ background: SPORT_COLORS[leg.leg] }} />
                    {LEG_LABEL[leg.leg]}
                  </span>
                  <span className="tabular-nums text-neutral-300">
                    {leg.projected_s != null ? fmtDuration(leg.projected_s) : "—"}
                    <span className="text-neutral-500"> / {fmtDuration(leg.budget_s)}</span>
                    {leg.delta_s != null && (
                      <span className="ml-2 font-medium text-white">{signed(leg.delta_s)}</span>
                    )}
                  </span>
                </div>
                <LegBar leg={leg} scale={scale} />
                <div className="mt-1 text-xs text-neutral-500">
                  {leg.basis ? (
                    <>
                      {leg.basis}
                      {leg.estimate_date ? ` · ${fmtShortDate(leg.estimate_date)}` : ""}
                    </>
                  ) : (
                    <>No estimate yet — using the budget split. Log a test on the threshold chart.</>
                  )}
                </div>
                <div className="text-[11px] text-neutral-600">{leg.assumption}</div>
              </li>
            ))}
            <li className="flex justify-between text-xs text-neutral-500">
              <span>T1 + T2 (budget remainder)</span>
              <span className="tabular-nums">{fmtDuration(data.transitions_s)}</span>
            </li>
          </ul>

          <div className="mt-4 rounded-lg bg-white/[0.03] px-3 py-2.5 text-xs">
            <div className="mb-1 font-semibold uppercase tracking-wide text-neutral-500">What the budget needs</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-neutral-300 sm:grid-cols-4">
              <span>CSS {fmtDuration(data.required.css_pace_s_per_100m)}/100m</span>
              <span>FTP {data.required.ftp_w} W</span>
              <span>Standalone HM {fmtDuration(data.required.hm_standalone_s)}</span>
              <span>Run {fmtDuration(data.required.run_pace_s_per_km)}/km off-bike</span>
            </div>
          </div>

          <p className="mt-3 text-xs leading-relaxed text-neutral-500">
            {data.note} Bar = projected, white tick = budget.
          </p>
        </>
      )}
    </Card>
  );
}
