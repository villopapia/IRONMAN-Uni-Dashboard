import { CalendarDays } from "lucide-react";
import { api, KeySession } from "@/lib/api";
import { fmtWeekRange } from "@/lib/format";
import { SPORT_COLORS } from "@/lib/palette";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";

const KEY_TONE: Record<KeySession["status"], [BadgeTone, string]> = {
  done: ["good", "Done"],
  missed: ["critical", "Missed"],
  pending: ["neutral", "Pending"],
  not_planned: ["neutral", "Not in calendar"],
};

const SPORTS = ["swim", "bike", "run"] as const;

export default function ThisWeek() {
  const { data, error } = usePolling(() => api.getThisWeek());

  return (
    <Card icon={CalendarDays} title="This week" meta={data ? fmtWeekRange(data.week_start) : undefined} className="lg:col-span-2">
      {error && <p className="mb-2 text-sm text-red-400">Couldn't refresh ({error}){data ? " — showing last known data." : ""}</p>}
      {!data && !error && <Skeleton className="h-32 w-full" />}

      {data && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Key sessions</div>
            <ul className="mt-1 divide-y divide-white/[0.05]">
              {(data.key_sessions ?? []).map((k) => {
                const [tone, label] = KEY_TONE[k.status] ?? ["neutral", k.status];
                return (
                  <li key={k.label} className="flex items-center justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <div className="text-sm text-neutral-200">{k.label}</div>
                      {k.title && (
                        <div className="truncate text-xs text-neutral-500" title={k.title}>
                          {k.title}
                        </div>
                      )}
                    </div>
                    <StatusBadge tone={tone} label={label} compact />
                  </li>
                );
              })}
            </ul>
          </div>

          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Minutes done vs planned</div>
            <ul className="mt-1 divide-y divide-white/[0.05] text-sm">
              {SPORTS.map((s) => {
                const m = data.minutes?.[s];
                if (!m) return null;
                return (
                  <li key={s} className="flex items-center justify-between py-2">
                    <span className="flex items-center gap-2 capitalize text-neutral-300">
                      <span className="h-2 w-2 rounded-full" style={{ background: SPORT_COLORS[s] }} />
                      {s}
                    </span>
                    <span className="tabular-nums text-neutral-400">
                      <span className="text-neutral-200">{m.done}</span> / {m.planned} min
                      {m.planned > 0 && ` · ${Math.round((m.done / m.planned) * 100)}%`}
                    </span>
                  </li>
                );
              })}
            </ul>
            <p className="mt-2 text-xs text-neutral-500">
              Planned = calendar block length (includes changing / transition time); done = moving time.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
