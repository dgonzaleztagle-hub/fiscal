import Link from "next/link";
import { ArrowRight, BookOpenCheck, Building2, FileCheck2, FileMinus2, FilePlus2, PackageCheck, Receipt, Search, ShieldCheck } from "lucide-react";
import { navigationSections, type NavigationSection } from "@/lib/demo-data";
import { DocumentTable } from "./document-table";
import { ClientsSection, ProductsSection } from "./catalog-sections";
import { ReceivedInbox } from "./received-inbox";
import { RcvReport } from "./rcv-report";
import { Onboarding } from "./onboarding";
import { BheSection, F29Section, RcvSection, SiiProfileSection, SyncSection } from "./sii-sections";
import { CertificationCockpit } from "./certification-cockpit";
import { MonthlyClose } from "./monthly-close";
import { MonthlyDossier } from "./monthly-dossier";
import { PaymentsReconciliation } from "./payments-reconciliation";
import { CommercialCenter } from "./commercial-center";
import { ApprovalsCenter } from "./approvals-center";
import { RecurringCenter } from "./recurring-center";
import { fiscalSection } from "@/lib/fiscal-api";
import { FolioControl, ProvidersSection, SubmissionTracking } from "./operational-sections";
import { DocumentFilters } from "./document-filters";

const issueOptions = [
  { code: "39 / 41", title: "Registrar una venta", detail: "Boleta afecta o exenta según los productos.", icon: Receipt, ready: true },
  { code: "33 / 34", title: "Facturar a una empresa", detail: "Factura con receptor identificado y condiciones de pago.", icon: Building2, ready: true, href: "/emitir/factura" },
  { code: "61 / 56", title: "Corregir un documento", detail: "Anula o ajusta una emisión anterior de forma trazable.", icon: FileMinus2, ready: true, href: "/emitir/correccion" },
  { code: "52", title: "Respaldar un traslado", detail: "Guía para despacho, devolución o movimiento interno.", icon: PackageCheck, ready: true, href: "/emitir/guia" },
];

type SectionCopy = { eyebrow: string; title: string; description: string };

export async function SectionContent({ section }: { section: NavigationSection }) {
  const content = navigationSections[section];
  if(section==="aprobaciones") { const result=await fiscalSection<Array<{id:string;operation_type:string;operation_ref:string;amount:number;requested_by:string;required_role:string;status:string}>>("/v1/approvals?status=pending"); return <ApprovalsCenter initial={result.data??[]} source={result.source}/>; }
  if(section==="recurrencia") { const result=await fiscalSection<Array<{id:string;counterparty_name:string;description:string;amount:number;day_of_month:number;next_run_on:string;active:number}>>("/v1/recurring-agreements"); return <RecurringCenter initial={result.data??[]} source={result.source}/>; }
  if (["ventas", "compras", "inventario", "caja"].includes(section)) return <CommercialCenter section={section as "ventas" | "compras" | "inventario" | "caja"} />;
  if (section === "emitir") return <IssueSection content={content} />;
  if (section === "documentos") return <DocumentsSection content={content} />;
  if (section === "recibidos") return <ReceivedInbox />;
  if (section === "reportes") return <RcvReport />;
  if (section === "cierre") return <MonthlyClose result={await fiscalSection("/v1/reports/monthly/2026/7/close/snapshots")} />;
  if (section === "expediente") return <MonthlyDossier result={await fiscalSection("/v1/reports/monthly/2026/7/dossier")} />;
  if (section === "pagos") return <PaymentsReconciliation result={await fiscalSection("/v1/payments/reconciliation/2026/7")} />;
  if (section === "rcv") return <RcvSection />;
  if (section === "f29") return <F29Section result={await fiscalSection("/v1/reports/monthly/2026/7/close/snapshots")} />;
  if (section === "bhe") return <BheSection />;
  if (section === "situacion") return <SiiProfileSection />;
  if (section === "sincronizaciones") return <SyncSection />;
  if (section === "configuracion") return <Onboarding />;
  if (section === "clientes") return <ClientsSection />;
  if (section === "productos") return <ProductsSection />;
  if (section === "proveedores") return <ProvidersSection />;
  if (section === "folios") return <FolioControl />;
  if (section === "envios") return <SubmissionTracking />;
  if (section === "certificacion") return <CertificationSection content={content} />;
  return (
    <div className="page section-page"><header className="page-header"><div><p className="eyebrow">{content.eyebrow}</p><h1>{content.title}</h1><p>{content.description}</p></div><button className="secondary-button" type="button"><Search size={17} /> Buscar</button></header><section className="panel empty-state"><span><BookOpenCheck size={28} /></span><h2>Esta área ya tiene un lugar definitivo</h2><p>El contrato y la navegación están listos. Se activará con datos reales en su hito documental, manteniendo la misma experiencia.</p><div className="progress-line"><i /><i /><i /><i /></div><small>Modo demostración · Sin efectos tributarios</small></section>
    </div>
  );
}

function IssueSection({ content }: { content: SectionCopy }) {
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">{content.eyebrow}</p><h1>{content.title}</h1><p>{content.description}</p></div></header><div className="issue-grid">{issueOptions.map(({ code, title, detail, icon: Icon, ready, ...option }) => ready ? <Link className="issue-option" href={option.href ?? "/emitir/boleta"} key={code}><span><Icon size={23} /></span><div><small>{code}</small><h2>{title}</h2><p>{detail}</p><em className="ready-label"><FileCheck2 size={13} /> Disponible en sandbox</em></div><ArrowRight size={19} /></Link> : option.href ? <Link className="issue-option" href={option.href} key={code}><span><Icon size={23} /></span><div><small>{code}</small><h2>{title}</h2><p>{detail}</p><em>Asistente disponible · Emisión bloqueada</em></div><ArrowRight size={19} /></Link> : <button className="issue-option" key={code} type="button"><span><Icon size={23} /></span><div><small>{code}</small><h2>{title}</h2><p>{detail}</p><em>Contrato validado · Builder en desarrollo</em></div><ArrowRight size={19} /></button>)}</div><section className="tip-card"><ShieldCheck size={21} /><div><strong>La consola te guía por intención</strong><p>No necesitas conocer códigos DTE. Antes de firmar verás el efecto tributario y cualquier referencia obligatoria.</p></div></section></div>;
}

function DocumentsSection({ content }: { content: SectionCopy }) {
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">{content.eyebrow}</p><h1>{content.title}</h1><p>{content.description}</p></div><Link className="primary-button" href="/emitir"><FilePlus2 size={18} /> Emitir documento</Link></header><DocumentFilters /><section className="panel documents-panel"><DocumentTable /></section></div>;
}

function CertificationSection({ content }: { content: SectionCopy }) {
  void content;
  return <CertificationCockpit />;
}
