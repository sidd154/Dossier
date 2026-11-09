"use client";

import { cn } from "@/lib/utils";

export interface SelectionOption {
  id: string;
  label: string;
  hint?: string;
}

export function SelectionList({
  options,
  selected,
  onToggle,
  emptyLabel = "Nothing available",
  maxHeight = "max-h-48",
}: {
  options: SelectionOption[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  emptyLabel?: string;
  maxHeight?: string;
}) {
  if (!options.length) {
    return (
      <p className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
        {emptyLabel}
      </p>
    );
  }

  return (
    <div
      className={cn(
        "space-y-0.5 overflow-y-auto rounded-lg border p-1.5",
        maxHeight,
      )}
    >
      {options.map((option) => (
        <label
          key={option.id}
          className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-muted/60"
        >
          <input
            type="checkbox"
            className="size-4 rounded border-input accent-primary"
            checked={selected.has(option.id)}
            onChange={() => onToggle(option.id)}
          />
          <span className="min-w-0 flex-1 truncate">{option.label}</span>
          {option.hint ? (
            <span className="shrink-0 text-xs text-muted-foreground">
              {option.hint}
            </span>
          ) : null}
        </label>
      ))}
    </div>
  );
}
