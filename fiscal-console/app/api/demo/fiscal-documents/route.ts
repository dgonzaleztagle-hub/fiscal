import { NextRequest, NextResponse } from "next/server";
import { DEMO_COOKIE, currentDemoSessionId, issueSyntheticDocument, loadDemoState, newDemoSessionId, saveDemoState } from "@/lib/demo-store";

export async function POST(request: NextRequest) {
  try {
    const input = await request.json() as { documentType: number; receiver: string; itemName: string; quantity: number; unitPrice: number };
    const sessionId = await currentDemoSessionId() ?? newDemoSessionId();
    const result = issueSyntheticDocument(await loadDemoState(sessionId), input);
    await saveDemoState(sessionId, result.state);
    const response = NextResponse.json(result.record, { status: 201 });
    response.cookies.set(DEMO_COOKIE, sessionId, { httpOnly: true, secure: request.nextUrl.protocol === "https:", sameSite: "lax", path: "/", maxAge: 14 * 86400 });
    return response;
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "No fue posible emitir en sandbox" }, { status: 422 });
  }
}
