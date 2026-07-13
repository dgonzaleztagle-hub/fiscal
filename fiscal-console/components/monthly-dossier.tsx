import Link from "next/link";
import { AlertTriangle, CheckCircle2, Download, FileArchive, FileQuestion, Link2Off, ShieldCheck } from "lucide-react";
import type { EngineSectionResult } from "@/lib/fiscal-api";

const evidence = [
  { label: "Ventas y compras documentadas", detail: "48 ventas · 18 compras con XML", source: "Ledger fiscal · hash 8de4…9ac1", state: "Disponible", tone: "success", icon: CheckCircle2 },
  { label: "Registro de Compras y Ventas", detail: "Snapshot RCV v2 · 10 jul 2026", source: "SII conectado · hash c221…71df", state: "Disponible", tone: "success", icon: CheckCircle2 },
  { label: "Cierre mensual calculado", detail: "Versión 1 · fórmula Plus baseline", source: "Cálculo inmutable · hash 5fa0…e318", state: "Disponible", tone: "success", icon: CheckCircle2 },
  { label: "Boletas de honorarios", detail: "Consulta preparada, sin snapshot congelado", source: "Conector BHE", state: "Falta versión", tone: "warning", icon: FileQuestion },
  { label: "Resumen de Personas", detail: "Se exigirá sólo si el tenant contrata Personas", source: "Módulo no conectado", state: "No conectado", tone: "neutral", icon: Link2Off },
  { label: "Pagos electrónicos", detail: "Vouchers y liquidaciones estarán aquí al habilitarlos", source: "Módulo no conectado", state: "No conectado", tone: "neutral", icon: Link2Off },
];

type DossierPayload = { ready: boolean; ready_count: number; total_count: number; items: Array<{ code: string; label: string; state: string; detail: string; source_ref: string | null; source_sha256: string | null }> };

export function MonthlyDossier({ result }: { result: EngineSectionResult<DossierPayload> }) {
  const rows = result.data?.items.map(item => ({ label: item.label, detail: item.detail, source: item.source_ref ? `${item.source_ref} · ${item.source_sha256?.slice(0, 8) ?? "sin hash"}` : "Sin fuente", state: item.state === "ready" ? "Disponible" : item.state === "not_connected" ? "No conectado" : "Falta versión", tone: item.state === "ready" ? "success" : item.state === "not_connected" ? "neutral" : "warning", icon: item.state === "ready" ? CheckCircle2 : item.state === "not_connected" ? Link2Off : FileQuestion })) ?? evidence;
  const ready = result.data?.ready ?? false;
  const readyCount = result.data?.ready_count ?? 3;
  const totalCount = result.data?.total_count ?? 6;
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">Expediente fiscal · Julio 2026</p><h1>Todo lo que respalda este mes</h1><p>Una carpeta verificable para entender el período sin reconstruirlo documento por documento.</p></div><button className="primary-button" type="button" disabled={!ready}><Download size={16} /> Descargar paquete</button></header><div className="dossier-status panel"><div><FileArchive size={24} /><div><small>{readyCount} de {totalCount} fuentes disponibles</small><strong>{ready ? "Expediente listo para entregar" : "Todavía existen fuentes pendientes"}</strong><p>Cada integración aporta una versión, nunca un número suelto.</p></div></div><span className={`received-status ${ready ? "success" : "warning"}`}>{ready ? "Listo" : "Incompleto"}</span></div><section className="panel dossier-list"><div className="table-toolbar"><div><h2>Inventario de evidencia</h2><p>Cada archivo o snapshot conserva origen, versión y hash</p></div><span className="demo-action">{result.source === "engine" ? "Motor conectado" : "Datos sintéticos"}</span></div>{rows.map(({ icon: Icon, ...item }) => <article key={item.label}><span className={`dossier-icon ${item.tone}`}><Icon size={18} /></span><div><strong>{item.label}</strong><p>{item.detail}</p><small>{item.source}</small></div><em className={`received-status ${item.tone}`}>{item.state}</em></article>)}</section><div className="dossier-actions"><section className="tip-card"><AlertTriangle size={21} /><div><strong>Un PDF no completa evidencia tributaria faltante</strong><p>Puede acompañar el expediente, pero el XML o snapshot autoritativo seguirá marcado como pendiente.</p></div></section><section className="panel dossier-next"><ShieldCheck size={21} /><div><strong>Volver al cierre mensual</strong><p>Resuelve el faltante y genera una nueva versión antes de congelar.</p></div><Link className="secondary-button" href="/cierre">Revisar cierre</Link></section></div></div>;
}
