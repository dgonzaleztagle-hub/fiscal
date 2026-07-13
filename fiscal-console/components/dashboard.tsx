import Link from "next/link";
import { AlertTriangle, ArrowRight, Calculator, CheckCircle2, Clock3, FileArchive, FilePlus2, Landmark, RefreshCw, Scale, TrendingUp } from "lucide-react";
import { clp } from "@/lib/format";
import { DocumentTable } from "./document-table";

const bars = [46, 61, 54, 76, 68, 84, 72, 93, 63, 78, 88, 70, 97, 82];

export function Dashboard() {
  return (
    <div className="page dashboard-page">
      <header className="page-header"><div><p className="eyebrow">Jueves, 9 de julio</p><h1>Tu operación fiscal, al día.</h1><p>Revisa lo importante y resuelve excepciones sin navegar por tecnicismos.</p></div><Link className="primary-button" href="/emitir"><FilePlus2 size={18} /> Emitir documento</Link></header>
      <section className="metrics" aria-label="Resumen de hoy">
        <article><span className="metric-icon mint"><Landmark size={19} /></span><p>Ventas de hoy</p><strong>{clp(1278940)}</strong><small className="positive"><TrendingUp size={13} /> 12,4% sobre ayer</small></article>
        <article><span className="metric-icon blue"><CheckCircle2 size={19} /></span><p>Documentos aceptados</p><strong>48</strong><small>de 49 enviados hoy</small></article>
        <article><span className="metric-icon amber"><Clock3 size={19} /></span><p>En proceso SII</p><strong>1</strong><small>Última consulta hace 2 min</small></article>
        <article className="attention-card"><span className="metric-icon coral"><AlertTriangle size={19} /></span><p>Requieren atención</p><strong>1</strong><Link href="/envios">Resolver ahora <ArrowRight size={13} /></Link></article>
      </section>
      <section className="panel accountant-path" aria-label="Recorrido recomendado para contador"><div><p className="eyebrow">Revisión profesional · Julio 2026</p><h2>Recorrido preparado para tu contador</h2><p>Cuatro vistas conectadas para validar origen, cálculo y evidencia sin recorrer toda la operación.</p></div><nav><Link href="/rcv"><span>1</span><Scale size={17}/><b>RCV</b><small>Contrastar registros</small></Link><Link href="/f29"><span>2</span><Calculator size={17}/><b>F29 explicado</b><small>Revisar composición</small></Link><Link href="/cierre"><span>3</span><CheckCircle2 size={17}/><b>Cierre</b><small>Detectar pendientes</small></Link><Link href="/expediente"><span>4</span><FileArchive size={17}/><b>Expediente</b><small>Ver evidencia</small></Link></nav></section>
      <div className="dashboard-grid">
        <section className="panel sales-panel"><div className="panel-heading"><div><p className="eyebrow">Últimos 14 días</p><h2>Ventas documentadas</h2></div><button className="quiet-button" type="button">Ver detalle</button></div><div className="sales-total"><strong>{clp(8935720)}</strong><span>+8,2% vs. período anterior</span></div><div className="bar-chart" aria-label="Gráfico de ventas de 14 días">{bars.map((height, index) => <span key={index} style={{ height: `${height}%` }} className={index === bars.length - 1 ? "current" : ""} />)}</div><div className="chart-axis"><span>26 jun</span><span>30 jun</span><span>4 jul</span><span>Hoy</span></div></section>
        <section className="panel health-panel"><div className="panel-heading"><div><p className="eyebrow">Continuidad</p><h2>Salud fiscal</h2></div><span className="health-ok"><CheckCircle2 size={14} /> Operativa</span></div><div className="health-row"><span className="health-symbol certificate">✓</span><div><strong>Certificado digital</strong><p>Vigente hasta 9 jul 2027</p></div><small>365 días</small></div><div className="health-row"><span className="health-symbol caf">#</span><div><strong>CAF boletas</strong><p>Rangos activos 39 y 41</p></div><small>742 folios</small></div><div className="health-row"><span className="health-symbol sync"><RefreshCw size={15} /></span><div><strong>Comunicación SII</strong><p>Servicios respondiendo</p></div><small>Hace 2 min</small></div><Link href="/folios" className="panel-link">Administrar continuidad <ArrowRight size={14} /></Link></section>
      </div>
      <section className="panel documents-panel"><div className="panel-heading"><div><p className="eyebrow">Actividad reciente</p><h2>Últimos documentos</h2></div><Link className="quiet-button" href="/documentos">Ver todos <ArrowRight size={14} /></Link></div><DocumentTable limit={5} /></section>
    </div>
  );
}
