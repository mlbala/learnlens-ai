import { VideoDetail } from "@/components/library/video-detail";

type PageProps = {
  params: Promise<{ videoId: string }>;
};

export async function generateMetadata({ params }: PageProps) {
  const { videoId } = await params;
  return { title: `Video ${videoId.slice(0, 8)}` };
}

export default async function VideoDetailPage({ params }: PageProps) {
  const { videoId } = await params;
  return <VideoDetail videoId={videoId} />;
}
