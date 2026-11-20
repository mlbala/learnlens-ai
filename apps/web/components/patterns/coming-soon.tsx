import { EmptyState } from "@/components/patterns/empty-state";
import { PageHeader } from "@/components/patterns/page-header";

type ComingSoonProps = {
  title: string;
  description?: string;
};

/** Shell placeholder for IA destinations not built until later phases. */
export function ComingSoon({
  title,
  description = "This screen is reserved in the navigation. Functional content arrives in a later phase.",
}: ComingSoonProps) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState
        title="Not available yet"
        description="Phase 09 ships the design system and app shell only. Library, import, and lesson screens follow in phases 10–11."
      />
    </>
  );
}
