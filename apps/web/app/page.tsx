import { HealthStatus } from "@/components/HealthStatus";
import { EmptyState } from "@/components/patterns/empty-state";
import { PageHeader } from "@/components/patterns/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function HomePage() {
  return (
    <>
      <PageHeader
        title="Your learning workspace"
        description="Turn supported video transcripts into lessons, summaries and cited answers."
        actions={
          <Button type="button" disabled aria-describedby="add-source-hint">
            Add source
          </Button>
        }
      />
      <p id="add-source-hint" className="sr-only">
        Source import arrives in a later phase. This control is disabled.
      </p>

      <section
        aria-label="Workspace overview"
        className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        {[
          { label: "Videos ready", value: "—" },
          { label: "Playlists", value: "—" },
          { label: "Processing", value: "—" },
          { label: "Pending transcripts", value: "—" },
        ].map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="pb-2">
              <CardDescription>{kpi.label}</CardDescription>
              <CardTitle className="text-2xl tabular-nums">{kpi.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <EmptyState
          title="Continue learning"
          description="No ready lessons yet. Import a permitted transcript in a later phase to start studying."
        />
        <Card>
          <CardHeader>
            <CardTitle>Infrastructure</CardTitle>
            <CardDescription>
              Connectivity check for Neon Postgres and Qdrant Cloud (fixture shell).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <HealthStatus />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
