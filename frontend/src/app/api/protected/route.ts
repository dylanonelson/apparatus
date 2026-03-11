import { proxyJson } from "@/lib/proxy";

export async function GET() {
  return proxyJson({
    upstreamPath: "/api/users/me",
    method: "GET",
  });
}
