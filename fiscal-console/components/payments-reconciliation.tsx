import { AlertTriangle, CheckCircle2, CreditCard, Upload } from "lucide-react";
import { clp } from "@/lib/format";
import type { EngineSectionResult } from "@/lib/fiscal-api";

const demoPayments = [
  { ref: "TBK-78421", sale: "Pedido #1842", amount: 28_650, evidence: "Voucher reemplaza boleta", state: "Conciliado", tone: "success" },
  { ref: "TBK-78420", sale: "Pedido #1841", amount: 14_990, evidence: "Boleta 39 · 1841", state: "Conciliado", tone: "success" },
  { ref: "GET-11903", sale: "Pedido no encontrado", amount: 36_900, evidence: "Sin respaldo resuelto", state: "Revisar", tone: "warning" },
];

type PaymentPayload = { total: number; ready: boolean; version: number; items: Array<{ provider_reference: string; sale_ref: string; amount: number; fiscal_evidence: string; state: string }> };

export function PaymentsReconciliation({ result }: { result: EngineSectionResult<PaymentPayload> }) {
  const rows = result.data?.items.map((item) => ({ ref: item.provider_reference, sale: item.sale_ref, amount: item.amount, evidence: item.fiscal_evidence, state: item.state === "match" ? "Conciliado" : "Revisar", tone: item.state === "match" ? "success" : "warning" })) ?? (result.source === "demo" ? demoPayments : []);
  const total = result.data?.total ?? (result.source === "demo" ? 80_540 : 0);
  const reconciled = rows.filter((item) => item.tone === "success").reduce((sum, item) => sum + item.amount, 0);
  const pending = total - reconciled;
  return <div className="page section-page">
    <header className="page-header"><div><p className="eyebrow">Pagos electrónicos · Julio 2026</p><h1>Vouchers y ventas, sin duplicar boletas</h1><p>Completo separa el cobro, la venta y su respaldo tributario.</p></div><button className="primary-button" type="button" disabled><Upload size={16} /> Importación mediante integración</button></header>
    <div className="summary-grid"><article className="panel summary-card"><CreditCard size={19} /><div><small>Total importado</small><strong>{clp(total)}</strong><p>{rows.length} pagos electrónicos</p></div></article><article className="panel summary-card"><CheckCircle2 size={19} /><div><small>Conciliado</small><strong>{clp(reconciled)}</strong><p>Pagos con venta y respaldo</p></div></article><article className="panel summary-card metric-warning"><AlertTriangle size={19} /><div><small>Por revisar</small><strong>{clp(pending)}</strong><p>Diferencias pendientes</p></div></article></div>
    <section className="panel payments-list"><div className="table-toolbar"><div><h2>Resultado de conciliación</h2><p>Identidad única por proveedor, terminal, autorización y referencia</p></div><span className="demo-action">{result.source === "engine" ? `Motor · v${result.data?.version ?? "—"}` : "Datos sintéticos"}</span></div>{rows.length ? rows.map((item) => <article key={item.ref}><span className="dossier-icon neutral"><CreditCard size={17} /></span><div><strong>{item.sale}</strong><p>{item.ref} · {item.evidence}</p></div><b>{clp(item.amount)}</b><em className={`received-status ${item.tone}`}>{item.state}</em></article>) : <div className="empty-inline"><strong>Sin pagos importados</strong><p>La integración todavía no ha entregado vouchers para este período.</p></div>}</section>
    <section className="tip-card"><AlertTriangle size={21} /><div><strong>Voucher no significa siempre lo mismo</strong><p>Completo aplica el modelo configurado para el tenant: reemplaza boleta o exige una boleta adicional.</p></div></section>
  </div>;
}
