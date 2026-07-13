import { NextRequest, NextResponse } from "next/server";
import { demoMutationResponse } from "@/lib/demo-route";
import { fiscalEngineCredentials } from "@/lib/fiscal-runtime";

export async function PUT(request: NextRequest) {
  const engine = fiscalEngineCredentials();
  if (!engine) return demoMutationResponse(request, "inventory_minimum");
  const response = await fetch(new URL("/v1/inventory/minimums", engine.baseUrl), { method: "PUT", headers: { Authorization: `Bearer ${engine.token}`, "Content-Type": "application/json" }, body: await request.text(), cache: "no-store" });
  return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
}
