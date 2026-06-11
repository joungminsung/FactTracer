import { SiteHeader } from "@/components/site-header";
import { PodcastHomeClient } from "@/components/podcast/podcast-home-client";
import { getPodcastHome, emptyPodcastHome } from "@/lib/api/podcasts";
import { getServerAccessToken } from "@/lib/auth/server-session";
import type { PodcastHomeResponse } from "@/lib/api/types";

export default async function PodcastsPage() {
  const accessToken = await getServerAccessToken();
  let home: PodcastHomeResponse = emptyPodcastHome;

  try {
    home = await getPodcastHome(accessToken);
  } catch {
    home = emptyPodcastHome;
  }

  return (
    <div className="min-h-screen bg-white pb-24 text-gray-950">
      <SiteHeader />
      <main className="mx-auto max-w-[1520px] px-5 pb-14 pt-6 sm:px-7 lg:px-9">
        <PodcastHomeClient home={home} />
      </main>
    </div>
  );
}
