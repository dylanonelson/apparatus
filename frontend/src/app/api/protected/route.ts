import { NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { AccessTokenError } from "@auth0/nextjs-auth0/errors";

export async function GET() {
  try {
    const { token } = await auth0.getAccessToken();
    console.log("token", token);
    if (!token) {
      return NextResponse.json(
        { error: "Unable to obtain access token" },
        { status: 401 },
      );
    }
    const resp = await fetch(`${process.env.READER_API_ORIGIN}/api/users/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!resp.ok) {
      return NextResponse.json(
        { error: await resp.text() },
        { status: resp.status },
      );
    }
    return NextResponse.json(await resp.json());
  } catch (err) {
    // err will be an instance of AccessTokenError if an access token could not be obtained
    if (err instanceof AccessTokenError) {
      return NextResponse.json({ error: err.message }, { status: 401 });
    }
    return NextResponse.json({ error: "Unknown error" }, { status: 500 });
  }
}
