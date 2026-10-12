import { useEffect, useState } from "react";
import { Flame } from "lucide-react";
import AcademicProgress from "@/components/AcademicProgress";
import ComplianceTracker from "@/components/ComplianceTracker";
import DeadlineTracker from "@/components/DeadlineTracker";
import DisciplineVolume from "@/components/DisciplineVolume";
import Durability from "@/components/Durability";
import EquipmentMilestones from "@/components/EquipmentMilestones";
import ExamPrepCoverage from "@/components/ExamPrepCoverage";
import GoalGapTracker from "@/components/GoalGapTracker";
import InjuryLog from "@/components/InjuryLog";
import IntensityDistribution from "@/components/IntensityDistribution";
import KpiStrip from "@/components/KpiStrip";
import LoadDeadlineOverlay from "@/components/LoadDeadlineOverlay";
import NutritionSupplements from "@/components/NutritionSupplements";
import PhaseGateChecklist from "@/components/PhaseGateChecklist";
import Readiness from "@/components/Readiness";
import RecoveryMetrics from "@/components/RecoveryMetrics";
import RecoveryTrend from "@/components/RecoveryTrend";
import RunGuard from "@/components/RunGuard";
import SeasonHeader from "@/components/SeasonHeader";
import StudyHours from "@/components/StudyHours";
import ThisWeek from "@/components/ThisWeek";
import ThresholdTrends from "@/components/ThresholdTrends";
import TrainingLoadChart from "@/components/TrainingLoadChart";
import TrainingWeekSummary from "@/components/TrainingWeekSummary";
import WeightedAverageTrend from "@/components/WeightedAverageTrend";

const ACADEMIC_YEAR = "2026/2027";

function SectionLabel({ children }: { children: string }) {
  return (
    <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-neutral-300">
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
  // The page photo is optional and local-only: if it fails to load, its layers are dropped
  // and the header goes back to its compact form on the plain background.
  const [photo, setPhoto] = useState(true);

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
    <div className="relative isolate min-h-screen bg-[#0d0d0d]">
      {photo && (
        <>
          <img src="/hero.jpg" alt="" aria-hidden="true" decoding="async" className="page-photo -z-20" onError={() => setPhoto(false)} />
          <div className="page-vignette -z-10" />
        </>
      )}
      {/* No background or backdrop-filter on the header: either would hide or re-anchor the fixed photo. */}
      <header className="relative isolate border-b border-white/[0.06] px-6 pt-5">
        {photo && (
          <div className="hero-photo-clip -z-10">
            <img src="/hero.jpg" alt="" aria-hidden="true" decoding="async" className="page-photo" />
          </div>
        )}
        {/* Three columns: title, countdown, date. Narrow screens: title and date share a
            row and the countdown sits centred beneath them, above the tabs. */}
        <div className={`mx-auto flex max-w-6xl flex-wrap justify-between gap-x-4 gap-y-3 ${photo ? "items-start" : "items-center"}`}>
          <div className="order-1 flex items-center gap-2.5 md:flex-1">
            <Flame size={22} className="text-orange-500" strokeWidth={2} />
            <h1 className="text-xl font-bold text-white">Fitness Dashboard</h1>
          </div>
          {/* With the photo, the countdown drops below the face and gets a dark pool behind it. */}
          <div className={`order-3 w-full md:order-2 md:w-auto ${photo ? "hero-countdown" : ""}`}>
            <div className={photo ? "hero-scrim" : undefined}>
              <SeasonHeader />
            </div>
          </div>
          <span className={`order-2 text-xs md:order-3 md:flex-1 md:text-right ${photo ? "text-neutral-100" : "text-neutral-400"}`}>{today}</span>
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
                  : "border-transparent text-neutral-300 hover:text-white"
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
            <section className="mb-8 space-y-5">
              <KpiStrip />
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <ThisWeek />
                <Readiness />
              </div>
              <LoadDeadlineOverlay />
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
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <TrainingLoadChart />
              <DisciplineVolume />
              <ComplianceTracker />
              <IntensityDistribution />
              <RunGuard />
              <Durability />
              <div className="flex flex-col gap-5">
                <RecoveryTrend />
                <InjuryLog />
              </div>
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
