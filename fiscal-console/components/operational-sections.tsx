import Link from "next/link";
import { AlertTriangle, ArrowRight, Building2, CheckCircle2, Clock3, FileKey2, PackageCheck, RefreshCw, Send } from "lucide-react";
import { DemoActionButton } from "./demo-action-button";

const providers = [
  { name: "Distribuidora Central SpA", rut: "76.345.210-8", purchases: "$428.400", documents: "7 documentos", note: "1 factura por revisar", tone: "warning" },
  { name: "Servicios Frío Sur Ltda.", rut: "77.120.934-2", purchases: "$85.000", documents: "3 documentos", note: "XML y RCV conciliados", tone: "success" },
  { name: "Comercial La Plaza Ltda.", rut: "76.991.804-7", purchases: "$119.000", documents: "2 documentos", note: "Sin diferencias", tone: "success" },
] as const;

const cafRanges = [
  { type: "39", name: "Boleta electrónica", range: "1.801–2.500", available: "658", used: "42", state: "Operativo", tone: "success" },
  { type: "41", name: "Boleta exenta", range: "401–500", available: "84", used: "16", state: "Operativo", tone: "success" },
  { type: "33", name: "Factura electrónica", range: "201–300", available: "96", used: "4", state: "Operativo", tone: "success" },
  { type: "61", name: "Nota de crédito", range: "41–60", available: "18", used: "2", state: "Vigilar", tone: "warning" },
] as const;

const submissions = [
  { envelope: "ENV-BE-20260709-018", documents: "25 boletas · tipos 39/41", sent: "Hoy, 12:48", track: "9102847351", state: "Aceptado", tone: "success" },
  { envelope: "ENV-DTE-20260709-006", documents: "1 factura · tipo 33", sent: "Hoy, 11:19", track: "9102846118", state: "Aceptado", tone: "success" },
  { envelope: "ENV-BE-20260709-017", documents: "24 boletas · tipo 39", sent: "Hoy, 10:56", track: "9102845902", state: "Procesando", tone: "warning" },
] as const;

export function ProvidersSection() {
  return <div className="page section-page">
    <header className="page-header"><div><p className="eyebrow">Compras · Julio 2026</p><h1>Proveedores y respaldo</h1><p>Concentra documentos, diferencias y compras del período por contraparte.</p></div><span className="demo-action">Datos sintéticos</span></header>
    <div className="summary-grid"><article className="panel summary-card"><Building2 size={19}/><div><small>Proveedores activos</small><strong>12</strong><p>3 con movimiento este mes</p></div></article><article className="panel summary-card"><PackageCheck size={19}/><div><small>Compras respaldadas</small><strong>$632.400</strong><p>18 XML conciliados</p></div></article><article className="panel summary-card metric-warning"><AlertTriangle size={19}/><div><small>Por aclarar</small><strong>1</strong><p>Sólo figura en el RCV</p></div></article></div>
    <section className="panel operational-list"><div className="table-toolbar"><div><h2>Actividad del período</h2><p>Totales y evidencia tributaria asociada</p></div><Link className="secondary-button" href="/rcv">Ver conciliación RCV</Link></div>{providers.map(item => <article key={item.rut}><span className="document-code"><Building2 size={17}/></span><div><strong>{item.name}</strong><p>{item.rut} · {item.documents}</p></div><b>{item.purchases}</b><em className={`received-status ${item.tone}`}>{item.note}</em><Link aria-label={`Revisar ${item.name}`} href="/recibidos"><ArrowRight size={17}/></Link></article>)}</section>
  </div>;
}

export function FolioControl() {
  return <div className="page section-page">
    <header className="page-header"><div><p className="eyebrow">Continuidad operacional</p><h1>Folios y CAF bajo control</h1><p>Disponibilidad por documento sin exponer claves privadas ni permitir reutilizaciones.</p></div><span className="health-ok"><CheckCircle2 size={14}/> Operativa</span></header>
    <div className="summary-grid"><article className="panel summary-card"><FileKey2 size={19}/><div><small>Folios disponibles</small><strong>856</strong><p>4 rangos activos</p></div></article><article className="panel summary-card"><Clock3 size={19}/><div><small>Proyección boletas</small><strong>19 días</strong><p>Según consumo reciente</p></div></article><article className="panel summary-card"><CheckCircle2 size={19}/><div><small>Solapamientos</small><strong>0</strong><p>Rangos consistentes</p></div></article></div>
    <section className="panel operational-list"><div className="table-toolbar"><div><h2>Rangos activos</h2><p>La demo representa metadatos; el CAF privado nunca llega al navegador</p></div><span className="demo-action">Última revisión hace 2 min</span></div>{cafRanges.map(item => <article key={item.type}><span className="document-code">{item.type}</span><div><strong>{item.name}</strong><p>Rango {item.range}</p></div><div><small>Disponibles</small><b>{item.available}</b></div><div><small>Consumidos</small><b>{item.used}</b></div><em className={`received-status ${item.tone}`}>{item.state}</em></article>)}</section>
    <section className="tip-card"><AlertTriangle size={21}/><div><strong>La nota de crédito llegará antes a su umbral</strong><p>Completo avisará antes del agotamiento; nunca descargará ni reemplazará un CAF sin una acción autorizada.</p></div></section>
  </div>;
}

export function SubmissionTracking() {
  return <div className="page section-page">
    <header className="page-header"><div><p className="eyebrow">Comunicación SII · Hoy</p><h1>Envíos y seguimiento</h1><p>Cada sobre conserva documentos, Track ID, intentos y resultado reconciliado.</p></div><DemoActionButton area="submission_status_query" className="secondary-button" done="Estados simulados actualizados"><RefreshCw size={16}/> Consultar estados</DemoActionButton></header>
    <div className="summary-grid"><article className="panel summary-card"><Send size={19}/><div><small>Enviados hoy</small><strong>3</strong><p>50 documentos</p></div></article><article className="panel summary-card"><CheckCircle2 size={19}/><div><small>Aceptados</small><strong>2</strong><p>Sin reparos</p></div></article><article className="panel summary-card metric-warning"><Clock3 size={19}/><div><small>En proceso</small><strong>1</strong><p>Consulta pendiente</p></div></article></div>
    <section className="panel operational-list"><div className="table-toolbar"><div><h2>Sobres recientes</h2><p>Un timeout queda desconocido hasta reconciliar; nunca se reenvía a ciegas</p></div><span className="demo-action">Simulación SII</span></div>{submissions.map(item => <article key={item.envelope}><span className="document-code"><Send size={16}/></span><div><strong>{item.envelope}</strong><p>{item.documents} · {item.sent}</p></div><div><small>Track ID</small><b>{item.track}</b></div><em className={`received-status ${item.tone}`}>{item.state}</em><Link aria-label={`Abrir ${item.envelope}`} href="/documentos"><ArrowRight size={17}/></Link></article>)}</section>
  </div>;
}
