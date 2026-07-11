import Link from "next/link";
import { CheckCircle2, Download, ExternalLink, FileCode2, FileText, Fingerprint } from "lucide-react";
import { clp } from "@/lib/format";
import { fiscalArtifactUrl, type FiscalDocumentDetail } from "@/lib/fiscal-api";
import { StatusPill } from "./status-pill";

export function DocumentDetail({ document }: { document: FiscalDocumentDetail }) {
  return <div className="page section-page document-detail-page">
    <header className="page-header"><div><p className="eyebrow">Documento emitido · DTE {document.kind}</p><h1>{document.label}</h1><p>Folio {document.folio} · {document.receiver}</p></div><StatusPill status={document.status}>{document.statusLabel}</StatusPill></header>
    <div className={`data-source ${document.source}`}>{document.source === "engine" ? "Motor local conectado · registro inmutable" : "Datos demostrativos · sin XML real"}{document.warning ? ` · ${document.warning}` : ""}</div>
    <div className="document-detail-grid">
      <section className="panel fiscal-summary"><div className="document-preview"><span>{document.kind}</span><div><strong>{document.label}</strong><p>{document.documentId}</p></div></div><dl className="detail-values"><div><dt>Receptor</dt><dd>{document.receiver}</dd></div><div><dt>Emisor</dt><dd>{document.taxpayerRut}</dd></div><div><dt>Fecha de emisión</dt><dd>{document.issuedAt}</dd></div><div className="total-row"><dt>Total</dt><dd>{document.amount ? clp(document.amount) : "$0"}</dd></div></dl><div className="verification-list"><p><CheckCircle2 size={15} /> Documento firmado y preservado</p><p><Fingerprint size={15} /> SHA-256: <code>{document.xmlSha256}</code></p></div></section>
      <aside className="panel artifact-panel"><p className="eyebrow">Representaciones</p><h2>Archivos tributarios</h2><p>Las descargas pasan por el servidor de la consola; la credencial del motor nunca llega al navegador.</p>{document.source === "engine" ? <div className="artifact-actions"><a className="secondary-button" href={fiscalArtifactUrl(document.id, "xml")}><FileCode2 size={17} /> Descargar XML <Download size={14} /></a><a className="secondary-button" href={fiscalArtifactUrl(document.id, "pdf")} target="_blank" rel="noreferrer"><FileText size={17} /> Abrir PDF <ExternalLink size={14} /></a></div> : <button className="secondary-button" disabled>Conecta el motor para descargar</button>}</aside>
    </div>
    <section className="panel event-timeline"><div className="panel-heading"><div><p className="eyebrow">Auditoría append-only</p><h2>Historia del documento</h2></div><Link className="quiet-button" href="/documentos">← Volver al listado</Link></div>{document.events.map((event) => <article key={event.sequence}><span>{event.sequence}</span><div><strong>{event.event_type.replaceAll("_", " ")}</strong><p>{new Intl.DateTimeFormat("es-CL", { dateStyle: "medium", timeStyle: "short" }).format(new Date(event.occurred_at))}</p><code>{JSON.stringify(event.metadata)}</code></div></article>)}</section>
  </div>;
}
