import { useEffect, useState } from "react";
import { CheckCircle2, Pill, Utensils } from "lucide-react";
import {
  api,
  NutritionDaySummary,
  NutritionPlan,
  SupplementDaySummary,
} from "@/lib/api";
import { status } from "@/lib/palette";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";

const SLOT_ORDER = ["breakfast", "snack1", "main_meal", "snack2", "snack3", "dinner"];
const CUSTOM_OPTION = "__custom__";
const today = () => new Date().toISOString().slice(0, 10);

const selectClass =
  "min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-neutral-100 focus:border-orange-500/60 focus:outline-none";

export default function NutritionSupplements() {
  const [plan, setPlan] = useState<NutritionPlan | null>(null);
  const [day, setDay] = useState<NutritionDaySummary | null>(null);
  const [supplements, setSupplements] = useState<SupplementDaySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selection, setSelection] = useState<Record<string, string>>({});
  const [customText, setCustomText] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  const loadDay = () => {
    const d = today();
    Promise.all([api.getNutritionDay(d), api.getSupplementDay(d)])
      .then(([nutritionDay, supplementDay]) => {
        setDay(nutritionDay);
        setSupplements(supplementDay);
      })
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    api.getNutritionPlan().then(setPlan).catch((err) => setError(err.message));
    loadDay();
    const id = setInterval(loadDay, 6 * 60 * 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function logSlot(slot: string) {
    const chosen = selection[slot];
    const description = chosen === CUSTOM_OPTION ? customText[slot] : chosen;
    if (!description) return;
    setSubmitting(slot);
    try {
      await api.logMeal({ date: today(), slot, description });
      loadDay();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(null);
    }
  }

  async function toggleSupplement(id: number, taken: boolean) {
    try {
      await api.logSupplement(today(), id, taken);
      loadDay();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const loggedBySlot = new Map(day?.logs.map((l) => [l.slot, l]) ?? []);
  const takenIds = new Set(supplements?.taken_supplement_ids ?? []);
  const slotsDone = SLOT_ORDER.filter((s) => loggedBySlot.has(s)).length;

  return (
    <Card
      icon={Utensils}
      title="Nutrition & supplements"
      meta={plan ? `${slotsDone}/${SLOT_ORDER.length} logged today` : "today"}
    >
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!plan && !error && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      )}

      {plan && (
        <ul className="space-y-3">
          {SLOT_ORDER.map((slot) => {
            const logged = loggedBySlot.get(slot);
            const options = plan.meal_options[slot] ?? [];
            return (
              <li key={slot} className="text-sm">
                <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  {plan.slot_labels[slot] ?? slot}
                </div>
                {logged ? (
                  <div className="mt-1 flex items-start gap-2 text-neutral-200">
                    <CheckCircle2 size={16} className="mt-0.5 shrink-0" style={{ color: status.good }} />
                    <span>{logged.description}</span>
                  </div>
                ) : (
                  <div className="mt-1 flex flex-wrap gap-2">
                    <select
                      value={selection[slot] ?? ""}
                      onChange={(e) =>
                        setSelection((s) => ({ ...s, [slot]: e.target.value }))
                      }
                      className={selectClass}
                    >
                      <option value="">Pick what you ate...</option>
                      {options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt.length > 70 ? `${opt.slice(0, 70)}...` : opt}
                        </option>
                      ))}
                      <option value={CUSTOM_OPTION}>Something else...</option>
                    </select>
                    {selection[slot] === CUSTOM_OPTION && (
                      <input
                        value={customText[slot] ?? ""}
                        onChange={(e) =>
                          setCustomText((c) => ({ ...c, [slot]: e.target.value }))
                        }
                        placeholder="What did you eat?"
                        className={selectClass}
                      />
                    )}
                    <button
                      onClick={() => logSlot(slot)}
                      disabled={submitting === slot || !selection[slot]}
                      className="shrink-0 rounded-lg bg-orange-600 px-3 py-1.5 font-medium text-white transition-colors hover:bg-orange-500 disabled:cursor-not-allowed disabled:bg-neutral-700 disabled:text-neutral-500"
                    >
                      Log
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {supplements && (
        <div className="mt-5 border-t border-white/[0.06] pt-4">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            <Pill size={13} /> Supplements
          </div>
          <ul className="mt-2 space-y-1.5">
            {supplements.protocols.map((p) => (
              <li key={p.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={takenIds.has(p.id)}
                  onChange={(e) => toggleSupplement(p.id, e.target.checked)}
                  className="h-4 w-4 accent-orange-600"
                />
                <span className="text-neutral-200">{p.name}</span>
                {p.timing && <span className="text-neutral-500">({p.timing})</span>}
                {p.needs_dose && (
                  <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-400">
                    dose TBD
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan && plan.notes.length > 0 && (
        <details className="mt-4 text-xs text-neutral-500">
          <summary className="cursor-pointer select-none hover:text-neutral-400">
            Προσοχή (dietician's notes)
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {plan.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}
