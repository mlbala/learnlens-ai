import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  FIXTURE_MODE_DESCRIPTION,
  FIXTURE_MODE_LABEL,
} from "@/lib/library/fixtures";
import type { LibraryClientMode } from "@/lib/library/client";

type FixtureModeBannerProps = {
  mode: LibraryClientMode;
};

export function FixtureModeBanner({ mode }: FixtureModeBannerProps) {
  if (mode !== "fixture") return null;
  return (
    <Alert variant="warning" className="mb-6" role="status">
      <AlertTitle>{FIXTURE_MODE_LABEL}</AlertTitle>
      <AlertDescription>{FIXTURE_MODE_DESCRIPTION}</AlertDescription>
    </Alert>
  );
}
