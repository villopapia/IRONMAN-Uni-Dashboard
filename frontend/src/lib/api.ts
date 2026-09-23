const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export interface AssessmentOut {
  id: number;
  module_id: number;
  name: string;
  weight_pct: number;
  mark_pct: number | null;
}

export interface ModuleOut {
  id: number;
  academic_year: string;
  name: string;
  calendar_tag: string | null;
  fheq_level: number | null;
  credits: number | null;
  assessments: AssessmentOut[];
}

export interface ModuleBreakdown {
  module_id: number;
  name: string;
  fheq_level: number | null;
  credits: number | null;
  mark_pct: number | null;
  fully_graded: boolean;
  needs_level_credits: boolean;
}

export interface ClassificationSummary {
  weighted_average_pct: number | null;
  classification_estimate: string | null;
  modules: ModuleBreakdown[];
  methodology_note: string;
}

export interface SportRollup {
  sport: string;
  target_minutes: number | null;
  actual_minutes: number;
  target_distance_km: number | null;
  actual_distance_km: number;
  on_track_pct: number | null;
}

export interface WeekSummary {
  week_start_date: string;
  week_label: string | null;
  sports: SportRollup[];
  rest_days: string[];
}

export interface CompetitorOut {
  id: number;
  name: string;
  note: string | null;
}

export interface CompetitorWeekTotal {
  competitor_id: number;
  name: string;
  total_minutes: number;
}

export interface WeekComparison {
  week_start_date: string;
  you_minutes: number;
  competitors: CompetitorWeekTotal[];
}

export interface CompetitorActivityInput {
  date: string;
  sport: string;
  duration_min: number;
  distance_km?: number | null;
  note?: string | null;
}

export interface NutritionPlan {
  slot_labels: Record<string, string>;
  meal_options: Record<string, string[]>;
  notes: string[];
}

export interface NutritionLogOut {
  id: number;
  date: string;
  slot: string;
  description: string;
  followed_plan: boolean;
}

export interface NutritionDaySummary {
  date: string;
  logs: NutritionLogOut[];
  slots_missing: string[];
}

export interface SupplementProtocolOut {
  id: number;
  name: string;
  dose: number | null;
  unit: string | null;
  timing: string | null;
  note: string | null;
  needs_dose: boolean;
}

export interface SupplementDaySummary {
  date: string;
  protocols: SupplementProtocolOut[];
  taken_supplement_ids: number[];
}

export interface CalendarEvent {
  summary: string;
  start: string;
}

export interface WeekSchedule {
  week_start_date: string;
  days: Record<string, CalendarEvent[]>;
}

export interface GarminDailyMetric {
  date: string;
  updated_at: string;
  sleep_score: number | null;
  sleep_duration_min: number | null;
  body_battery_high: number | null;
  body_battery_low: number | null;
  training_readiness: number | null;
  hrv_status: string | null;
  hrv_value: number | null;
  resting_hr: number | null;
  vo2max_running: number | null;
  training_status: string | null;
}

// --- Race prep: phase gates, milestones, thresholds, niggle log ------------

export type GateStatus =
  | "pass"
  | "fail"
  | "pending"
  | "overdue"
  | "on_track"
  | "behind"
  | "recorded";

export interface GateItem {
  id: number;
  key: string;
  title: string;
  criterion: string;
  evaluation: string;
  target_value: number | null;
  unit: string | null;
  result_value: number | null;
  result_text: string | null;
  recorded_on: string | null;
  manual_status: "pass" | "fail" | null;
  status: GateStatus;
  detail: string | null;
}

export interface Gate {
  gate_date: string;
  gate_name: string;
  days_remaining: number;
  source_note: string | null;
  overall: "pass" | "fail" | "pending" | "incomplete";
  passed: number;
  total: number;
  items: GateItem[];
}

export interface GateItemUpdate {
  result_value?: number | null;
  result_text?: string | null;
  manual_status?: "pass" | "fail" | null;
  recorded_on?: string | null;
  t400_s?: number;
  t200_s?: number;
}

export interface Milestone {
  id: number;
  key: string;
  title: string;
  target_date: string | null;
  done: boolean;
  done_on: string | null;
  note: string | null;
  days_remaining: number | null;
  overdue: boolean;
}

export interface ThresholdTest {
  id: number;
  test_date: string;
  discipline: string;
  metric: string;
  value: number;
  unit: string;
  source: "manual" | "phase_gate" | "garmin";
  protocol: string | null;
  note: string | null;
}

export interface Phase {
  number: number;
  name: string;
  start_date: string;
  end_date: string | null;
}

export interface ThresholdHistory {
  tests: ThresholdTest[];
  phases: Phase[];
  race_date: string | null;
  metric_units: Record<string, string>;
}

