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
  events: DemoEvent[];
};

export type DemoState = {
  version: 1;
  documents: StoredDemoDocument[];
};

const labels: Record<number, string> = {
  33: "Factura electrónica", 34: "Factura exenta", 39: "Boleta electrónica", 41: "Boleta exenta",
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
    try { return JSON.parse(await readFile(join(localStore, `${id}.json`), "utf8")) as DemoState; }
    catch { return seedState(); }
  }
  const response = await supabaseFetch(`/rest/v1/fiscal_demo_sessions?session_id=eq.${encodeURIComponent(id)}&select=state&limit=1`);
  if (!response.ok) throw new Error(`Sandbox storage HTTP ${response.status}`);
  const rows = await response.json() as Array<{ state: DemoState }>;
  return rows[0]?.state ?? seedState();
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

export function issueSyntheticDocument(state: DemoState, input: { documentType: number; receiver: string; itemName: string; quantity: number; unitPrice: number }) {
  if (![33, 34, 39, 41].includes(input.documentType)) throw new Error("Tipo documental no permitido en sandbox");
  if (!input.itemName.trim() || !input.receiver.trim() || !Number.isFinite(input.quantity) || !Number.isFinite(input.unitPrice) || input.quantity <= 0 || input.quantity > 10_000 || input.unitPrice < 0 || input.unitPrice > 1_000_000_000) throw new Error("Datos incompletos o fuera de rango");
  const exempt = input.documentType === 34 || input.documentType === 41;
  const invoice = input.documentType === 33 || input.documentType === 34;
  const base = Math.round(input.quantity * input.unitPrice);
  const net = exempt ? base : invoice ? base : Math.round(base / 1.19);
  const vat = exempt ? 0 : invoice ? Math.round(base * 0.19) : base - net;
  const total = invoice ? net + vat : base;
  const currentMax = state.documents.filter(row => Number(row.kind) === input.documentType).reduce((max, row) => Math.max(max, Number(row.folio.replaceAll(".", "")) || 0), 0);
  const folio = currentMax + 1;
  const issuedAt = new Date().toISOString();
  const payload = { documentType: input.documentType, folio, receiver: input.receiver, itemName: input.itemName, net, vat, total };
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
    events: [
      { sequence: 1, event_type: "draft_validated", occurred_at: issuedAt, metadata: { synthetic: true } },
      { sequence: 2, event_type: "folio_reserved", occurred_at: issuedAt, metadata: { folio, synthetic: true } },
      { sequence: 3, event_type: "signed_with_synthetic_credential", occurred_at: issuedAt, metadata: { synthetic: true } },
      { sequence: 4, event_type: "accepted_by_sii_simulator", occurred_at: issuedAt, metadata: { track_id: `SIM-${Date.now()}`, synthetic: true } },
    ],
  };
  return { state: { ...state, documents: [record, ...state.documents].slice(0, 100) }, record };
}

function seedState(): DemoState {
  return { version: 1, documents: demoDocuments.map((document, index) => {
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
      events: [{ sequence: 1, event_type: "seeded_demo_document", occurred_at: `2026-07-${11 - Math.min(index, 2)}T12:00:00Z`, metadata: { synthetic: true } }],
    };
  }) };
}

function supabaseFetch(path: string, init: RequestInit = {}) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Persistencia sandbox no configurada");
  return fetch(new URL(path, url), { ...init, cache: "no-store", headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json", ...init.headers } });
}
