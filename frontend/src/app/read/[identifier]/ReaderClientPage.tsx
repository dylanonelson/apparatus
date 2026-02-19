"use client";

import { useEffect, useMemo, useState } from "react";

import {
  createAnswersPlugin,
  createDefaultPlugin,
  StatefulReader,
  type LocalStorageReadingLocation,
} from "@/components/Epub";
import { StatefulLoader } from "@/components/StatefulLoader";
import { usePublication } from "@/hooks/usePublication";
import { useAppSelector } from "@/lib/hooks";
import { verifyManifestUrl } from "@/app/api/verify-manifest/verifyDomain";
import type { PublicationConfig } from "@/types/publications";

import "@/app/app.css";

type Props = {
  publicationConfig: PublicationConfig;
  serverInitialReadingLocation: LocalStorageReadingLocation | null;
};

export default function ReaderClientPage({
  publicationConfig,
  serverInitialReadingLocation,
}: Props) {
  const [domainError, setDomainError] = useState<string | null>(null);
  const isLoading = useAppSelector((state) => state.reader.isLoading);
  const manifestUrl = publicationConfig?.manifestUrl ?? "";

  useEffect(() => {
    if (manifestUrl) {
      verifyManifestUrl(manifestUrl).then((allowed) => {
        if (!allowed) {
          setDomainError(
            `Domain not allowed: ${new URL(manifestUrl).hostname}`,
          );
        }
      });
    }
  }, [manifestUrl]);

  const { error, manifest, selfLink } = usePublication({
    url: manifestUrl,
    onError: (err) => {
      console.error("Publication loading error:", err);
    },
  });

  const plugins = useMemo(() => {
    return [createDefaultPlugin(), createAnswersPlugin()];
  }, []);

  if (domainError) {
    return (
      <div className="container">
        <h1>Access Denied</h1>
        <p>{domainError}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <h1>Error</h1>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <StatefulLoader isLoading={isLoading}>
      {manifest && selfLink && (
        <StatefulReader
          rawManifest={manifest}
          selfHref={selfLink}
          publicationId={publicationConfig.id}
          plugins={plugins}
          serverInitialReadingLocation={
            serverInitialReadingLocation ?? undefined
          }
        />
      )}
    </StatefulLoader>
  );
}
