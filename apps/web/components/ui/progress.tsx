import * as React from "react";

import { cn } from "@/lib/utils";

type ProgressProps = React.HTMLAttributes<HTMLDivElement> & {
  value: number;
  max?: number;
  label?: string;
};

export function Progress({
  value,
  max = 100,
  label,
  className,
  ...props
}: ProgressProps) {
  const pct = max <= 0 ? 0 : Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(pct)}
      aria-label={label}
      className={cn(
        "h-2 w-full overflow-hidden rounded-full bg-surface-muted",
        className,
      )}
      {...props}
    >
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-150 motion-reduce:transition-none"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
