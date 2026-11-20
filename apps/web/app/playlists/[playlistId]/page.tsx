import { PlaylistDetail } from "@/components/library/playlist-detail";

type PageProps = {
  params: Promise<{ playlistId: string }>;
};

export async function generateMetadata({ params }: PageProps) {
  const { playlistId } = await params;
  return { title: `Playlist ${playlistId.slice(0, 8)}` };
}

export default async function PlaylistDetailPage({ params }: PageProps) {
  const { playlistId } = await params;
  return <PlaylistDetail playlistId={playlistId} />;
}
