import { NextRequest } from "next/server";
import { demoMutationResponse } from "@/lib/demo-route";
import { loadDemoState } from "@/lib/demo-store";

export async function GET(request: NextRequest) {
  const area = request.nextUrl.searchParams.get("area")?.replace(/[^a-z0-9_-]/gi, "").slice(0, 40);
  const document = request.nextUrl.searchParams.get("document");
  const rows = (await loadDemoState()).activities.filter(item => (!area || item.area === area) && (!document || item.payload.document === document));
  return Response.json(rows.slice(0, 50));
}

export async function POST(request: NextRequest) {
  const area = request.nextUrl.searchParams.get("area")?.replace(/[^a-z0-9_-]/gi, "").slice(0, 40) || "general";
  return demoMutationResponse(request, area);
}
