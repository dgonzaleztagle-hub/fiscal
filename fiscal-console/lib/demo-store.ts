import "server-only";

import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { cookies } from "next/headers";
import { demoDocuments, type DemoDocument } from "./demo-data";

export const DEMO_COOKIE = "completo_fiscal_demo_session";

export type DemoEvent = {
  sequence: number;
  event_type: string;
  occurred_at: string;
  metadata: Record<string, string | number | boolean>;
};

export type StoredDemoDocument = DemoDocument & {
  documentId: string;
  taxpayerRut: string;
  xmlSha256: string;
  itemName: string;
  net: number;
  vat: number;
  referenceId?: string;
  reason?: string;
  events: DemoEvent[];
};

export type DemoState = {
  version: 1;
  documents: StoredDemoDocument[];
  commercialDocuments: DemoCommercialDocument[];
  inventoryProducts: DemoInventoryProduct[];
  obligations: DemoObligation[];
  activities: DemoActivity[];
  idempotency: Record<string, string>;
};

export type DemoCommercialDocument = { id: string; number: number; kind: string; counterparty_name: string; valid_until: string | null; total: number; status: string };
export type DemoInventoryProduct = { id: string; sku: string; name: string; unit: string; balance: number };
export type DemoObligation = { id: string; direction: string; counterparty_name: string; source_ref: string; amount: number; paid: number; due_on: string };
export type DemoActivity = { id: string; area: string; occurred_at: string; payload: Record<string, unknown> };

const labels: Record<number, string> = {
  33: "Factura electrónica", 34: "Factura exenta", 39: "Boleta electrónica", 41: "Boleta exenta",
  52: "Guía de despacho electrónica", 56: "Nota de débito electrónica", 61: "Nota de crédito electrónica",
};
const localStore = join(tmpdir(), "completo-fiscal-demo-sessions");

export function demoBackendConfigured() {
  return Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);
}

export async function currentDemoSessionId() {
  const value = (await cookies()).get(DEMO_COOKIE)?.value;
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value) ? value : null;
}

export function newDemoSessionId() {
  return randomUUID();
}

export async function loadDemoState(sessionId?: string | null): Promise<DemoState> {
  const id = sessionId === undefined ? await currentDemoSessionId() : sessionId;
  if (!id) return seedState();
  if (!demoBackendConfigured()) {
    try { return normalizeState(JSON.parse(await readFile(join(localStore, `${id}.json`), "utf8")) as Partial<DemoState>); }
    catch { return seedState(); }
  }
  const response = await supabaseFetch(`/rest/v1/fiscal_demo_sessions?session_id=eq.${encodeURIComponent(id)}&select=state&limit=1`);
  if (!response.ok) throw new Error(`Sandbox storage HTTP ${response.status}`);
  const rows = await response.json() as Array<{ state: DemoState }>;
  return rows[0]?.state ? normalizeState(rows[0].state) : seedState();
}

export async function saveDemoState(sessionId: string, state: DemoState) {
  if (!demoBackendConfigured()) {
    await mkdir(localStore, { recursive: true });
    await writeFile(join(localStore, `${sessionId}.json`), JSON.stringify(state), "utf8");
    return;
  }
  const response = await supabaseFetch("/rest/v1/fiscal_demo_sessions?on_conflict=session_id", {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ session_id: sessionId, state, updated_at: new Date().toISOString(), expires_at: new Date(Date.now() + 14 * 86400000).toISOString() }),
  });
  if (!response.ok) throw new Error(`Sandbox storage HTTP ${response.status}`);
}

export async function demoDocumentById(id: string) {
  return (await loadDemoState()).documents.find(document => document.id === id) ?? null;
}

