import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type ProviderBadgeProps = {
  /** Display-only provider name; never show raw API keys. */
  providerLabel: string;
  configured?: boolean;
  className?: string;
};

export function ProviderBadge({
  providerLabel,
  configured = true,
  className,
}: ProviderBadgeProps) {
  return (
    <Badge
      variant={configured ? "info" : "warning"}
      className={cn("font-normal", className)}
      aria-label={`Text provider: ${providerLabel}, ${configured ? "configured" : "not configured"}`}
    >
      {providerLabel}
      <span className="ml-1 text-[10px] uppercase tracking-wide opacity-80">
        {configured ? "ok" : "missing"}
      </span>
    </Badge>
  );
}
