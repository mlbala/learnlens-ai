import { LibraryBrowser } from "@/components/library/library-browser";

export const metadata = { title: "Videos" };

export default function VideosPage() {
  return (
    <LibraryBrowser
      initialKind="videos"
      title="Videos"
      description="Imported video metadata and transcript readiness."
    />
  );
}
