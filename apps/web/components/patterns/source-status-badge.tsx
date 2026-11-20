import { Badge } from "@/components/ui/badge";
import { presentStatus, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

const toneToVariant: Record<
  StatusTone,
  "secondary" | "success" | "warning" | "danger" | "info"
> = {
  neutral: "secondary",
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info",
};

type SourceStatusBadgeProps = {
  status: string;
  className?: string;
};

export function SourceStatusBadge({ status, className }: SourceStatusBadgeProps) {
  const presented = presentStatus(status);
  return (
    <Badge
      variant={toneToVariant[presented.tone]}
      className={cn(className)}
      title={presented.actionHint}
    >
      {presented.label}
    </Badge>
  );
}
