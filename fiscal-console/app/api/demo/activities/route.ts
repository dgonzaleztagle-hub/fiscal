import { NextRequest } from "next/server";
import { demoMutationResponse } from "@/lib/demo-route";

export async function POST(request: NextRequest) {
  const area = request.nextUrl.searchParams.get("area")?.replace(/[^a-z0-9_-]/gi, "").slice(0, 40) || "general";
  return demoMutationResponse(request, area);
}