export interface InjuryEntry {
  id: number;
  date: string;
  body_region: string;
  pain_scale: number;
  note: string | null;
}

export interface InjurySummary {
  entries: InjuryEntry[];
  weekly: { week_start: string; max_pain: number; entries: number; regions: string[] }[];
}

// --- Multi-discipline rollup + compliance ----------------------------------

export interface DisciplineWeek {
  minutes: number;
  distance_km: number;
  sessions: number;
  load: number;
}

export interface WeekDisciplineRollup {
  week_start: string;
  sports: Record<"swim" | "bike" | "run" | "gym" | "other", DisciplineWeek>;
}

export interface ComplianceRollup {
  planned: number;
  due: number;
  completed: number;
  pending: number;
  pct: number | null;
  flag: boolean;
}

export interface DisciplineCompliance extends ComplianceRollup {
  extras: number;
}

export interface StrengthCompliance extends ComplianceRollup {
  label: string;
}

export interface BrickDay {
  date: string;
  status: "done" | "split" | "partial" | "missed" | "pending" | "in_progress";
  titles: string[];
  bike_activity: string | null;
  run_activity: string | null;
}

export type SlotStatus = "done" | "moved" | "manual_done" | "skipped" | "missed" | "pending";

export interface PlannedSlot {
  ids: number[];
  date: string;
  start_at: string | null;
  discipline: string;
  titles: string[];
  is_brick: boolean;
  strength_type: string | null;
  status: SlotStatus;
  manual_status: "done" | "skipped" | null;
  activity_name: string | null;
  activity_date: string | null;
}

export interface WeekCompliance {
  week_start: string;
  has_plan: boolean;
  overall: ComplianceRollup;
  by_discipline: Record<string, DisciplineCompliance>;
  strength: Record<string, StrengthCompliance>;
  bricks: { days: BrickDay[]; planned: number; completed: number; pct: number | null; flag: boolean };
  sessions: PlannedSlot[];
  extras: { name: string; date: string; sport: string; duration_min: number }[];
  flag_threshold_pct: number;
}

export interface ComplianceRange {
  weeks: WeekCompliance[];
  plan_synced_at: string | null;
  note: string;
}

// --- Training load (PMC) -----------------------------------------------------

export interface PmcPoint {
  date: string;
  load: number;
  ctl: number;
  atl: number;
  tsb: number;
  by_sport: Record<string, number>;
}

export interface PmcResponse {
  series: PmcPoint[];
  current: PmcPoint | null;
  ctl_ramp_7d: number | null;
  first_load_date: string | null;
  estimated_sessions: number;
  total_sessions: number;
  methodology_note: string;
}

// --- Goal gap + recovery trend ---------------------------------------------

export interface GoalLeg {
  leg: "swim" | "bike" | "run";
  budget_s: number;
  projected_s: number | null;
  delta_s: number | null;
  basis: string | null;
  source: string | null;
  estimate_date: string | null;
  assumption: string;
}

export interface GoalGap {
  target_low_s: number;
  target_high_s: number;
  transitions_s: number;
  legs: GoalLeg[];
  projected_total_s: number;
  delta_to_target_high_s: number;
  delta_to_target_low_s: number;
  complete: boolean;
  missing_legs: string[];
  required: {
    css_pace_s_per_100m: number;
    ftp_w: number;
    hm_standalone_s: number;
    run_pace_s_per_km: number;
  };
  race_date: string | null;
  days_to_race: number | null;
  note: string;
}

export interface RecoveryTrendPoint {
  date: string;
  hrv: number | null;
  rhr: number | null;
  hrv_7d: number | null;
  rhr_7d: number | null;
}

export interface RecoveryMetricTrend {
  unit: string;
  rolling_7d: number | null;
  baseline: {
    value: number | null;
    method: "manual" | "snapshot_28d" | "auto_28d" | "insufficient_history";
    effective_from: string | null;
    sd: number | null;
    n: number;
  };
  deviation_pct: number | null;
  flag: "normal" | "below_normal" | "above_normal" | null;
  readings: number;
  first_reading: string | null;
}

export interface RecoveryTrend {
  series: RecoveryTrendPoint[];
  metrics: { hrv: RecoveryMetricTrend; rhr: RecoveryMetricTrend };
}

// --- Academic trajectory ------------------------------------------------------

export interface WeightedHistory {
  academic_year: string;
  snapshots: {
    recorded_on: string;
    weighted_average_pct: number;
    classification_estimate: string | null;
    modules_counted: number;
  }[];
  first_threshold_pct: number;
  current_pct: number | null;
  modules_missing_level_credits: string[];
  note: string;
}