export function recordDemoActivity(state: DemoState, area: string, payload: Record<string, unknown>) {
  const now = new Date().toISOString();
  const id = `sandbox-${area}-${randomUUID().slice(0, 10)}`;
  const safePayload = area === "public_payment_proof" && typeof payload.content_base64 === "string" ? { ...payload, content_base64: undefined, content_sha256: createHash("sha256").update(payload.content_base64).digest("hex"), content_bytes: Math.round(payload.content_base64.length * 0.75) } : payload;
  const activity: DemoActivity = { id, area, occurred_at: now, payload: safePayload };
  let next: DemoState = { ...state, activities: [activity, ...state.activities].slice(0, 200) };
  let record: Record<string, unknown> = { id, sandbox: true, status: "saved" };
  if (area === "commercial") {
    const lines = Array.isArray(payload.lines) ? payload.lines as Array<Record<string, unknown>> : [];
    const total = lines.reduce((sum, line) => sum + Number(line.quantity || 0) * Number(line.unit_price || 0), 0);
    const item: DemoCommercialDocument = { id, number: state.commercialDocuments.length + 19, kind: String(payload.kind || "quote"), counterparty_name: String(payload.counterparty_name || "Contraparte demo"), valid_until: payload.valid_until ? String(payload.valid_until) : null, total, status: "draft" };
    next = { ...next, commercialDocuments: [item, ...state.commercialDocuments] }; record = { ...item, sandbox: true };
  } else if (area === "inventory_movement") {
    const productId = String(payload.product_id || "producto-demo");
    const delta = Number(payload.quantity || 0) * (["sale", "adjustment_out"].includes(String(payload.movement_type)) ? -1 : 1);
    const current = state.inventoryProducts.find(item => item.id === productId);
    const balance = Math.max(0, (current?.balance ?? 0) + delta);
    const item: DemoInventoryProduct = { id: productId, sku: String(payload.branch_id || "main"), name: current?.name ?? productId, unit: `${new Intl.NumberFormat("es-CL", { maximumFractionDigits: 3 }).format(balance)} un.`, balance };
    next = { ...next, inventoryProducts: [item, ...state.inventoryProducts.filter(row => row.id !== productId)] }; record = { ...item, sandbox: true };
  } else if (area === "obligation") {
    const item: DemoObligation = { id, direction: String(payload.direction || "receivable"), counterparty_name: String(payload.counterparty_name || "Contraparte demo"), source_ref: String(payload.source_ref || "manual"), amount: Number(payload.amount || 0), paid: 0, due_on: String(payload.due_on || now.slice(0, 10)) };
    next = { ...next, obligations: [item, ...state.obligations] }; record = { ...item, sandbox: true };
  } else if (area === "payment") {
    const obligationId = String(payload.obligation_id || "");
    const amount = Number(payload.amount || 0);
    const existing = state.obligations.find(item => item.id === obligationId);
    if (!existing) throw new Error("No existe una cuenta sandbox con ese ID");
    if (amount <= 0 || existing.paid + amount > existing.amount) throw new Error("El pago supera el saldo pendiente");
    const updated = { ...existing, paid: existing.paid + amount };
    next = { ...next, obligations: state.obligations.map(item => item.id === obligationId ? updated : item) }; record = { ...updated, sandbox: true };
  } else if (area === "recurring") {
    record = { id, counterparty_name: String(payload.counterparty_name || "Cliente demo"), description: String(payload.description || "Servicio recurrente"), amount: Number(payload.amount || 0), day_of_month: Number(payload.day_of_month || 15), next_run_on: String(payload.next_run_on || now.slice(0, 10)), active: 1, sandbox: true };
  }
  return { state: next, record };
}

export type DemoIssueInput = {
  documentType: number;
  receiver: string;
  itemName: string;
  quantity: number;
  unitPrice: number;
  referenceId?: string;
  reason?: string;
  exempt?: boolean;
};

