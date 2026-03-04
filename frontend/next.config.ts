import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import type { NextConfig } from "next";
import type { PublicationManifestMap } from "./src/types/publications";

const DEFAULT_MANIFEST_BASE_URL = "http://localhost:15080";
const PUBLICATIONS_ROOT = __dirname;
const CATALOG_PATH = path.join(PUBLICATIONS_ROOT, "publications.yaml");

const manifestBaseUrl = normalizeBaseUrl(
  process.env.NEXT_PUBLIC_MANIFEST_BASE_URL ?? DEFAULT_MANIFEST_BASE_URL,
);
const publicationManifestMap = loadPublicationManifestMap(manifestBaseUrl);

const nextConfig: NextConfig = {
  // Disable React running twice as it messes up with iframes
  reactStrictMode: false,
  typedRoutes: true,
  experimental: {
    webpackBuildWorker: true,
  },
  // Configure asset prefix for CDN or subdirectory support
  assetPrefix: process.env.ASSET_PREFIX || undefined,
  env: {
    NEXT_PUBLIC_MANIFEST_BASE_URL: manifestBaseUrl,
    NEXT_PUBLIC_PUBLICATION_MANIFESTS: JSON.stringify(publicationManifestMap),
  },
  webpack(config) {
    const fileLoaderRule = config.module.rules.find((rule: { test?: RegExp }) =>
      rule?.test?.test?.(".svg"),
    ) as any;

    if (!fileLoaderRule) {
      return config;
    }

    config.module.rules.push(
      // Reapply the existing rule, but only for svg imports ending in ?url
      {
        ...fileLoaderRule,
        test: /\.svg$/i,
        resourceQuery: /url/, // *.svg?url
      },
      // Convert all other *.svg imports to React components
      {
        test: /\.svg$/i,
        issuer: fileLoaderRule.issuer,
        resourceQuery: { not: [...fileLoaderRule.resourceQuery.not, /url/] }, // exclude if *.svg?url
        use: ["@svgr/webpack"],
      },
    );

    // Modify the file loader rule to ignore *.svg, since we have it handled now.
    fileLoaderRule.exclude = /\.svg$/i;

    return config;
  },
  async redirects() {
    const isProduction = process.env.NODE_ENV === "production";
    const isManifestEnabled =
      !isProduction || process.env.MANIFEST_ROUTE_FORCE_ENABLE === "true";

    if (isProduction && !isManifestEnabled) {
      return [
        {
          source: "/read/manifest/:path*",
          destination: "/",
          permanent: false,
        },
      ];
    }
    return [];
  },
};

export default nextConfig;

function normalizeBaseUrl(value?: string) {
  const trimmed = (value ?? "").trim();
  if (!trimmed) {
    return DEFAULT_MANIFEST_BASE_URL;
  }
  const withoutTrailingSlash = trimmed.replace(/\/+$/, "");
  return withoutTrailingSlash || DEFAULT_MANIFEST_BASE_URL;
}

function loadPublicationManifestMap(baseUrl: string): PublicationManifestMap {
  try {
    if (!fs.existsSync(CATALOG_PATH)) {
      console.warn(`Publications catalog not found at ${CATALOG_PATH}`);
      return {};
    }
    const rawCatalog = fs.readFileSync(CATALOG_PATH, "utf8");
    const parsed = yaml.load(rawCatalog);
    if (!Array.isArray(parsed)) {
      console.warn("Publications catalog must be a YAML list of entries");
      return {};
    }

    return parsed.reduce<PublicationManifestMap>((acc, entry) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
        return acc;
      }
      const {
        id: rawId,
        title: rawTitle,
        author: rawAuthor,
        filename: rawFilename,
        urlSlug: rawUrlSlug,
      } = entry as Record<string, unknown>;
      const id = typeof rawId === "string" ? rawId.trim() : "";
      const title = typeof rawTitle === "string" ? rawTitle.trim() : "";
      const author = typeof rawAuthor === "string" ? rawAuthor.trim() : "";
      const filename =
        typeof rawFilename === "string" ? rawFilename.trim() : "";
      const urlSlug = typeof rawUrlSlug === "string" ? rawUrlSlug.trim() : "";
      if (!id || !filename || !urlSlug) {
        return acc;
      }
      const manifestUrl = `${baseUrl}/webpub/${encodeFilename(filename)}/manifest.json`;
      const value = {
        id,
        title,
        author,
        filename,
        manifestUrl,
        urlSlug,
      };
      acc[id] = value;
      acc[urlSlug] = value;
      return acc;
    }, {});
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`Unable to load publications catalog: ${message}`);
    return {};
  }
}

function encodeFilename(filename: string) {
  return Buffer.from(filename, "utf8")
    .toString("base64")
    .replace(/=+$/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}
