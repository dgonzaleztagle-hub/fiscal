"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, FileCode2, PackageX, ShieldCheck } from "lucide-react";
import { receivedDemoById } from "@/lib/received-demo-data";

type Decision = "accept" | "receipt" | "content" | "partial" | "total" | null;
const options = [
  ["accept", "Aceptar contenido", "Confirma que el DTE está correcto", CheckCircle2],
  ["receipt", "Confirmar recepción", "Mercaderías o servicios recibidos", CheckCircle2],
  ["content", "Documento incorrecto", "Reclamar contra su contenido", AlertTriangle],
  ["partial", "Entrega parcial", "Faltan bienes o parte del servicio", PackageX],
  ["total", "No hubo entrega", "Reclamo por falta total", PackageX],
] as const;

export function ReceivedDetail({ documentId }: { documentId: string }) {
  const document = receivedDemoById(documentId);
  const [decision, setDecision] = useState<Decision>(null), [reason, setReason] = useState(""), [confirmed, setConfirmed] = useState(false);
  const selected = decisionCopy(decision);
  useEffect(() => { fetch(`/api/demo/activities?area=received_decision&document=${encodeURIComponent(document.id)}`).then(response => response.json()).then((rows: Array<{ payload: { decision?: Decision; reason?: string } }>) => { if (rows[0]?.payload.decision) { setDecision(rows[0].payload.decision); setReason(rows[0].payload.reason ?? ""); setConfirmed(true); } }); }, [document.id]);
  const choose = (value: Decision) => { if (!confirmed) { setDecision(value); setReason(""); } };
  async function confirm() { if (!decision) return; const response = await fetch("/api/demo/activities?area=received_decision", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ document: document.id, decision, code: selected?.code, reason }) }); if (response.ok) setConfirmed(true); }
  const claim = decision && !["accept", "receipt"].includes(decision);
  return <div className="page section-page">
    <Link href="/recibidos" className="back-link"><ArrowLeft size={15} /> Volver a recibidos</Link>
    <header className="page-header"><div><p className="eyebrow">DTE {document.type} · Folio {document.folio}</p><h1>{document.issuer}</h1><p>RUT {document.rut} · Recepción sintética del {document.date}.</p></div><span className={`received-status ${document.tone}`}>{document.status}</span></header>
    <div className="received-detail-grid">
      <section className="panel received-document-card"><div className="document-preview"><span>{document.type}</span><div><strong>{document.type === 34 ? "Factura exenta electrónica" : document.type === 61 ? "Nota de crédito electrónica" : "Factura electrónica"}</strong><p>XML firmado y esquema oficial válidos</p></div></div><dl className="detail-values"><div><dt>Neto</dt><dd>{document.net}</dd></div><div><dt>IVA 19%</dt><dd>{document.vat}</dd></div><div className="total-row"><dt>Total</dt><dd>{document.total}</dd></div></dl><div className="verification-list"><p><CheckCircle2 size={15} /> Firma XMLDSig verificada</p><p><CheckCircle2 size={15} /> RUT receptor corresponde al tenant</p><p><CheckCircle2 size={15} /> Sin duplicado de emisor, tipo y folio</p><p><FileCode2 size={15} /> XML original conservado con SHA-256</p></div><div className="legal-warning"><AlertTriangle size={18} /><p>Plazo desconocido: este ejemplo no posee timestamp autoritativo del SII. Completo no inventará una fecha.</p></div></section>
      <section className="panel decision-card"><p className="eyebrow">Decisión tributaria</p><h2>¿Qué ocurrió con esta compra?</h2><div className="decision-options">{options.map(([id, title, detail, Icon]) => <DecisionButton key={id} active={decision === id} disabled={confirmed} icon={<Icon size={18} />} title={title} detail={detail} onClick={() => choose(id)} />)}</div>{selected && <div className="decision-consequence"><ShieldCheck size={18} /><div><strong>{selected.title}</strong><p>{selected.body}</p><code>{selected.code}</code></div></div>}{claim && <label className="decision-reason">Razón del reclamo<textarea maxLength={200} value={reason} disabled={confirmed} onChange={event => setReason(event.target.value)} placeholder="Describe el problema comprobable" /></label>}<button className="primary-button" disabled={!decision || confirmed || Boolean(claim && reason.trim().length < 5)} onClick={confirm}>{confirmed ? "Ensayo registrado" : "Confirmar en simulador"}</button>{confirmed && <p className="simulation-success"><CheckCircle2 size={15} /> La decisión quedó persistida y bloqueada; no se contactó al SII.</p>}</section>
    </div>
  </div>;
}

function DecisionButton({ active, disabled, icon, title, detail, onClick }: { active: boolean; disabled: boolean; icon: ReactNode; title: string; detail: string; onClick: () => void }) { return <button className={active ? "selected" : ""} disabled={disabled} onClick={onClick}>{icon}<span><strong>{title}</strong><small>{detail}</small></span></button>; }
function decisionCopy(decision: Decision) { if (decision === "accept") return { code: "ACD", title: "Aceptación expresa del contenido", body: "Después de ACD no podrás reclamar. ERM es una acción separada y compatible." }; if (decision === "receipt") return { code: "ERM", title: "Recibo de mercaderías o servicios", body: "Confirma entrega o prestación. Después de ERM no podrás reclamar." }; if (decision === "content") return { code: "RCD", title: "Reclamo contra el contenido", body: "Declara una discrepancia del documento; la razón quedará auditada." }; if (decision === "partial") return { code: "RFP", title: "Reclamo por falta parcial", body: "Declara que sólo una parte de los bienes o servicios fue recibida." }; if (decision === "total") return { code: "RFT", title: "Reclamo por falta total", body: "Declara que los bienes o servicios respaldados no fueron recibidos." }; return null; }
