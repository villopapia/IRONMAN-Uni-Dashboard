/** 7300 -> "2:01:40", 400 -> "6:40". */
export function fmtDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null || !isFinite(totalSeconds)) return "—";
  const neg = totalSeconds < 0;
  let s = Math.round(Math.abs(totalSeconds));
  const h = Math.floor(s / 3600);
  s -= h * 3600;
  const m = Math.floor(s / 60);
  const sec = s - m * 60;
  const body = h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
  return neg ? `-${body}` : body;
}

/** "1:55:00" / "6:40" / "95" -> seconds; null if unparseable. */
export function parseDuration(input: string): number | null {
  const parts = input.trim().split(":");
  if (parts.length === 0 || parts.length > 3 || parts.some((p) => p === "" || isNaN(Number(p)))) {
    return null;
  }
  return parts.reduce((acc, p) => acc * 60 + Number(p), 0);
}

/** Format a threshold / gate value for its unit. */
export function fmtMetric(value: number | null | undefined, unit: string | null | undefined): string {
  if (value == null) return "—";
  switch (unit) {
    case "s":
      return fmtDuration(value);
    case "s/100m":
      return `${fmtDuration(value)}/100m`;
    case "s/km":
      return `${fmtDuration(value)}/km`;
    case "W":
      return `${Math.round(value)} W`;
    case "bpm":
      return `${Math.round(value)} bpm`;
    default:
      return unit ? `${value} ${unit}` : String(value);
  }
}

export function fmtShortDate(iso: string): string {
  return new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

/** Mon–Sun week label from its Monday start date: "6–12 Jul" or, spanning a
 * month boundary, "28 Sep – 4 Oct". A single "Jul 6" reads as one day's data
 * on a chart whose bars are actually weekly totals - the range makes that
 * explicit. */
export function fmtWeekRange(weekStartIso: string): string {
  const start = new Date(weekStartIso + (weekStartIso.length === 10 ? "T00:00:00" : ""));
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const sameMonth = start.getMonth() === end.getMonth();
  const day = (d: Date) => d.toLocaleDateString(undefined, { day: "numeric" });
  const dayMonth = (d: Date) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return sameMonth
    ? `${day(start)}–${dayMonth(end)}`
    : `${dayMonth(start)} – ${dayMonth(end)}`;
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
