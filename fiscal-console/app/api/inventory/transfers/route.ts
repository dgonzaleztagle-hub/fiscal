import { NextRequest, NextResponse } from "next/server";
import { demoMutationResponse } from "@/lib/demo-route";
import { fiscalEngineCredentials } from "@/lib/fiscal-runtime";

export async function POST(request: NextRequest) {
  const engine = fiscalEngineCredentials();
  if (!engine) return demoMutationResponse(request, "inventory_transfer");
  const response = await fetch(new URL("/v1/inventory/transfers", engine.baseUrl), { method: "POST", headers: { Authorization: `Bearer ${engine.token}`, "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() }, body: await request.text(), cache: "no-store" });
  return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
}
