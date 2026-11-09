import { cn } from "@/lib/utils";

export function BrandMark({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm ring-1 ring-black/5">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="size-4.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5z" />
          <path d="M12 12v9" />
          <path d="m4 7.5 8 4.5 8-4.5" />
        </svg>
      </div>
      {!compact ? (
        <span className="text-[15px] font-semibold tracking-tight">
          Dossier
        </span>
      ) : null}
    </div>
  );
}
