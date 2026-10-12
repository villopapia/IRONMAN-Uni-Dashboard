interface StatTileProps {
  label: string;
  value: string | null;
  sub?: string | null;
  accent?: string;
}

export default function StatTile({ label, value, sub, accent }: StatTileProps) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-neutral-500">{label}</div>
      <div
        className="mt-0.5 break-words text-xl font-semibold text-white"
        style={accent ? { color: accent } : undefined}
      >
        {value ?? "—"}
      </div>
      {sub && <div className="text-xs text-neutral-500">{sub}</div>}
    </div>
  );
}