export type DeadlineKind = "assignment" | "exam" | "test" | "other";

export interface Deadline {
  id: number;
  module_id: number | null;
  module_name: string | null;
  assessment_id: number | null;
  assessment_name: string | null;
  title: string;
  due_at: string;
  kind: DeadlineKind;
  weight_pct: number | null;
  status: "pending" | "submitted";
  note: string | null;
  days_until: number;
  overdue: boolean;
}

export interface DeadlineInput {
  title: string;
  due_at: string;
  kind: DeadlineKind;
  module_id?: number | null;
  assessment_id?: number | null;
  weight_pct?: number | null;
  note?: string | null;
}

export interface StudyWeek {
  week_start: string;
  logged_hours: number;
  target_hours: number | null;
  target_source: "manual" | "calendar" | null;
  calendar_planned_hours: number;
  pct: number | null;
  in_progress: boolean;
  flag: boolean;
}

export interface StudyLog {
  id: number;
  date: string;
  hours: number;
  module_id: number | null;
  note: string | null;
}

export interface StudySummary {
  weeks: StudyWeek[];
  recent_logs: StudyLog[];
  manual_target_hours: number | null;
  flag_threshold_pct: number;
  note: string;
}

export interface PrepItem {
  id: number;
  module_id: number;
  kind: "topic" | "past_paper";
  title: string;
  done: boolean;
  done_on: string | null;
}

export interface ModulePrep {
  module_id: number;
  module_name: string;
  total: number;
  done: number;
  pct: number | null;
  topics_done: number;
  topics_total: number;
  papers_done: number;
  papers_total: number;
  items: PrepItem[];
}

// --- Load vs deadlines overlay ------------------------------------------------

export interface OverlayWeek {
  week_start: string;
  state: "past" | "current" | "future";
  actual_load: number;
  projected_load: number | null;
  total_load: number | null;
  chronic_weekly_load: number;
  elevated_above: number | null;
  load_ratio: number | null;
  planned_sessions: number;
  planned_hours: number;
  training_elevated: boolean;
  deadlines: { title: string; kind: string; due_at: string; module_name: string | null; status: string }[];
  deadline_count: number;
  exam_count: number;
  deadline_elevated: boolean;
  risk: boolean;
}

