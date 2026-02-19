import { AccessTokenError } from "@auth0/nextjs-auth0/errors";
import { notFound } from "next/navigation";

import { PUBLICATION_MANIFESTS } from "@/config/publications";
import { auth0 } from "@/lib/auth0";
import { type LocalStorageReadingLocation } from "@/components/Epub/StatefulReader";

import ReaderClientPage from "./ReaderClientPage";

export const runtime = "nodejs";

type Params = { identifier: string };

type Props = {
  params: Promise<Params>;
};

type ReadingLocationResponse = {
  publication_id: LocalStorageReadingLocation["publicationId"];
  locator: LocalStorageReadingLocation["locator"];
  recorded_at?: LocalStorageReadingLocation["recordedAt"];
};

async function fetchLatestReadingLocation(
  publicationId: string,
): Promise<LocalStorageReadingLocation | null> {
  if (!publicationId) return null;

  try {
    const { token } = await auth0.getAccessToken();
    if (!token) {
      return null;
    }

    const response = await fetch(
      `${
        process.env.READER_API_ORIGIN
      }/api/reading-locations/latest?publication_id=${encodeURIComponent(
        publicationId,
      )}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      console.error(
        "Failed to fetch latest reading location",
        response.status,
        await response.text(),
      );
      return null;
    }

    const data = (await response.json()) as ReadingLocationResponse;
    return {
      publicationId: data.publication_id || publicationId,
      locator: data.locator,
      recordedAt: data.recorded_at,
    } satisfies LocalStorageReadingLocation;
  } catch (error) {
    if (error instanceof AccessTokenError) {
      console.warn("Auth token unavailable when fetching reading location");
      return null;
    }
    console.error("Unexpected error fetching reading location", error);
    return null;
  }
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
