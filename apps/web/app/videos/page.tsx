import { Suspense } from "react";

import { LibraryBrowser } from "@/components/library/library-browser";

export const metadata = { title: "Videos" };

export default function VideosPage() {
  return (
    <Suspense>
      <LibraryBrowser
        initialKind="videos"
        title="Videos"
        description="Paste a public YouTube link. Gemini builds the lesson from the video."
      />
    </Suspense>
  );
}
