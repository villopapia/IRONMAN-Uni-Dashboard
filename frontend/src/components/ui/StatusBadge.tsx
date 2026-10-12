import { AlertTriangle, CheckCircle2, Circle, Clock, XCircle } from "lucide-react";
import { ink, status as statusColors } from "@/lib/palette";

export type BadgeTone = "good" | "warning" | "serious" | "critical" | "neutral";

/** The PASS / AMBER / RED / NO DATA badge every status panel uses. */
export const FLAG_BADGE: Record<"pass" | "amber" | "red" | "no_data", [BadgeTone, string]> = {
  pass: ["good", "PASS"],
  amber: ["warning", "AMBER"],
  red: ["critical", "RED"],
  no_data: ["neutral", "NO DATA"],
};

const TONE_COLOR: Record<BadgeTone, string> = {
  good: statusColors.good,
  warning: statusColors.warning,
  serious: statusColors.serious,
  critical: statusColors.critical,
  neutral: ink.muted,
};

const TONE_ICON = {
  good: CheckCircle2,
  warning: AlertTriangle,
  serious: AlertTriangle,
  critical: XCircle,
  neutral: Clock,
};

/** Status is never color-alone: always icon + text label alongside the hue. */
export default function StatusBadge({
  tone,
  label,
  compact = false,
}: {
  tone: BadgeTone;
  label: string;
  compact?: boolean;
}) {
  const Icon = TONE_ICON[tone] ?? Circle;
  const color = TONE_COLOR[tone];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full font-medium ${
        compact ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-xs"
      }`}
      style={{ background: `${color}1f` }}
    >
      <Icon size={compact ? 11 : 13} style={{ color }} strokeWidth={2.25} />
      <span className="text-neutral-200">{label}</span>
    </span>
  );
}
