import { LibraryBrowser } from "@/components/library/library-browser";

export const metadata = { title: "Playlists" };

export default function PlaylistsPage() {
  return (
    <LibraryBrowser
      initialKind="playlists"
      title="Playlists"
      description="Ordered collections with honest ready / missing / unavailable coverage."
    />
  );
}
