import { notFound } from "next/navigation";

import { PUBLICATION_MANIFESTS } from "@/config/publications";
import { type LocalStorageReadingLocation } from "@/components/Epub/StatefulReader";
import { type ReadingLocationResponse } from "@/lib/api";
import { serverFetchJson } from "@/lib/proxy";

import ReaderClientPage from "./ReaderClientPage";

export const runtime = "nodejs";

type Params = { identifier: string };

type Props = {
  params: Promise<Params>;
};

async function fetchLatestReadingLocation(
  publicationId: string,
): Promise<LocalStorageReadingLocation | null> {
  if (!publicationId) return null;

  const data = await serverFetchJson<ReadingLocationResponse>({
    upstreamPath: "/api/reading-locations/latest",
    params: { publication_id: publicationId },
  });

  if (!data) return null;

  // The API returns a plain JSON locator; the Readium navigator accepts it
  // at runtime even though LocalStorageReadingLocation types it as a class.
  return {
    publicationId: data.publication_id || publicationId,
    locator: data.locator as LocalStorageReadingLocation["locator"],
    recordedAt: data.recorded_at ?? undefined,
  } satisfies LocalStorageReadingLocation;
}

export default async function BookPage({ params }: Props) {
  const { identifier: urlSlug } = await params;
  const publicationConfig =
    PUBLICATION_MANIFESTS[urlSlug as keyof typeof PUBLICATION_MANIFESTS];

  if (!publicationConfig) {
    notFound();
  }

  const serverInitialReadingLocation = await fetchLatestReadingLocation(
    publicationConfig.id,
  );

  return (
    <ReaderClientPage
      publicationConfig={publicationConfig}
      serverInitialReadingLocation={serverInitialReadingLocation}
    />
  );
}
