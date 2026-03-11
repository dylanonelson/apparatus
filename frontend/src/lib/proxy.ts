import { NextResponse } from "next/server";
import { AccessTokenError } from "@auth0/nextjs-auth0/errors";

import { auth0 } from "@/lib/auth0";

/**
 * Headers forwarded from the upstream reader_api response to the browser.
 * Hop-by-hop headers (e.g. transfer-encoding) are intentionally excluded.
 */
const FORWARDED_HEADERS = new Set([
  "content-type",
  "cache-control",
  "etag",
  "last-modified",
  "accept-ranges",
  "content-range",
]);

function getReaderApiOrigin(): string | null {
  return process.env.READER_API_ORIGIN ?? null;
}

async function getAccessToken(): Promise<string | null> {
  const { token } = await auth0.getAccessToken();
  return token ?? null;
}

async function parseResponseBody(response: Response) {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

type ProxyJsonOptions = {
  /** Path relative to READER_API_ORIGIN (e.g. "/api/reading-state") */
  upstreamPath: string;
  method: "GET" | "POST";
  /** JSON-serializable body for POST requests */
  body?: unknown;
  /** Fallback error message when upstream returns a non-OK status */
  errorMessage?: string;
};

/**
 * Proxy a JSON request to reader_api with Auth0 Bearer auth.
 *
 * Handles token extraction, upstream fetch, response parsing, and
 * error handling in a single place. Used by all BFF API routes
 * except the streaming publication proxy.
 */
export async function proxyJson({
  upstreamPath,
  method,
  body,
  errorMessage = "Upstream request failed",
}: ProxyJsonOptions): Promise<NextResponse> {
  const origin = getReaderApiOrigin();
  if (!origin) {
    return NextResponse.json(
      { error: "Reader API origin is not configured" },
      { status: 500 },
    );
  }

  try {
    const token = await getAccessToken();
    if (!token) {
      return NextResponse.json(
        { error: "Unable to obtain access token" },
        { status: 401 },
      );
    }

    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
    };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const upstreamResponse = await fetch(`${origin}${upstreamPath}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const parsed = await parseResponseBody(upstreamResponse);

    if (!upstreamResponse.ok) {
      return NextResponse.json(
        { error: parsed ?? errorMessage },
        { status: upstreamResponse.status },
      );
    }

    return NextResponse.json(parsed ?? {}, {
      status: upstreamResponse.status,
    });
  } catch (error) {
    if (error instanceof AccessTokenError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }
    return NextResponse.json({ error: "Unknown error" }, { status: 500 });
  }
}

type ProxyStreamOptions = {
  /** Path relative to READER_API_ORIGIN (e.g. "/read/some/resource") */
  upstreamPath: string;
};

/**
 * Proxy a request to reader_api and stream the response back.
 *
 * Used for publication resources (EPUB assets) where buffering the
 * entire response would be wasteful. Forwards a curated set of
 * response headers.
 */
export async function proxyStream({
  upstreamPath,
}: ProxyStreamOptions): Promise<NextResponse> {
  const origin = getReaderApiOrigin();
  if (!origin) {
    return NextResponse.json(
      { error: "Reader API origin is not configured" },
      { status: 500 },
    );
  }

  try {
    const token = await getAccessToken();
    if (!token) {
      return NextResponse.json(
        { error: "Unable to obtain access token" },
        { status: 401 },
      );
    }

    const upstreamResponse = await fetch(`${origin}${upstreamPath}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!upstreamResponse.ok) {
      const errorText = await upstreamResponse.text();
      return new NextResponse(errorText, {
        status: upstreamResponse.status,
        headers: { "content-type": "text/plain" },
      });
    }

    const responseHeaders = new Headers();
    for (const [key, value] of upstreamResponse.headers.entries()) {
      if (FORWARDED_HEADERS.has(key.toLowerCase())) {
        responseHeaders.set(key, value);
      }
    }

    return new NextResponse(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    });
  } catch (error) {
    if (error instanceof AccessTokenError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }
    console.error("Publication proxy error:", error);
    return NextResponse.json(
      { error: "Failed to fetch publication resource" },
      { status: 500 },
    );
  }
}

type ServerFetchOptions = {
  /** Path relative to READER_API_ORIGIN (e.g. "/api/reading-locations/latest") */
  upstreamPath: string;
  /** Query parameters to append */
  params?: Record<string, string>;
};

/**
 * Fetch JSON from reader_api in a server component (not a route handler).
 *
 * Returns the parsed JSON on success, or null on any error (auth failure,
 * upstream error, network issue). Designed for server-component data
 * loading where we want to degrade gracefully.
 */
export async function serverFetchJson<T>(
  options: ServerFetchOptions,
): Promise<T | null> {
  const origin = getReaderApiOrigin();
  if (!origin) return null;

  try {
    const token = await getAccessToken();
    if (!token) return null;

    const url = new URL(`${origin}${options.upstreamPath}`);
    if (options.params) {
      for (const [key, value] of Object.entries(options.params)) {
        url.searchParams.set(key, value);
      }
    }

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      if (response.status !== 404) {
        console.error(
          `Failed to fetch ${options.upstreamPath}`,
          response.status,
          await response.text(),
        );
      }
      return null;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof AccessTokenError) {
      console.warn(
        `Auth token unavailable when fetching ${options.upstreamPath}`,
      );
      return null;
    }
    console.error(
      `Unexpected error fetching ${options.upstreamPath}`,
      error,
    );
    return null;
  }
}
