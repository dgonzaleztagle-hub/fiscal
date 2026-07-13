import { NextRequest, NextResponse } from "next/server";
import { DEMO_COOKIE, currentDemoSessionId, issueSyntheticDocument, loadDemoState, newDemoSessionId, saveDemoState, type DemoIssueInput } from "@/lib/demo-store";

export async function GET() {
  const state = await loadDemoState();
  return NextResponse.json(state.documents.map(({ id, kind, label, folio, receiver, amount }) => ({ id, kind, label, folio, receiver, amount })));
}

export async function POST(request: NextRequest) {
  try {
    const input = await request.json() as DemoIssueInput;
    const sessionId = await currentDemoSessionId() ?? newDemoSessionId();
    const state = await loadDemoState(sessionId);
    const idempotencyKey = request.headers.get("Idempotency-Key")?.slice(0, 120);
    const previousId = idempotencyKey ? state.idempotency[idempotencyKey] : null;
    const previous = previousId ? state.documents.find(document => document.id === previousId) : null;
    if (previous) return NextResponse.json(previous, { status: 200 });
    const result = issueSyntheticDocument(state, input);
    if (idempotencyKey) result.state.idempotency[idempotencyKey] = result.record.id;
    await saveDemoState(sessionId, result.state);
    const response = NextResponse.json(result.record, { status: 201 });
    response.cookies.set(DEMO_COOKIE, sessionId, { httpOnly: true, secure: request.nextUrl.protocol === "https:", sameSite: "lax", path: "/", maxAge: 14 * 86400 });
    return response;
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "No fue posible emitir en sandbox" }, { status: 422 });
  }
}
