// Validated dark-mode palette (dataviz skill's reference instance) - shared
// across charts and UI chrome so colors mean the same thing everywhere.

export const surface = {
  page: "#0d0d0d",
  card: "#1a1a19",
  cardHover: "#212120",
  border: "rgba(255,255,255,0.08)",
};

export const ink = {
  primary: "#ffffff",
  secondary: "#c3c2b7",
  muted: "#898781",
  gridline: "#2c2c2a",
  baseline: "#383835",
};

export const status = {
  good: "#0ca30c",
  warning: "#fab219",
  serious: "#ec835a",
  critical: "#d03b3b",
};

// Performance Management Chart series. Deliberately NOT the sport hues
// (blue/orange/aqua already mean run/bike/swim on this page) and not the
// status red/green. Validated as a set with the dataviz skill's
// validate_palette.js --mode dark on #1a1a19: all checks pass (worst adjacent
// CVD dE 13.2, normal-vision dE 19.3, all >= 3:1 contrast).
export const LOAD_COLORS = {
  ctl: "#9085e9", // violet - fitness
  atl: "#d55181", // magenta - fatigue
  tsb: "#c98500", // yellow - form
};

// Fixed categorical order - identity follows the sport, never cycled.
export const SPORT_COLORS: Record<string, string> = {
  run: "#3987e5", // blue
  bike: "#d95926", // orange
  swim: "#199e70", // aqua
  gym: "#c98500", // yellow
  walk: "#d55181", // magenta
  other: ink.muted, // uncategorized - neutral, not a "real" series
};
