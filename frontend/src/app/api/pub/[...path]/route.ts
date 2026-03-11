import { NextRequest } from "next/server";

import { proxyStream } from "@/lib/proxy";

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
  const { path: segments } = await params;
  const upstreamPath = `/read/${segments.join("/")}`;

  return proxyStream({ upstreamPath });
}
