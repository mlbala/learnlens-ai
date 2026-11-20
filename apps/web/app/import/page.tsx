"use client";

import { useState } from "react";

import { FixtureModeBanner } from "@/components/library/fixture-mode-banner";
import { ImportSourceDialog } from "@/components/library/import-source-dialog";
import { PageHeader } from "@/components/patterns/page-header";
import { Button } from "@/components/ui/button";
import { resolveLibraryMode } from "@/lib/library/client";

export default function ImportPage() {
  const [open, setOpen] = useState(true);
  const mode = resolveLibraryMode();

  return (
    <>
      <PageHeader
        title="Import source"
        description="Add a YouTube video or playlist URL. Transcript access always requires a separate attested upload."
        actions={
          <Button type="button" onClick={() => setOpen(true)}>
            Open import form
          </Button>
        }
      />
      <FixtureModeBanner mode={mode} />
      <ImportSourceDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
