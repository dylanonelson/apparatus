import { NextRequest, NextResponse } from "next/server";
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

/**
 * Catch-all GET proxy for publication resources.
 *
 * Requests arrive from the Readium `HttpFetcher` in the browser with the
 * session cookie attached automatically (same-origin).  This route extracts
 * the Auth0 access token from the session and forwards the request to
 * `reader_api /read/{path}` with a Bearer token.  The response is streamed
 * back to the browser.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  if (!process.env.READER_API_ORIGIN) {
    return NextResponse.json(
      { error: "Reader API origin is not configured" },
      { status: 500 },
    );
  }

  const { path: segments } = await params;
  const upstreamPath = segments.join("/");

  try {
    const { token } = await auth0.getAccessToken();
    if (!token) {
      return NextResponse.json(
        { error: "Unable to obtain access token" },
        { status: 401 },
      );
    }

    const upstreamUrl = `${process.env.READER_API_ORIGIN}/read/${upstreamPath}`;
    console.log("upstreamUrl", upstreamUrl);

    const upstreamResponse = await fetch(upstreamUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!upstreamResponse.ok) {
      const errorText = await upstreamResponse.text();
      return new NextResponse(errorText, {
        status: upstreamResponse.status,
        headers: { "content-type": "text/plain" },
      });
    }

    // Forward the response body and selected headers to the browser.
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
