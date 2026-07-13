import "server-only";
import type { components } from "./api.generated";
import type { DemoDocument } from "./demo-data";
import { loadDemoState } from "./demo-store";

type DocumentResponse = components["schemas"]["DocumentResponse"];
type EventResponse = components["schemas"]["EventResponse"];

const labels: Record<number, string> = {
  33: "Factura electrónica", 34: "Factura exenta", 39: "Boleta electrónica",
  41: "Boleta exenta", 52: "Guía de despacho", 56: "Nota de débito", 61: "Nota de crédito",
};

export type FiscalDocumentsResult = {
  rows: DemoDocument[];
  source: "engine" | "sandbox" | "demo";
  warning?: string;
};

export type FiscalDocumentDetail = DemoDocument & {
  documentId: string;
  taxpayerRut: string;
  xmlSha256: string;
  publicUrl?: string;
  events: EventResponse[];
  source: "engine" | "sandbox" | "demo";
  warning?: string;
};

export type EngineSectionResult<T> = { data: T | null; source: "engine" | "sandbox" | "demo"; warning?: string };

export async function fiscalSection<T>(path: string): Promise<EngineSectionResult<T>> {
  const baseUrl = process.env.FISCAL_API_URL;
  const token = process.env.FISCAL_API_TOKEN;
  if (!baseUrl || !token) return { data: await sandboxSection<T>(path), source: "sandbox" };
  try {
    const response = await engineFetch(path, baseUrl, token);
    if (response.status === 404) return { data: null, source: "engine" };
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return { data: await response.json() as T, source: "engine" };
  } catch (error) {
    return { data: await sandboxSection<T>(path), source: "demo", warning: error instanceof Error ? error.message : "Motor no disponible" };
  }
}

export async function fiscalDocuments(limit?: number): Promise<FiscalDocumentsResult> {
  const baseUrl = process.env.FISCAL_API_URL;
  const token = process.env.FISCAL_API_TOKEN;
  if (!baseUrl || !token) {
    const state = await loadDemoState();
    return { rows: slice(state.documents, limit), source: "sandbox" };
  }
  try {
    const url = new URL("/v1/fiscal-documents", baseUrl);
    url.searchParams.set("limit", String(limit ?? 50));
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json() as DocumentResponse[];
    return {
      source: "engine",
      rows: payload.map(mapDocument),
    };
  } catch (error) {
    const state = await loadDemoState();
    return {
      rows: slice(state.documents, limit),
      source: "sandbox",
      warning: error instanceof Error ? error.message : "Motor no disponible",
    };
  }
}

export async function fiscalDocument(id: string): Promise<FiscalDocumentDetail | null> {
  const baseUrl = process.env.FISCAL_API_URL;
  const token = process.env.FISCAL_API_TOKEN;
  if (!baseUrl || !token) return demoDetail(id);
  try {
    const [recordResponse, eventsResponse] = await Promise.all([
      engineFetch(`/v1/fiscal-documents/${encodeURIComponent(id)}`, baseUrl, token),
      engineFetch(`/v1/fiscal-documents/${encodeURIComponent(id)}/events`, baseUrl, token),
    ]);
    if (recordResponse.status === 404) return null;
    if (!recordResponse.ok) throw new Error(`HTTP ${recordResponse.status}`);
    if (!eventsResponse.ok) throw new Error(`Eventos HTTP ${eventsResponse.status}`);
    const record = await recordResponse.json() as DocumentResponse;
    return {
      ...mapDocument(record),
      documentId: record.document_id,
      taxpayerRut: record.taxpayer_rut,
      xmlSha256: record.xml_sha256,
      publicUrl: record.public_url,
      events: await eventsResponse.json() as EventResponse[],
      source: "engine",
    };
  } catch (error) {
    const fallback = await demoDetail(id);
    return fallback ? { ...fallback, warning: error instanceof Error ? error.message : "Motor no disponible" } : null;
  }
}

export function fiscalArtifactUrl(id: string, artifact: "xml" | "pdf") {
  return `/api/fiscal-documents/${encodeURIComponent(id)}/${artifact}`;
}

