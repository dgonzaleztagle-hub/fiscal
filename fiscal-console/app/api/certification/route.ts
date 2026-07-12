import { NextRequest, NextResponse } from "next/server";

export async function GET() {
  return forward("/v1/certification/readiness", "GET", undefined, readinessFallback());
}

export async function POST(request: NextRequest) {
  const body = await request.json() as { scenario: string };
  return forward("/v1/certification/dry-runs", "POST", body, {
    synthetic: true, document_count: 5, scenario: body.scenario,
    final_state: body.scenario === "accepted" ? "accepted" : body.scenario === "timeout_after_upload" ? "unknown" : "rejected",
    evidence_sha256: "demo-local-sin-motor-conectado", source: "demo",
    timeline: ["generate_five_documents", "build_envelope", "build_rcof", body.scenario].map((step) => ({ step, state: "simulated" })),
  });
}

async function forward(path: string, method: "GET" | "POST", body: unknown, fallback: object) {
  const base = process.env.FISCAL_API_URL;
  const token = process.env.FISCAL_API_TOKEN;
  if (!base || !token) return NextResponse.json(fallback);
  try {
    const response = await fetch(new URL(path, base), { method, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined, cache: "no-store", signal: AbortSignal.timeout(15_000) });
    if (!response.ok) throw new Error(String(response.status));
    return NextResponse.json({ ...(await response.json()), source: "engine" });
  } catch { return NextResponse.json(fallback); }
}

function readinessFallback() {
  return { ready_to_download_caf: false, completed: 2, total: 5, source: "demo", gates: [
    ["offline_engine", "Motor y regresión documental", true, "DTE y firmas locales cubiertos"],
    ["dry_run", "Ensayo de cinco folios", true, "Sobre, RCOF, fallas y evidencia sintética"],
    ["public_https", "Consulta pública HTTPS", false, "Requiere despliegue accesible"],
    ["real_certificate", "Certificado digital real", false, "Pendiente de compra y vault"],
    ["real_caf", "CAF real de cinco folios", false, "Bloqueado para no iniciar las 24 horas"],
  ].map(([code, title, completed, detail]) => ({ code, title, completed, detail })) };
}
