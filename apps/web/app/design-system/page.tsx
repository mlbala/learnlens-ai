import { EmptyState } from "@/components/patterns/empty-state";
import { ErrorState } from "@/components/patterns/error-state";
import { PageHeader } from "@/components/patterns/page-header";
import { PageSkeleton } from "@/components/patterns/page-skeleton";
import { ProviderBadge } from "@/components/patterns/provider-badge";
import { SourceStatusBadge } from "@/components/patterns/source-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CONTENT_TABS } from "@/lib/navigation";

export const metadata = { title: "Design system" };

const DEMO_STATUSES = [
  "needs_transcript",
  "queued",
  "ready",
  "failed_retryable",
  "not_authorized",
  "unavailable",
] as const;

/** Cheap component gallery — Storybook deferred; fixture UI only. */
export default function DesignSystemPage() {
  return (
    <>
      <PageHeader
        title="Design system"
        description="Formal enterprise tokens and shell primitives. No gradients, no glassmorphism. Fixture preview only."
        actions={
          <>
            <Button type="button">Primary</Button>
            <Button type="button" variant="secondary">
              Secondary
            </Button>
            <Button type="button" variant="outline">
              Outline
            </Button>
          </>
        }
      />

      <div className="space-y-10">
        <section aria-labelledby="tokens-heading">
          <h2 id="tokens-heading" className="mb-4 text-lg font-semibold">
            Color tokens
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(
              [
                ["background", "bg-background"],
                ["surface", "bg-surface"],
                ["primary", "bg-primary"],
                ["success", "bg-success"],
                ["warning", "bg-warning"],
                ["danger", "bg-danger"],
                ["border", "bg-border"],
                ["muted", "bg-surface-muted"],
              ] as const
            ).map(([name, swatch]) => (
              <div
                key={name}
                className="overflow-hidden rounded-[var(--radius-card)] border border-border"
              >
                <div className={`h-14 ${swatch}`} />
                <p className="px-3 py-2 text-xs text-muted-foreground">{name}</p>
              </div>
            ))}
          </div>
        </section>

        <Separator />

        <section aria-labelledby="status-heading">
          <h2 id="status-heading" className="mb-4 text-lg font-semibold">
            Status badges
          </h2>
          <div className="flex flex-wrap gap-2">
            {DEMO_STATUSES.map((status) => (
              <SourceStatusBadge key={status} status={status} />
            ))}
            <ProviderBadge providerLabel="fake" configured />
            <ProviderBadge providerLabel="openai" configured={false} />
            <Badge>Default</Badge>
          </div>
        </section>

        <Separator />

        <section aria-labelledby="forms-heading">
          <h2 id="forms-heading" className="mb-4 text-lg font-semibold">
            Forms & alerts
          </h2>
          <div className="grid max-w-xl gap-4">
            <div className="space-y-2">
              <Label htmlFor="demo-url">YouTube URL</Label>
              <Input
                id="demo-url"
                placeholder="https://www.youtube.com/watch?v=…"
                aria-describedby="demo-url-help"
              />
              <p id="demo-url-help" className="text-xs text-muted-foreground">
                Fixture field — import wiring arrives later.
              </p>
            </div>
            <Alert>
              <AlertTitle>Honest coverage</AlertTitle>
              <AlertDescription>
                A pasted public URL alone does not guarantee a transcript.
              </AlertDescription>
            </Alert>
            <ErrorState message="Request failed. No private content is shown." />
          </div>
        </section>

        <Separator />

        <section aria-labelledby="tabs-heading">
          <h2 id="tabs-heading" className="mb-4 text-lg font-semibold">
            Content tabs pattern
          </h2>
          <Tabs defaultValue="Overview">
            <TabsList aria-label="Lesson sections" className="flex h-auto flex-wrap">
              {CONTENT_TABS.map((tab) => (
                <TabsTrigger key={tab} value={tab} disabled={tab !== "Overview"}>
                  {tab}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="Overview">
              <Card>
                <CardHeader>
                  <CardTitle>Overview</CardTitle>
                  <CardDescription>
                    Disabled tabs have no source data yet — shown with explanation, not hidden.
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  Secondary content navigation from the design system IA.
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </section>

        <Separator />

        <section aria-labelledby="states-heading">
          <h2 id="states-heading" className="mb-4 text-lg font-semibold">
            Empty, loading, skeleton
          </h2>
          <div className="grid gap-6 lg:grid-cols-2">
            <EmptyState
              title="No sources yet"
              description="Add a permitted transcript when import screens ship."
              action={
                <Button type="button" variant="outline" disabled>
                  Add source
                </Button>
              }
            />
            <div className="rounded-[var(--radius-panel)] border border-border bg-surface p-5">
              <p className="mb-4 text-sm text-muted-foreground">Page skeleton</p>
              <PageSkeleton />
              <div className="mt-4 flex gap-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
