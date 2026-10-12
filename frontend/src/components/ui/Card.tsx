import { ReactNode } from "react";
import { Info, LucideIcon } from "lucide-react";

interface CardProps {
  icon?: LucideIcon;
  title: string;
  /** Methodology / how-to-read note, shown on hover or focus of an info icon beside the title. */
  info?: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
}

export default function Card({ icon: Icon, title, info, meta, children, className }: CardProps) {
  return (
    <div
      className={`rounded-2xl border border-white/[0.08] bg-[#1a1a19] p-5 shadow-lg shadow-black/20 transition-colors ${className ?? ""}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={18} className="text-neutral-400" strokeWidth={1.75} />}
          <h2 className="text-base font-semibold text-white">{title}</h2>
          {info && (
            <span className="group relative inline-flex cursor-help rounded-full outline-none focus-visible:ring-1 focus-visible:ring-white/40" tabIndex={0} aria-label={`About ${title}`}>
              <Info size={14} className="text-neutral-500 group-hover:text-neutral-300" />
              <span
                role="tooltip"
                className="invisible absolute left-0 top-6 z-20 w-80 max-w-[75vw] rounded-lg border border-white/[0.08] bg-[#212120] p-3 text-xs font-normal leading-relaxed text-neutral-300 shadow-lg shadow-black/40 group-hover:visible group-focus:visible"
              >
                {info}
              </span>
            </span>
          )}
        </div>
        {meta && <span className="text-sm text-neutral-400">{meta}</span>}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}
