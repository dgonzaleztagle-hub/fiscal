import { NextRequest, NextResponse } from "next/server";
import { DEMO_COOKIE, currentDemoSessionId, loadDemoState, newDemoSessionId, recordDemoActivity, saveDemoState } from "./demo-store";

export async function demoMutationResponse(request: NextRequest, area: string, extra: Record<string, unknown> = {}) {
  try {
    const payload = { ...await request.json() as Record<string, unknown>, ...extra };
    if (JSON.stringify(payload).length > 1_500_000) throw new Error("El archivo de demostración supera el límite de 1 MB");
    const sessionId = await currentDemoSessionId() ?? newDemoSessionId();
    const result = recordDemoActivity(await loadDemoState(sessionId), area, payload);
    await saveDemoState(sessionId, result.state);
    const response = NextResponse.json(result.record, { status: 201 });
    response.cookies.set(DEMO_COOKIE, sessionId, { httpOnly: true, secure: request.nextUrl.protocol === "https:", sameSite: "lax", path: "/", maxAge: 14 * 86400 });
    return response;
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "No fue posible guardar en sandbox" }, { status: 422 });
  }
}
