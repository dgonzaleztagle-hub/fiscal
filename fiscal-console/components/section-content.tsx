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

const issueOptions = [
  { code: "39 / 41", title: "Registrar una venta", detail: "Boleta afecta o exenta según los productos.", icon: Receipt, ready: true },
  { code: "33 / 34", title: "Facturar a una empresa", detail: "Factura con receptor identificado y condiciones de pago.", icon: Building2, ready: true, href: "/emitir/factura" },
  { code: "61 / 56", title: "Corregir un documento", detail: "Anula o ajusta una emisión anterior de forma trazable.", icon: FileMinus2, ready: true, href: "/emitir/correccion" },
  { code: "52", title: "Respaldar un traslado", detail: "Guía para despacho, devolución o movimiento interno.", icon: PackageCheck, ready: true, href: "/emitir/guia" },
];

type SectionCopy = { eyebrow: string; title: string; description: string };

export function SectionContent({ section }: { section: NavigationSection }) {
  const content = navigationSections[section];
  if (section === "emitir") return <IssueSection content={content} />;
  if (section === "documentos") return <DocumentsSection content={content} />;
  if (section === "recibidos") return <ReceivedInbox />;
  if (section === "reportes") return <RcvReport />;
  if (section === "rcv") return <RcvSection />;
  if (section === "f29") return <F29Section />;
  if (section === "bhe") return <BheSection />;
  if (section === "situacion") return <SiiProfileSection />;
  if (section === "sincronizaciones") return <SyncSection />;
  if (section === "configuracion") return <Onboarding />;
  if (section === "clientes") return <ClientsSection />;
  if (section === "productos") return <ProductsSection />;
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
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">{content.eyebrow}</p><h1>{content.title}</h1><p>{content.description}</p></div><Link className="primary-button" href="/emitir"><FilePlus2 size={18} /> Emitir documento</Link></header><div className="filter-row"><button className="active">Todos <span>5</span></button><button>Aceptados <span>2</span></button><button>En proceso <span>1</span></button><button>Por resolver <span>1</span></button><button>Borradores <span>1</span></button></div><section className="panel documents-panel"><DocumentTable /></section></div>;
}

function CertificationSection({ content }: { content: SectionCopy }) {
  void content;
  return <CertificationCockpit />;
}
