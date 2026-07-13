import { NextResponse, type NextRequest } from "next/server";
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import { demoDocumentById } from "@/lib/demo-store";
import { fiscalEngineCredentials } from "@/lib/fiscal-runtime";

const allowed = new Set(["xml", "pdf"]);

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string; artifact: string }> }) {
  const { id, artifact } = await params;
  if (!allowed.has(artifact)) return NextResponse.json({ error: "Representación no disponible" }, { status: 404 });
  const engine = fiscalEngineCredentials();
  if (!engine) return sandboxArtifact(id, artifact);
  const { baseUrl, token } = engine;
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

async function sandboxArtifact(id: string, artifact: string) {
  const document = await demoDocumentById(id);
  if (!document) return NextResponse.json({ error: "Documento sandbox no encontrado" }, { status: 404 });
  if (artifact === "xml") {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<CompletoFiscalSandbox version="1.0" NO_VALIDO_COMO_DTE="true">\n  <Aviso>DOCUMENTO SINTETICO - NO ENVIADO AL SII</Aviso>\n  <Documento tipo="${document.kind}" folio="${escapeXml(document.folio)}">\n    <Emisor rut="${escapeXml(document.taxpayerRut)}" />\n    <Receptor>${escapeXml(document.receiver)}</Receptor>\n    <Detalle>${escapeXml(document.itemName)}</Detalle>\n    <Neto>${document.net}</Neto><IVA>${document.vat}</IVA><Total>${document.amount}</Total>\n    ${document.referenceId ? `<Referencia>${escapeXml(document.referenceId)}</Referencia>` : ""}\n    <SHA256>${document.xmlSha256}</SHA256>\n    <Estado>ACEPTADO_POR_SIMULADOR</Estado>\n  </Documento>\n</CompletoFiscalSandbox>`;
    return new NextResponse(xml, { headers: { "Content-Type": "application/xml; charset=utf-8", "Content-Disposition": `attachment; filename="sandbox-${document.kind}-${document.folio}.xml"`, "Cache-Control": "private, no-store" } });
  }
  const pdf = await PDFDocument.create();
  const page = pdf.addPage([595, 842]);
  const font = await pdf.embedFont(StandardFonts.Helvetica);
  const bold = await pdf.embedFont(StandardFonts.HelveticaBold);
  page.drawRectangle({ x: 34, y: 34, width: 527, height: 774, borderColor: rgb(0.08, 0.16, 0.31), borderWidth: 1 });
  page.drawText("COMPLETO FISCAL · SANDBOX", { x: 55, y: 775, size: 18, font: bold, color: rgb(0.08, 0.16, 0.31) });
  page.drawText("DOCUMENTO SINTETICO · NO VALIDO COMO DTE", { x: 55, y: 748, size: 11, font: bold, color: rgb(0.75, 0.2, 0.12) });
  const lines = [
    [`${document.label}`, `Tipo ${document.kind} · Folio ${document.folio}`],
    ["Emisor", document.taxpayerRut], ["Receptor", document.receiver], ["Detalle", document.itemName],
    ["Neto", clp(document.net)], ["IVA", clp(document.vat)], ["TOTAL", clp(document.amount)],
    ...(document.referenceId ? [["Referencia", document.referenceId]] : []),
    ["Estado", "Aceptado por simulador (sin conexion al SII)"], ["Huella SHA-256", document.xmlSha256],
  ];
  let y = 700;
  for (const [label, value] of lines) {
    page.drawText(safePdf(label), { x: 55, y, size: 10, font: bold });
    page.drawText(safePdf(value).slice(0, 74), { x: 175, y, size: 10, font });
    y -= 32;
  }
  page.drawText("Generado exclusivamente para demostracion y pruebas visuales.", { x: 55, y: 70, size: 9, font, color: rgb(0.35, 0.4, 0.48) });
  const bytes = await pdf.save();
  return new NextResponse(Buffer.from(bytes), { headers: { "Content-Type": "application/pdf", "Content-Disposition": `inline; filename="sandbox-${document.kind}-${document.folio}.pdf"`, "Cache-Control": "private, no-store" } });
}

function escapeXml(value: string) { return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&apos;"); }
function clp(value: number) { return `$${new Intl.NumberFormat("es-CL").format(value)}`; }
function safePdf(value: string) { return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^ -ÿ]/g, "-"); }