export interface Overlay {
  weeks: OverlayWeek[];
  load_per_hour_by_discipline: Record<string, number>;
  current_ctl: number;
  acwr_threshold: number;
  deadline_count_threshold: number;
  risk_weeks: string[];
  note: string;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export const api = {
  getDisciplineWeeks: (weeks = 12) =>
    request<WeekDisciplineRollup[]>(`/training/weeks?weeks=${weeks}`),
  getCompliance: (weeksBack = 6, weeksAhead = 1) =>
    request<ComplianceRange>(`/compliance/weeks?weeks_back=${weeksBack}&weeks_ahead=${weeksAhead}`),
  setSessionStatus: (ids: number[], manualStatus: "done" | "skipped" | null) =>
    request("/compliance/sessions", json("PATCH", { ids, manual_status: manualStatus })),
  syncPlan: () => request("/compliance/sync", { method: "POST" }),
  getPmc: (days = 120) => request<PmcResponse>(`/load/pmc?days=${days}`),
  getGoalGap: () => request<GoalGap>("/performance/goal-gap"),
  getOverlay: (weeksBack = 6, weeksAhead = 10) =>
    request<Overlay>(`/overview/load-vs-deadlines?weeks_back=${weeksBack}&weeks_ahead=${weeksAhead}`),

  updateModule: (id: number, update: { fheq_level?: number | null; credits?: number | null }) =>
    request<ModuleOut>(`/academic/modules/${id}`, json("PATCH", update)),
  getWeightedHistory: (academicYear: string) =>
    request<WeightedHistory>(`/academic/history?academic_year=${encodeURIComponent(academicYear)}`),
  getDeadlines: () => request<Deadline[]>("/academic/deadlines"),
  createDeadline: (d: DeadlineInput) => request<Deadline>("/academic/deadlines", json("POST", d)),
  updateDeadline: (id: number, update: Partial<DeadlineInput> & { status?: "pending" | "submitted" }) =>
    request<Deadline>(`/academic/deadlines/${id}`, json("PATCH", update)),
  deleteDeadline: (id: number) => request(`/academic/deadlines/${id}`, { method: "DELETE" }),
  getStudy: (weeks = 8) => request<StudySummary>(`/academic/study?weeks=${weeks}`),
  logStudy: (entry: { date: string; hours: number; module_id?: number | null; note?: string | null }) =>
    request<StudyLog>("/academic/study/logs", json("POST", entry)),
  deleteStudyLog: (id: number) => request(`/academic/study/logs/${id}`, { method: "DELETE" }),
  setStudyTarget: (weeklyHours: number) =>
    request("/academic/study/target", json("POST", { weekly_hours: weeklyHours })),
  clearStudyTarget: () => request("/academic/study/target", { method: "DELETE" }),
  getPrep: (academicYear: string) =>
    request<ModulePrep[]>(`/academic/prep?academic_year=${encodeURIComponent(academicYear)}`),
  addPrepItem: (item: { module_id: number; title: string; kind: "topic" | "past_paper" }) =>
    request<PrepItem>("/academic/prep", json("POST", item)),
  togglePrepItem: (id: number, done: boolean) =>
    request<PrepItem>(`/academic/prep/${id}?done=${done}`, { method: "PATCH" }),
  deletePrepItem: (id: number) => request(`/academic/prep/${id}`, { method: "DELETE" }),
  getRecoveryTrend: (days = 42) => request<RecoveryTrend>(`/garmin/trend?days=${days}`),
  setRecoveryBaseline: (metric: "hrv" | "rhr", value?: number) =>
    request("/garmin/baselines", json("POST", { metric, value: value ?? null })),
  clearRecoveryBaseline: (metric: "hrv" | "rhr") =>
    request(`/garmin/baselines/${metric}`, { method: "DELETE" }),

  getGates: () => request<Gate[]>("/performance/gates"),
  updateGateItem: (key: string, update: GateItemUpdate) =>
    request<Gate[]>(`/performance/gates/${key}`, json("PATCH", update)),
  getMilestones: () => request<Milestone[]>("/performance/milestones"),
  updateMilestone: (
    id: number,
    update: { done?: boolean; target_date?: string | null; note?: string | null }
  ) => request<Milestone>(`/performance/milestones/${id}`, json("PATCH", update)),
  getThresholds: () => request<ThresholdHistory>("/performance/thresholds"),
  createThreshold: (t: {
    test_date: string;
    metric: string;
    value: number;
    protocol?: string | null;
    note?: string | null;
  }) => request<ThresholdTest>("/performance/thresholds", json("POST", t)),
  deleteThreshold: (id: number) =>
    request(`/performance/thresholds/${id}`, { method: "DELETE" }),
  getInjuries: () => request<InjurySummary>("/performance/injuries"),
  createInjury: (e: { date: string; body_region: string; pain_scale: number; note?: string | null }) =>
    request<InjuryEntry>("/performance/injuries", json("POST", e)),
  deleteInjury: (id: number) => request(`/performance/injuries/${id}`, { method: "DELETE" }),

  getAcademicSummary: (academicYear: string) =>
    request<ClassificationSummary>(
      `/academic/summary?academic_year=${encodeURIComponent(academicYear)}`
    ),
  getModules: (academicYear: string) =>
    request<ModuleOut[]>(
      `/academic/modules?academic_year=${encodeURIComponent(academicYear)}`
    ),
  getWeekSummary: (weekStartDate: string) =>
    request<WeekSummary>(`/training/week?week_start_date=${weekStartDate}`),
  getCompetitors: () => request<CompetitorOut[]>("/competitors"),
  createCompetitor: (name: string, note?: string) =>
    request<CompetitorOut>("/competitors", {
      method: "POST",
      body: JSON.stringify({ name, note: note ?? null }),
    }),
  logCompetitorActivity: (competitorId: number, activity: CompetitorActivityInput) =>
    request(`/competitors/${competitorId}/activities`, {
      method: "POST",
      body: JSON.stringify(activity),
    }),
  compareWeek: (weekStartDate: string) =>
    request<WeekComparison>(`/competitors/compare?week_start_date=${weekStartDate}`),

  getNutritionPlan: () => request<NutritionPlan>("/nutrition/plan"),
  getNutritionDay: (day: string) =>
    request<NutritionDaySummary>(`/nutrition/day?day=${day}`),
  logMeal: (entry: { date: string; slot: string; description: string; followed_plan?: boolean }) =>
    request<NutritionLogOut>("/nutrition/log", {
      method: "POST",
      body: JSON.stringify(entry),
    }),
  getSupplementDay: (day: string) =>
    request<SupplementDaySummary>(`/nutrition/supplements/day?day=${day}`),
  logSupplement: (date: string, supplementId: number, taken = true) =>
    request("/nutrition/supplements/log", {
      method: "POST",
      body: JSON.stringify({ date, supplement_id: supplementId, taken }),
    }),

  getWeekSchedule: (weekStartDate: string) =>
    request<WeekSchedule>(`/calendar/week?week_start_date=${weekStartDate}`),

  getGarminToday: () => request<GarminDailyMetric | null>("/garmin/today"),
};
