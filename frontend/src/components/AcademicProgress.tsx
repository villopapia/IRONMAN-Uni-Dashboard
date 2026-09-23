import { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";
import { api, ClassificationSummary } from "@/lib/api";
import { ink, status } from "@/lib/palette";
import Card from "@/components/ui/Card";
import Skeleton from "@/components/ui/Skeleton";

interface Props {
  academicYear: string;
}

const BAND_COLOR: Record<string, string> = {
  First: status.good,
  "Upper Second (2:1)": "#3987e5",
  "Lower Second (2:2)": status.warning,
  Third: status.serious,
  Fail: status.critical,
};

export default function AcademicProgress({ academicYear }: Props) {
  const [summary, setSummary] = useState<ClassificationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api
        .getAcademicSummary(academicYear)
        .then(setSummary)
        .catch((err) => setError(err.message));

    load();
    const id = setInterval(load, 6 * 60 * 1000); // 10x/hour
    return () => clearInterval(id);
  }, [academicYear]);

  return (
    <Card icon={GraduationCap} title="Academic progress" meta={academicYear}>
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!summary && !error && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </div>
      )}

      {summary && (
        <>
          <div className="flex items-end gap-3">
            <span className="text-4xl font-bold text-white">
              {summary.weighted_average_pct !== null
                ? `${summary.weighted_average_pct.toFixed(1)}%`
                : "—"}
            </span>
            {summary.classification_estimate && (
              <span
                className="rounded-full px-3 py-1 text-sm font-medium"
                style={{
                  color: BAND_COLOR[summary.classification_estimate] ?? ink.secondary,
                  background: `${BAND_COLOR[summary.classification_estimate] ?? ink.muted}1a`,
                }}
              >
                {summary.classification_estimate}
              </span>
            )}
          </div>

          <ul className="mt-4 divide-y divide-white/[0.06]">
            {summary.modules.map((m) => (
              <li
                key={m.module_id}
                className="flex items-center justify-between py-2.5 text-sm"
              >
                <span className="text-neutral-300">
                  {m.name}{" "}
                  {m.needs_level_credits ? (
                    <span className="text-amber-400/80" title="Excluded from the weighted average until its FHEQ level and credit value are set">
                      (level/credits needed)
                    </span>
                  ) : (
                    <span className="text-neutral-500">
                      (L{m.fheq_level}, {m.credits} credits)
                    </span>
                  )}
                </span>
                <span className="font-medium text-white">
                  {m.mark_pct !== null ? `${m.mark_pct.toFixed(1)}%` : "—"}
                  {!m.fully_graded && m.mark_pct !== null && (
                    <span className="ml-1 text-xs font-normal text-neutral-500">
                      (partial)
                    </span>
                  )}
                </span>
              </li>
            ))}
            {summary.modules.length === 0 && (
              <li className="py-2 text-sm text-neutral-500">
                No modules seeded for {academicYear} yet.
              </li>
            )}
          </ul>

          <p className="mt-4 text-xs leading-relaxed text-neutral-500">
            {summary.methodology_note}
          </p>
        </>
      )}
    </Card>
  );
}