export function issueSyntheticDocument(state: DemoState, input: DemoIssueInput) {
  if (![33, 34, 39, 41, 52, 56, 61].includes(input.documentType)) throw new Error("Tipo documental no permitido en sandbox");
  if (!input.itemName.trim() || !input.receiver.trim() || !Number.isFinite(input.quantity) || !Number.isFinite(input.unitPrice) || input.quantity <= 0 || input.quantity > 10_000 || input.unitPrice < 0 || input.unitPrice > 1_000_000_000) throw new Error("Datos incompletos o fuera de rango");
  if ([56, 61].includes(input.documentType) && !input.referenceId?.trim()) throw new Error("La nota debe indicar el documento que corrige");
  if ([56, 61].includes(input.documentType)) {
    const original = state.documents.find(document => document.id === input.referenceId);
    if (!original) throw new Error("El documento de referencia no existe en este tenant sandbox");
    if (!["33", "34", "56"].includes(original.kind)) throw new Error("Ese tipo documental no admite esta corrección");
  }
  const exempt = input.exempt || input.documentType === 34 || input.documentType === 41;
  const invoice = [33, 34, 52, 56, 61].includes(input.documentType);
  const base = Math.round(input.quantity * input.unitPrice);
  const net = exempt ? base : invoice ? base : Math.round(base / 1.19);
  const vat = exempt ? 0 : invoice ? Math.round(base * 0.19) : base - net;
  const total = invoice ? net + vat : base;
  const currentMax = state.documents.filter(row => Number(row.kind) === input.documentType).reduce((max, row) => Math.max(max, Number(row.folio.replaceAll(".", "")) || 0), 0);
  const folio = currentMax + 1;
  const issuedAt = new Date().toISOString();
  const payload = { documentType: input.documentType, folio, receiver: input.receiver, itemName: input.itemName, net, vat, total, referenceId: input.referenceId, reason: input.reason };
  const id = `sandbox-${input.documentType}-${folio}-${randomUUID().slice(0, 8)}`;
  const record: StoredDemoDocument = {
    id,
    kind: String(input.documentType),
    label: labels[input.documentType],
    folio: new Intl.NumberFormat("es-CL").format(folio),
    receiver: input.receiver,
    amount: total,
    status: "accepted",
    statusLabel: "Aceptada por simulador",
    issuedAt: "Ahora",
    documentId: `SANDBOX-${input.documentType}-${folio}`,
    taxpayerRut: "76.192.083-9",
    xmlSha256: createHash("sha256").update(JSON.stringify(payload)).digest("hex"),
    itemName: input.itemName,
    net,
    vat,
    referenceId: input.referenceId?.trim(),
    reason: input.reason?.trim(),
    events: [
      { sequence: 1, event_type: "draft_validated", occurred_at: issuedAt, metadata: { synthetic: true } },
      { sequence: 2, event_type: "folio_reserved", occurred_at: issuedAt, metadata: { folio, synthetic: true } },
      { sequence: 3, event_type: "signed_with_synthetic_credential", occurred_at: issuedAt, metadata: { synthetic: true } },
      { sequence: 4, event_type: "accepted_by_sii_simulator", occurred_at: issuedAt, metadata: { track_id: `SIM-${Date.now()}`, synthetic: true, sii_network_called: false } },
    ],
  };
  return { state: { ...state, documents: [record, ...state.documents].slice(0, 100) }, record };
}

function seedState(): DemoState {
  return { version: 1, commercialDocuments: [], inventoryProducts: [], obligations: [], activities: [], idempotency: {}, documents: demoDocuments.map((document, index) => {
    const total = document.amount;
    const exempt = document.kind === "34" || document.kind === "41";
    const net = exempt ? total : Math.round(total / 1.19);
    return {
      ...document,
      documentId: `DEMO-${document.kind}-${document.folio}`,
      taxpayerRut: "76.192.083-9",
      xmlSha256: createHash("sha256").update(`seed:${document.id}`).digest("hex"),
      itemName: "Operación demostrativa",
      net,
      vat: exempt ? 0 : total - net,
      events: [{ sequence: 1, event_type: "seeded_demo_document", occurred_at: `2026-07-${String(11 - Math.min(index, 2)).padStart(2, "0")}T12:00:00Z`, metadata: { synthetic: true } }],
    };
  }) };
}

function normalizeState(state: Partial<DemoState>): DemoState {
  const seed = seedState();
  return { version: 1, documents: Array.isArray(state.documents) ? state.documents : seed.documents, commercialDocuments: state.commercialDocuments ?? [], inventoryProducts: state.inventoryProducts ?? [], obligations: state.obligations ?? [], activities: state.activities ?? [], idempotency: state.idempotency ?? {} };
}

function supabaseFetch(path: string, init: RequestInit = {}) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Persistencia sandbox no configurada");
  return fetch(new URL(path, url), { ...init, cache: "no-store", headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json", ...init.headers } });
}
