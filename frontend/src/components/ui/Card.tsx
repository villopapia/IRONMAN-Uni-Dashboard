import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

interface CardProps {
  icon?: LucideIcon;
  title: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
}

export default function Card({ icon: Icon, title, meta, children, className }: CardProps) {
  return (
    <div
      className={`rounded-2xl border border-white/[0.08] bg-[#1a1a19] p-5 shadow-lg shadow-black/20 transition-colors ${className ?? ""}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={18} className="text-neutral-400" strokeWidth={1.75} />}
          <h2 className="text-base font-semibold text-white">{title}</h2>
        </div>
        {meta && <span className="text-sm text-neutral-400">{meta}</span>}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}
