export function mostRecentMonday(): string {
  const now = new Date();
  const day = now.getDay();
  const diff = (day === 0 ? -6 : 1) - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + diff);
  return monday.toISOString().slice(0, 10);
}

// The backend serializes naive UTC datetimes (Python's datetime.utcnow(),
// via FastAPI/Pydantic) without a timezone suffix, e.g.
// "2026-09-23T14:24:56.705596". JS's Date constructor treats a timestamp
// string with no offset/Z as LOCAL time, not UTC - during BST that silently
// added an hour to every "synced Xh ago" reading. Append Z when there's no
// timezone designator already, so it's parsed as the UTC time it actually is.
function parseUtc(isoTimestamp: string): Date {
  const hasTz = /Z$|[+-]\d\d:?\d\d$/.test(isoTimestamp);
  return new Date(hasTz ? isoTimestamp : `${isoTimestamp}Z`);
}

export function timeAgo(isoTimestamp: string): string {
  const diffMs = Date.now() - parseUtc(isoTimestamp).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}
