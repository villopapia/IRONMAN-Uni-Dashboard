import { useEffect, useState } from "react";
import { Flame } from "lucide-react";
import AcademicProgress from "@/components/AcademicProgress";
import ComplianceTracker from "@/components/ComplianceTracker";
import DeadlineTracker from "@/components/DeadlineTracker";
import DisciplineVolume from "@/components/DisciplineVolume";
import EquipmentMilestones from "@/components/EquipmentMilestones";
import ExamPrepCoverage from "@/components/ExamPrepCoverage";
import GoalGapTracker from "@/components/GoalGapTracker";
import InjuryLog from "@/components/InjuryLog";
import LoadDeadlineOverlay from "@/components/LoadDeadlineOverlay";
import NutritionSupplements from "@/components/NutritionSupplements";
import PhaseGateChecklist from "@/components/PhaseGateChecklist";
import RecoveryMetrics from "@/components/RecoveryMetrics";
import RecoveryTrend from "@/components/RecoveryTrend";
import StudyHours from "@/components/StudyHours";
import ThresholdTrends from "@/components/ThresholdTrends";
import TrainingLoadChart from "@/components/TrainingLoadChart";
import TrainingWeekSummary from "@/components/TrainingWeekSummary";
import WeightedAverageTrend from "@/components/WeightedAverageTrend";

const ACADEMIC_YEAR = "2026/2027";

function SectionLabel({ children }: { children: string }) {
  return (
    <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-neutral-500">
      {children}
    </h2>
  );
}

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "training", label: "Training" },
  { id: "race", label: "Race prep" },
  { id: "academic", label: "Academic" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function tabFromHash(): TabId {
  const h = window.location.hash.replace("#", "");
  return (TABS.find((t) => t.id === h)?.id ?? "overview") as TabId;
}

export default function App() {
  const [tab, setTab] = useState<TabId>(tabFromHash);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="min-h-screen bg-[#0d0d0d]">
      <header className="border-b border-white/[0.06] bg-[#0d0d0d]/80 px-6 pt-5 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Flame size={22} className="text-orange-500" strokeWidth={2} />
            <h1 className="text-xl font-bold text-white">Fitness Dashboard</h1>
          </div>
          <span className="text-sm text-neutral-500">{today}</span>
        </div>
        <nav className="mx-auto mt-4 flex max-w-6xl gap-1 overflow-x-auto" role="tablist">
          {TABS.map((t) => (
            <a
              key={t.id}
              href={`#${t.id}`}
              role="tab"
              aria-selected={tab === t.id}
              className={`whitespace-nowrap border-b-2 px-3 pb-2.5 text-sm font-medium transition-colors ${
                tab === t.id
                  ? "border-orange-500 text-white"
                  : "border-transparent text-neutral-500 hover:text-neutral-300"
              }`}
            >
              {t.label}
            </a>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {tab === "overview" && (
          <>
            <section className="mb-8">
              <SectionLabel>Burnout watch</SectionLabel>
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <LoadDeadlineOverlay />
              </div>
            </section>

            <section>
              <SectionLabel>Training</SectionLabel>
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <TrainingWeekSummary />
                <RecoveryMetrics />
              </div>
            </section>

            <section className="mt-8">
              <SectionLabel>Life</SectionLabel>
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <AcademicProgress academicYear={ACADEMIC_YEAR} />
                <NutritionSupplements />
              </div>
            </section>
          </>
        )}

        {tab === "training" && (
          <section>
            <SectionLabel>Load, volume & compliance</SectionLabel>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <TrainingLoadChart />
              <DisciplineVolume />
              <ComplianceTracker />
            </div>
          </section>
        )}

        {tab === "training" && (
          <section className="mt-8">
            <SectionLabel>Recovery & niggles</SectionLabel>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <RecoveryTrend />
              <InjuryLog />
            </div>
          </section>
        )}

        {tab === "race" && (
          <section className="mb-8">
            <SectionLabel>Goal & thresholds</SectionLabel>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <GoalGapTracker />
              <PhaseGateChecklist />
              <ThresholdTrends />
            </div>
          </section>
        )}

        {tab === "race" && (
          <section>
            <SectionLabel>Equipment</SectionLabel>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <EquipmentMilestones />
            </div>
          </section>
        )}
        {tab === "academic" && (
          <section>
            <SectionLabel>Trajectory & deadlines</SectionLabel>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <WeightedAverageTrend academicYear={ACADEMIC_YEAR} />
              <DeadlineTracker academicYear={ACADEMIC_YEAR} />
              <StudyHours academicYear={ACADEMIC_YEAR} />
              <ExamPrepCoverage academicYear={ACADEMIC_YEAR} />
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
