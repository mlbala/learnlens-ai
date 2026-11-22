import { cn } from "@/lib/utils";

type BrandMarkProps = {
  className?: string;
};

/** Event-horizon mark. Same shape as the browser tab icon. */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      aria-hidden
      className={cn("h-7 w-7 shrink-0", className)}
    >
      <rect width="32" height="32" rx="8" fill="#0B1220" />
      <circle cx="16" cy="16" r="9" fill="none" stroke="#E8EEF9" strokeWidth="1.6" />
      <circle cx="16" cy="16" r="3.4" fill="#0B1220" stroke="#7DD3FC" strokeWidth="1.4" />
      <path
        d="M8.1 13.1c1.7-3.4 4.8-5.5 7.9-5.5 3.2 0 6.2 2.1 7.9 5.5"
        fill="none"
        stroke="#38BDF8"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}
