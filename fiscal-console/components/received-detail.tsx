"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, FileCode2, PackageX, ShieldCheck } from "lucide-react";

type Decision = "accept" | "receipt" | "content" | "partial" | "total" | null;
const options = [
  ["accept", "Aceptar contenido", "Confirma que el DTE está correcto", CheckCircle2],
  ["receipt", "Confirmar recepción", "Mercaderías o servicios recibidos", CheckCircle2],
  ["content", "Documento incorrecto", "Reclamar contra su contenido", AlertTriangle],
  ["partial", "Entrega parcial", "Faltan bienes o parte del servicio", PackageX],
  ["total", "No hubo entrega", "Reclamo por falta total", PackageX],
] as const;

export function ReceivedDetail() {
  const [decision, setDecision] = useState<Decision>(null);
  const [confirmed, setConfirmed] = useState(false);
  const selected = decisionCopy(decision);
  const choose = (value: Decision) => { setDecision(value); setConfirmed(false); };
  return <div className="page section-page">
    <Link href="/recibidos" className="back-link"><ArrowLeft size={15} /> Volver a recibidos</Link>
    <header className="page-header"><div><p className="eyebrow">Factura electrónica 33 · Folio 7.841</p><h1>DISTRIBUIDORA CENTRAL SPA</h1><p>RUT 76.345.210-8 · Recepción sintética del 10 de julio de 2026.</p></div><span className="received-status warning">Por revisar</span></header>
    <div className="received-detail-grid">
      <section className="panel received-document-card"><div className="document-preview"><span>33</span><div><strong>Factura electrónica</strong><p>XML firmado y esquema oficial válidos</p></div></div><dl className="detail-values"><div><dt>Neto</dt><dd>$360.000</dd></div><div><dt>IVA 19%</dt><dd>$68.400</dd></div><div className="total-row"><dt>Total</dt><dd>$428.400</dd></div></dl><div className="verification-list"><p><CheckCircle2 size={15} /> Firma XMLDSig verificada</p><p><CheckCircle2 size={15} /> RUT receptor corresponde al tenant</p><p><CheckCircle2 size={15} /> Sin duplicado de emisor, tipo y folio</p><p><FileCode2 size={15} /> XML original conservado con SHA-256</p></div><div className="legal-warning"><AlertTriangle size={18} /><p>Plazo desconocido: este ejemplo no posee timestamp autoritativo del SII. Completo no inventará una fecha.</p></div></section>
      <section className="panel decision-card"><p className="eyebrow">Decisión tributaria</p><h2>¿Qué ocurrió con esta compra?</h2><div className="decision-options">{options.map(([id, title, detail, Icon]) => <DecisionButton key={id} active={decision === id} icon={<Icon size={18} />} title={title} detail={detail} onClick={() => choose(id)} />)}</div>{selected && <div className="decision-consequence"><ShieldCheck size={18} /><div><strong>{selected.title}</strong><p>{selected.body}</p><code>{selected.code}</code></div></div>}{decision && !["accept", "receipt"].includes(decision) && <label className="decision-reason">Razón del reclamo<textarea maxLength={200} defaultValue="Describe aquí el problema comprobable" /></label>}<button className="primary-button" disabled={!decision || confirmed} onClick={() => setConfirmed(true)}>{confirmed ? "Ensayo registrado" : "Confirmar en simulador"}</button>{confirmed && <p className="simulation-success"><CheckCircle2 size={15} /> La intención quedó simulada; no se contactó al SII.</p>}</section>
    </div>
  </div>;
}

function DecisionButton({ active, icon, title, detail, onClick }: { active: boolean; icon: ReactNode; title: string; detail: string; onClick: () => void }) { return <button className={active ? "selected" : ""} onClick={onClick}>{icon}<span><strong>{title}</strong><small>{detail}</small></span></button>; }

function decisionCopy(decision: Decision) {
  if (decision === "accept") return { code: "ACD", title: "Aceptación expresa del contenido", body: "Después de ACD no podrás reclamar. ERM es una acción separada y compatible." };
  if (decision === "receipt") return { code: "ERM", title: "Recibo de mercaderías o servicios", body: "Confirma entrega o prestación. Después de ERM no podrás reclamar." };
  if (decision === "content") return { code: "RCD", title: "Reclamo contra el contenido", body: "Declara una discrepancia del documento; la razón quedará auditada." };
  if (decision === "partial") return { code: "RFP", title: "Reclamo por falta parcial", body: "Declara que sólo una parte de los bienes o servicios fue recibida." };
  if (decision === "total") return { code: "RFT", title: "Reclamo por falta total", body: "Declara que los bienes o servicios respaldados no fueron recibidos." };
  return null;
}
