import { UsageDashboard } from "@/features/usage/usage-dashboard";
import { PageHeader } from "@/components/patterns/page-header";

export const metadata = { title: "Usage" };

export default function UsagePage() {
  return (
    <>
      <PageHeader
        title="Usage & cost estimates"
        description="Period quotas and estimated provider spend for this workspace."
      />
      <UsageDashboard />
    </>
  );
}