function mapDocument(record: DocumentResponse): DemoDocument {
  return {
    id: record.id,
    kind: String(record.document_type),
    label: labels[record.document_type] ?? `DTE ${record.document_type}`,
    folio: new Intl.NumberFormat("es-CL").format(record.folio),
    receiver: record.counterparty_name,
    amount: record.total,
    status: "submitted",
    statusLabel: record.status === "signed" ? "Firmado local" : record.status,
    issuedAt: new Intl.DateTimeFormat("es-CL", { dateStyle: "medium" }).format(new Date(`${record.issued_on}T12:00:00`)),
  };
}

async function demoDetail(id: string): Promise<FiscalDocumentDetail | null> {
  const document = (await loadDemoState()).documents.find((item) => item.id === id);
  if (!document) return null;
  return {
    ...document,
    source: "sandbox",
  };
}

function engineFetch(path: string, baseUrl: string, token: string) {
  return fetch(new URL(path, baseUrl), {
    headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(4000),
  });
}

function slice(rows: DemoDocument[], limit?: number) {
  return limit ? rows.slice(0, limit) : rows;
}

async function sandboxSection<T>(path: string): Promise<T | null> {
  const state = await loadDemoState();
  if (path.startsWith("/v1/commercial-documents")) {
    const kind = new URL(path, "http://sandbox.local").searchParams.get("kind");
    return state.commercialDocuments.filter(row => !kind || row.kind === kind) as T;
  }
  if (path === "/v1/inventory/products") return state.inventoryProducts as T;
  if (path.startsWith("/v1/obligations")) return state.obligations as T;
  if (path.startsWith("/v1/recurring-agreements")) return state.activities.filter(item => item.area === "recurring").map(item => ({ id: item.id, counterparty_name: String(item.payload.counterparty_name || "Cliente demo"), description: String(item.payload.description || "Servicio recurrente"), amount: Number(item.payload.amount || 0), day_of_month: Number(item.payload.day_of_month || 15), next_run_on: String(item.payload.next_run_on || "2026-08-15"), active: 1 })) as T;
  if (path.startsWith("/v1/approvals")) return [] as T;
  if (path.startsWith("/v1/cash-flow/projection")) {
    if (!state.obligations.length) return null;
    const incoming = state.obligations.filter(row => row.direction === "receivable").reduce((sum, row) => sum + row.amount - row.paid, 0);
    const outgoing = state.obligations.filter(row => row.direction === "payable").reduce((sum, row) => sum + row.amount - row.paid, 0);
    return { incoming, outgoing, net: incoming - outgoing, from_on: "2026-07-13", to_on: "2026-08-09" } as T;
  }
  if (!path.includes("/close/snapshots")) return null;
  const documents = state.documents;
  const sign = (kind: string) => kind === "61" ? -1 : 1;
  const salesDocuments = documents.filter(row => ["33", "34", "39", "41", "61"].includes(row.kind));
  const salesTotal = salesDocuments.reduce((sum, row) => sum + sign(row.kind) * row.amount, 0);
  const salesVat = salesDocuments.reduce((sum, row) => sum + sign(row.kind) * row.vat, 0);
  const purchaseTotal = 632_400, purchaseVat = 68_400, withholding = 6_863, ppm = 24_400;
  const totalPayable = Math.max(0, salesVat - purchaseVat + withholding + ppm);
  const lines = [
    { code: "sales_vat", label: "Débito fiscal por ventas", amount: salesVat, sii_amount: salesVat, state: "matched" },
    { code: "purchase_vat", label: "Crédito fiscal por compras", amount: purchaseVat, sii_amount: purchaseVat, state: "matched" },
    { code: "second_category_withholding", label: "Retención honorarios", amount: withholding, sii_amount: withholding, state: "matched" },
    { code: "ppm", label: "PPM neto determinado", amount: ppm, sii_amount: ppm, state: "matched" },
  ];
  return [{ version: Math.max(1, documents.length - 4), payload: { sales: { total: salesTotal, vat: salesVat }, purchases: { total: purchaseTotal, vat: purchaseVat }, total_payable: totalPayable, ppm, lines } }] as T;
}
