import { useState } from "react";
import { Flag } from "lucide-react";
import { api, Gate, GateItem, GateItemUpdate, GateStatus } from "@/lib/api";
import { fmtDuration, fmtMetric, fmtShortDate, parseDuration, todayIso } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";
import StatusBadge, { BadgeTone } from "@/components/ui/StatusBadge";

const STATUS_TONE: Record<GateStatus, [BadgeTone, string]> = {
  pass: ["good", "Pass"],
  fail: ["critical", "Fail"],
  pending: ["neutral", "Pending"],
  overdue: ["serious", "Not logged"],
  on_track: ["good", "On track"],
  behind: ["warning", "Behind"],
  recorded: ["good", "Recorded"],
};

const OVERALL_TONE: Record<Gate["overall"], [BadgeTone, string]> = {
  pass: ["good", "Gate passed"],
  fail: ["critical", "Gate failed"],
  pending: ["neutral", "In progress"],
  incomplete: ["serious", "Results missing"],
};

const inputCls =
  "rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-sm text-white placeholder:text-neutral-600 focus:border-white/20 focus:outline-none";
const btnCls =
  "rounded-md bg-white/[0.08] px-2.5 py-1 text-xs font-medium text-neutral-200 hover:bg-white/[0.14] disabled:opacity-40";

function RecordForm({
  item,
  onSave,
}: {
  item: GateItem;
  onSave: (update: GateItemUpdate) => Promise<void>;
}) {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [on, setOn] = useState(item.recorded_on ?? todayIso());
  const [err, setErr] = useState<string | null>(null);

  if (item.evaluation === "auto_swim_freq") return null;

  if (item.evaluation === "manual") {
    return (
      <div className="mt-2 flex flex-wrap gap-1.5">
        <button className={btnCls} onClick={() => onSave({ manual_status: "pass" })}>
          Mark pass
        </button>
        <button className={btnCls} onClick={() => onSave({ manual_status: "fail" })}>
          Mark fail
        </button>
        {item.manual_status && (
          <button className={btnCls} onClick={() => onSave({ manual_status: null })}>
            Clear
          </button>
        )}
      </div>
    );
  }

  const submit = async () => {
    setErr(null);
    let update: GateItemUpdate | null = null;
    if (item.unit === "s/100m") {
      const t400 = parseDuration(a);
      const t200 = parseDuration(b);
      if (!t400 || !t200 || t400 <= t200) {
        setErr("Enter both splits as m:ss (400m slower than 200m).");
        return;
      }
      update = { t400_s: t400, t200_s: t200, recorded_on: on };
    } else if (item.unit === "s") {
      const secs = parseDuration(a);
      if (!secs) {
        setErr("Enter a time as h:mm:ss.");
        return;
      }
      update = { result_value: secs, result_text: fmtDuration(secs), recorded_on: on };
    } else {
      const v = Number(a);
      if (!a || !isFinite(v) || v <= 0) {
        setErr("Enter a number.");
        return;
      }
      update = { result_value: v, result_text: null, recorded_on: on };
    }
    await onSave(update);
    setA("");
    setB("");
  };

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        {item.unit === "s/100m" ? (
          <>
            <input className={`${inputCls} w-24`} placeholder="400m m:ss" value={a} onChange={(e) => setA(e.target.value)} />
            <input className={`${inputCls} w-24`} placeholder="200m m:ss" value={b} onChange={(e) => setB(e.target.value)} />
          </>
        ) : (
          <input
            className={`${inputCls} w-28`}
            placeholder={item.unit === "s" ? "h:mm:ss" : item.unit ?? "value"}
            value={a}
            onChange={(e) => setA(e.target.value)}
          />
        )}
        <input type="date" className={`${inputCls} w-36`} value={on} onChange={(e) => setOn(e.target.value)} />
        <button className={btnCls} onClick={submit}>
          Save result
        </button>
      </div>
      {err && <p className="text-xs text-red-400">{err}</p>}
    </div>
  );
}

export default function PhaseGateChecklist() {
  const { data: gates, error, setData, reload } = usePolling(api.getGates);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const save = async (key: string, update: GateItemUpdate) => {
    setSaveError(null);
    try {
      setData(await api.updateGateItem(key, update));
      setOpenKey(null);
    } catch (e) {
      setSaveError((e as Error).message);
      reload();
    }
  };

  // Next upcoming gate first; fall back to the most recent past one.
  const gate =
    gates?.find((g) => g.days_remaining >= 0) ?? (gates && gates[gates.length - 1]) ?? null;

  return (
    <Card
      icon={Flag}
      title="Phase gate"
      meta={gate ? `${fmtShortDate(gate.gate_date)} · ${gate.gate_name}` : undefined}
    >
      {error && (
        <p className="mb-2 text-sm text-red-400">
          Couldn't refresh ({error}){gates ? " — showing last known data." : ""}
        </p>
      )}
      {saveError && <p className="mb-2 text-sm text-red-400">Save failed: {saveError}</p>}

      {!gates && !error && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}

      {gates && !gate && <p className="text-sm text-neutral-500">No phase gates set up.</p>}

      {gate && (
        <>
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-4xl font-bold text-white">
                {gate.days_remaining >= 0 ? gate.days_remaining : 0}
                <span className="ml-1.5 text-base font-medium text-neutral-400">
                  {gate.days_remaining >= 0 ? "days to go" : "days — gate date passed"}
                </span>
              </div>
              <div className="mt-1 text-sm text-neutral-400">
                {gate.passed}/{gate.total} criteria passed
              </div>
            </div>
            <StatusBadge tone={OVERALL_TONE[gate.overall][0]} label={OVERALL_TONE[gate.overall][1]} />
          </div>

          <ul className="mt-4 divide-y divide-white/[0.06]">
            {gate.items.map((item) => {
              const [tone, label] = STATUS_TONE[item.status] ?? ["neutral", item.status];
              const open = openKey === item.key;
              return (
                <li key={item.key} className="py-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-neutral-200">{item.title}</div>
                      <div className="text-xs text-neutral-500">{item.criterion}</div>
                      {item.result_value != null && (
                        <div className="mt-0.5 text-xs text-neutral-300">
                          Result: {fmtMetric(item.result_value, item.unit)}
                          {item.result_text && item.unit !== "s" ? ` (${item.result_text})` : ""}
                          {item.recorded_on ? ` · ${fmtShortDate(item.recorded_on)}` : ""}
                        </div>
                      )}
                      {item.detail && <div className="mt-0.5 text-xs text-neutral-400">{item.detail}</div>}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <StatusBadge tone={tone} label={label} compact />
                      {item.evaluation !== "auto_swim_freq" && (
                        <button
                          className="text-[11px] text-neutral-500 hover:text-neutral-300"
                          onClick={() => setOpenKey(open ? null : item.key)}
                        >
                          {open ? "Cancel" : item.evaluation === "manual" ? "Set" : "Record"}
                        </button>
                      )}
                    </div>
                  </div>
                  {open && <RecordForm item={item} onSave={(u) => save(item.key, u)} />}
                </li>
              );
            })}
          </ul>

          {gate.source_note && (
            <p className="mt-3 text-xs leading-relaxed text-neutral-500">{gate.source_note}</p>
          )}
        </>
      )}
    </Card>
  );
}
