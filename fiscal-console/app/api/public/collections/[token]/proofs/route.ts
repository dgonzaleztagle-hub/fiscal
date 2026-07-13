import { NextRequest, NextResponse } from "next/server";
import { demoMutationResponse } from "@/lib/demo-route";
import { fiscalPublicEngineUrl } from "@/lib/fiscal-runtime";

export async function POST(request: NextRequest, { params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const base = fiscalPublicEngineUrl();
  if (!base) return demoMutationResponse(request, "public_payment_proof", { public_token: token });
  const response = await fetch(new URL(`/v1/public/collections/${encodeURIComponent(token)}/proofs`, base), { method: "POST", headers: { "Content-Type": "application/json" }, body: await request.text(), cache: "no-store" });
  return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
}
