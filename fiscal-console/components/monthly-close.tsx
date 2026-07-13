import Link from "next/link";
import { AlertTriangle, CheckCircle2, FileArchive, FileCheck2, RefreshCw, ShieldCheck } from "lucide-react";
import { clp } from "@/lib/format";
import type { EngineSectionResult } from "@/lib/fiscal-api";
import { DemoActionButton } from "./demo-action-button";

const steps = [
  { label: "Ventas del período", detail: "DTE emitidos y notas incorporados", state: "Listo", tone: "success" },
  { label: "Compras respaldadas", detail: "18 XML conciliados · falta 1 respaldo", state: "Revisar", tone: "warning" },
  { label: "Honorarios y Personas", detail: "BHE cargadas · resumen Personas pendiente", state: "Pendiente", tone: "neutral" },
  { label: "Pagos electrónicos", detail: "Liquidación y vouchers aún no importados", state: "Pendiente", tone: "neutral" },
];

type ClosePayload = { version: number; payload: { sales: { total: number; vat: number }; purchases: { total: number; vat: number }; total_payable: number; ppm: number; lines: Array<{ code: string; amount: number }> } };

export function MonthlyClose({ result }: { result: EngineSectionResult<ClosePayload[]> }) {
  const close = result.data?.[0];
  const fallback = result.source === "demo";
  const payable = close?.payload.total_payable ?? (fallback ? 157_492 : 0);
  const sales = close?.payload.sales.total ?? (fallback ? 1_218_990 : 0);
  const purchases = close?.payload.purchases.total ?? (fallback ? 632_400 : 0);
  const salesVat = close?.payload.sales.vat ?? (fallback ? 194_629 : 0);
  const purchaseVat = close?.payload.purchases.vat ?? (fallback ? 68_400 : 0);
  const extras = close ? close.payload.ppm + (close.payload.lines.find(line => line.code === "second_category_withholding")?.amount ?? 0) : (fallback ? 31_263 : 0);
  return <div className="page section-page">
    <header className="page-header"><div><p className="eyebrow">Operación fiscal · Julio 2026</p><h1>Cómo viene este mes</h1><p>Completa la evidencia, resuelve diferencias y entrega un período explicable a tu contador.</p></div><DemoActionButton area="monthly_close_recalculation" done="Nueva versión sandbox calculada"><RefreshCw size={16} /> Recalcular versión</DemoActionButton></header>
    <div className="close-state"><div><span>2 de 4 fuentes preparadas</span><strong>El mes todavía necesita revisión</strong></div><span className="demo-action">{result.source === "engine" ? `Cálculo v${close?.version ?? "—"} · motor` : "Cálculo v1 · datos sintéticos"}</span></div>
    <div className="summary-grid"><article className="panel summary-card"><FileCheck2 size={19} /><div><small>Ventas documentadas</small><strong>{clp(sales)}</strong><p>Incluye notas y exentos</p></div></article><article className="panel summary-card"><FileArchive size={19} /><div><small>Compras respaldadas</small><strong>{clp(purchases)}</strong><p>Una factura sólo aparece en RCV</p></div></article><article className="panel summary-card metric-warning"><AlertTriangle size={19} /><div><small>Pago estimado</small><strong>{clp(payable)}</strong><p>Informativo · cierre no congelado</p></div></article></div>
    <div className="close-layout"><section className="panel close-checklist"><div className="table-toolbar"><div><h2>Camino para cerrar julio</h2><p>Cada fuente conserva versión, fecha y evidencia</p></div><span className="received-status warning">2 pendientes</span></div>{steps.map((step, index) => <article key={step.label}><span className={step.tone === "success" ? "close-step done" : "close-step"}>{step.tone === "success" ? <CheckCircle2 size={17} /> : index + 1}</span><div><strong>{step.label}</strong><p>{step.detail}</p></div><em className={`received-status ${step.tone}`}>{step.state}</em></article>)}</section><aside className="panel close-explanation"><ShieldCheck size={25} /><p className="eyebrow">Qué puede hacerse ahora</p><h2>Resolver antes de congelar</h2><p>Completo no hará cuadrar el período modificando documentos. Cada diferencia abre una explicación o una tarea.</p><dl><div><dt>IVA ventas</dt><dd>+{clp(salesVat)}</dd></div><div><dt>IVA compras</dt><dd>−{clp(purchaseVat)}</dd></div><div><dt>Retenciones + PPM</dt><dd>+{clp(extras)}</dd></div></dl><Link className="secondary-button" href="/f29">Ver propuesta F29 explicada</Link></aside></div>
    <section className="tip-card"><FileArchive size={21} /><div><strong>Congelar no significa declarar</strong><p>Creará una fotografía inmutable del período y un paquete para revisión. No presenta formularios ni genera una orden de pago en el SII.</p><Link href="/expediente">Ver expediente del mes →</Link></div></section>
  </div>;
}
