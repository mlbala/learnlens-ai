import { Suspense } from "react";

import { LibraryBrowser } from "@/components/library/library-browser";

export const metadata = { title: "Playlists" };

export default function PlaylistsPage() {
  return (
    <Suspense>
      <LibraryBrowser
        initialKind="playlists"
        title="Playlists"
        description="This list is official playlist metadata and permitted transcripts, separate from a pasted video lesson."
      />
    </Suspense>
  );
}
