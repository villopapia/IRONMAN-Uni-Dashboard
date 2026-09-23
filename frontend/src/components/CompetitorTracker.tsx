import { useEffect, useState } from "react";
import { Swords } from "lucide-react";
import { api, WeekComparison } from "@/lib/api";
import { mostRecentMonday } from "@/lib/dates";
import { status } from "@/lib/palette";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";

const inputClass =
  "min-w-0 rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-sm text-neutral-100 focus:border-orange-500/60 focus:outline-none";
const buttonClass =
  "shrink-0 rounded-lg bg-orange-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-orange-500 disabled:cursor-not-allowed disabled:bg-neutral-700 disabled:text-neutral-500";

export default function CompetitorTracker() {
  const [weekStart] = useState(mostRecentMonday());
  const [comparison, setComparison] = useState<WeekComparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [logCompetitorId, setLogCompetitorId] = useState<number | null>(null);
  const [logSport, setLogSport] = useState("run");
  const [logMinutes, setLogMinutes] = useState("");
  const [logDate, setLogDate] = useState(new Date().toISOString().slice(0, 10));
  const [submitting, setSubmitting] = useState(false);

  const load = () =>
    api
      .compareWeek(weekStart)
      .then(setComparison)
      .catch((err) => setError(err.message));

  useEffect(() => {
    load();
    const id = setInterval(load, 6 * 60 * 1000); // 10x/hour
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekStart]);

  async function handleAddCompetitor(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    try {
      await api.createCompetitor(newName.trim());
      setNewName("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogActivity(e: React.FormEvent) {
    e.preventDefault();
    if (logCompetitorId === null || !logMinutes) return;
    setSubmitting(true);
    try {
      await api.logCompetitorActivity(logCompetitorId, {
        date: logDate,
        sport: logSport,
        duration_min: Number(logMinutes),
      });
      setLogMinutes("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const you = comparison?.you_minutes ?? 0;
  const maxMinutes = Math.max(you, ...(comparison?.competitors.map((c) => c.total_minutes) ?? [0]), 1);

  return (
    <Card icon={Swords} title="The competition" meta="this week, minutes trained">
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!comparison && !error && (
        <div className="space-y-2.5">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </div>
      )}

      {comparison && (
        <ul className="space-y-2.5">
          <li className="flex items-center gap-3">
            <span className="w-24 shrink-0 text-sm font-medium text-neutral-200">You</span>
            <div className="h-3.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className="h-full rounded-full bg-orange-500 transition-all"
                style={{ width: `${(you / maxMinutes) * 100}%` }}
              />
            </div>
            <span className="w-14 shrink-0 text-right text-sm text-neutral-300">
              {you}m
            </span>
          </li>
          {comparison.competitors.map((c) => (
            <li key={c.competitor_id} className="flex items-center gap-3">
              <span className="w-24 shrink-0 truncate text-sm text-neutral-300">
                {c.name}
              </span>
              <div className="h-3.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${(c.total_minutes / maxMinutes) * 100}%`,
                    background: c.total_minutes > you ? status.critical : "#525252",
                  }}
                />
              </div>
              <span className="w-14 shrink-0 text-right text-sm text-neutral-300">
                {c.total_minutes}m
              </span>
            </li>
          ))}
          {comparison.competitors.length === 0 && (
            <li className="text-sm text-neutral-500">
              No competitors added yet — add one below.
            </li>
          )}
        </ul>
      )}

      <div className="mt-5 grid grid-cols-1 gap-3 border-t border-white/[0.06] pt-4 sm:grid-cols-2">
        <form onSubmit={handleAddCompetitor} className="flex gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Add competitor name"
            className={`flex-1 ${inputClass}`}
          />
          <button type="submit" disabled={submitting} className={buttonClass}>
            Add
          </button>
        </form>

        <form onSubmit={handleLogActivity} className="flex flex-wrap gap-2">
          <select
            value={logCompetitorId ?? ""}
            onChange={(e) => setLogCompetitorId(Number(e.target.value) || null)}
            className={inputClass}
          >
            <option value="">Log for...</option>
            {comparison?.competitors.map((c) => (
              <option key={c.competitor_id} value={c.competitor_id}>
                {c.name}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={logDate}
            onChange={(e) => setLogDate(e.target.value)}
            className={inputClass}
          />
          <select
            value={logSport}
            onChange={(e) => setLogSport(e.target.value)}
            className={inputClass}
          >
            <option value="run">Run</option>
            <option value="bike">Bike</option>
            <option value="swim">Swim</option>
            <option value="gym">Gym</option>
            <option value="walk">Walk</option>
            <option value="other">Other</option>
          </select>
          <input
            type="number"
            min="0"
            value={logMinutes}
            onChange={(e) => setLogMinutes(e.target.value)}
            placeholder="min"
            className={`w-16 ${inputClass}`}
          />
          <button
            type="submit"
            disabled={submitting || logCompetitorId === null}
            className={buttonClass}
          >
            Log
          </button>
        </form>
      </div>

      <p className="mt-3 text-xs text-neutral-500">
        Manually logged — Strava doesn't expose other athletes' activities to
        third-party apps, so this is self-reported for whoever you're keeping
        an eye on.
      </p>
    </Card>
  );
}
