interface StatTileProps {
  label: string;
  value: string | null;
  accent?: string;
}

export default function StatTile({ label, value, accent }: StatTileProps) {
  return (
    <div>
      <div className="text-xs text-neutral-500">{label}</div>
      <div
        className="mt-0.5 text-2xl font-semibold text-white"
        style={accent ? { color: accent } : undefined}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}
