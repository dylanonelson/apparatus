import { NextResponse } from "next/server";

import { proxyJson } from "@/lib/proxy";

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload" },
      { status: 400 },
    );
  }

  return proxyJson({
    upstreamPath: "/api/ask-automatic",
    method: "POST",
    body: payload,
    errorMessage: "Failed to get automatic answer",
  });
}
