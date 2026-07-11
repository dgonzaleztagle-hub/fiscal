import { NextResponse, type NextRequest } from "next/server";

const allowed = new Set(["xml", "pdf"]);

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string; artifact: string }> }) {
  const { id, artifact } = await params;
  const baseUrl = process.env.FISCAL_API_URL;
  const token = process.env.FISCAL_API_TOKEN;
  if (!baseUrl || !token || !allowed.has(artifact)) return NextResponse.json({ error: "Representación no disponible" }, { status: 404 });
  const upstream = await fetch(new URL(`/v1/fiscal-documents/${encodeURIComponent(id)}/${artifact}`, baseUrl), {
    headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(8000),
  });
  if (!upstream.ok) return NextResponse.json({ error: "El motor no pudo generar la representación" }, { status: upstream.status });
  const sha256 = upstream.headers.get("x-content-sha256");
  return new NextResponse(await upstream.arrayBuffer(), { status: 200, headers: {
    "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
    "Content-Disposition": upstream.headers.get("content-disposition") ?? `inline; filename="documento.${artifact}"`,
    "Cache-Control": "private, no-store",
    ...(sha256 ? { "X-Content-SHA256": sha256 } : {}),
  }});
}
