export default function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded bg-white/[0.06] ${className ?? "h-4 w-full"}`} />
  );
}
