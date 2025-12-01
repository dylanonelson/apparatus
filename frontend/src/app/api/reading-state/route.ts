import { NextResponse } from "next/server";
import { AccessTokenError } from "@auth0/nextjs-auth0/errors";

import { auth0 } from "@/lib/auth0";

const parseResponseBody = async (response: Response) => {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch (_error) {
    return { message: text };
  }
};

export async function POST(request: Request) {
  if (!process.env.READER_API_ORIGIN) {
    return NextResponse.json(
      { error: "Reader API origin is not configured" },
      { status: 500 },
    );
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch (error) {
    return NextResponse.json(
      { error: "Invalid JSON payload" },
      { status: 400 },
    );
  }

  try {
    const { token } = await auth0.getAccessToken();
    if (!token) {
      return NextResponse.json(
        { error: "Unable to obtain access token" },
        { status: 401 },
      );
    }

    const upstreamResponse = await fetch(
      `${process.env.READER_API_ORIGIN}/api/reading-state`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      },
    );

    const body = await parseResponseBody(upstreamResponse);

    if (!upstreamResponse.ok) {
      return NextResponse.json(
        { error: body ?? "Failed to store reading state" },
        { status: upstreamResponse.status },
      );
    }

    return NextResponse.json(body ?? {});
  } catch (error) {
    if (error instanceof AccessTokenError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    return NextResponse.json({ error: "Unknown error" }, { status: 500 });
  }
}
