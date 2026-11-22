import Link from "next/link";

import { PageHeader } from "@/components/patterns/page-header";
import { LearningHistorySetting } from "@/components/settings/learning-history-setting";

export const metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader
        title="Settings"
        description="Workspace preferences and usage. Provider keys stay server-side."
      />
      <section className="max-w-xl space-y-4">
        <LearningHistorySetting />
        <p className="text-sm text-muted-foreground">
          Manage estimated spend and period quotas. Figures are{" "}
          <strong className="font-medium text-foreground">estimates only</strong> — not
          live vendor billing.
        </p>
        <Link
          href="/settings/usage"
          className="inline-flex h-10 items-center justify-center rounded-[var(--radius-control)] bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
        >
          View usage &amp; estimates
        </Link>
      </section>
    </>
  );
}
