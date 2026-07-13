import Link from "next/link";
import {
  ArrowRight, BadgeCheck, Boxes, Building2, Check, FileCheck2,
  FileText, Landmark, LockKeyhole, ReceiptText, RefreshCcw,
  ShieldCheck, Sparkles, TrendingUp, WalletCards,
} from "lucide-react";
import "./landing.css";

const capabilities = [
  { icon: ReceiptText, title: "Emisión tributaria", text: "Boletas, facturas, guías y notas conectadas por una historia que no se borra." },
  { icon: FileCheck2, title: "Compras y recibidos", text: "XML, aceptación o reclamo, proveedores y diferencias del RCV en una sola bandeja." },
  { icon: WalletCards, title: "Caja explicada", text: "Cobros, pagos parciales, vencimientos y conciliación sin confundir proyección con saldo bancario." },
  { icon: Boxes, title: "Operación comercial", text: "Cotizaciones, órdenes, inventario y aprobaciones antes de que exista un documento tributario." },
  { icon: Landmark, title: "Cierre mensual", text: "F29 explicado, RCV, honorarios y alertas de evidencia pendiente antes de cerrar el período." },
  { icon: Building2, title: "Carpeta del contador", text: "Un expediente mensual versionado con reportes, respaldos y trazabilidad para revisar más rápido." },
] as const;

export default function LandingPage() {
  return <main className="fiscal-landing">
    <nav className="landing-nav" aria-label="Navegación principal">
      <Link href="/" className="landing-brand" aria-label="Completo Fiscal, inicio">
        <span><ReceiptText size={20} /></span><strong>Completo <em>Fiscal</em></strong>
      </Link>
      <div><a href="#producto">Producto</a><a href="#seguridad">Confianza</a><Link className="landing-nav-cta" href="/dashboard">Abrir sandbox <ArrowRight size={15} /></Link></div>
    </nav>

    <section className="landing-hero">
      <div className="landing-hero-copy">
        <span className="landing-pill"><Sparkles size={14} /> Fiscalidad clara para pymes chilenas</span>
        <h1>Tu negocio al día.<br/><span>Tu contador, tranquilo.</span></h1>
        <p>Emite, ordena compras, proyecta caja y prepara el cierre mensual desde un solo lugar. Completo transforma la operación tributaria en decisiones que cualquier dueño puede entender.</p>
        <div className="landing-actions"><Link className="landing-primary" href="/dashboard">Explorar sandbox <ArrowRight size={18} /></Link><a className="landing-secondary" href="#producto">Ver qué resuelve</a></div>
        <small><BadgeCheck size={15} /> Demo pública con datos sintéticos. No emite ni presenta documentos reales.</small>
      </div>
      <div className="landing-product-frame" aria-label="Vista previa del dashboard de Completo Fiscal">
        <div className="landing-frame-bar"><span><i/><i/><i/></span><b>Empresa Sintética</b><em>Ambiente demo</em></div>
        <div className="landing-preview">
          <aside><span className="preview-logo"><ReceiptText size={16}/></span>{["Inicio","Emitir","Documentos","Recibidos","Cierre mensual"].map((item,index)=><i className={index===0?"active":""} key={item}>{item}</i>)}</aside>
          <div className="preview-main">
            <p>RESUMEN DE HOY</p><h2>Tu operación fiscal, al día.</h2>
            <div className="preview-metrics"><article><small>Ventas documentadas</small><strong>$1.278.940</strong><span><TrendingUp size={11}/> 12,4% sobre ayer</span></article><article><small>Documentos aceptados</small><strong>48</strong><span>de 49 enviados</span></article><article><small>Requieren atención</small><strong>1</strong><span>Resolver ahora →</span></article></div>
            <div className="preview-bottom"><article><small>ÚLTIMOS 14 DÍAS</small><b>$8.935.720</b><div className="preview-bars">{[35,52,44,67,58,76,62,88,55,72,82,64,92,79].map((height,index)=><i key={index} style={{height:`${height}%`}} />)}</div></article><article><small>CONTINUIDAD</small><b>Salud fiscal</b>{["Certificado digital","CAF disponibles","Comunicación SII"].map(item=><span key={item}><Check size={11}/>{item}</span>)}</article></div>
          </div>
        </div>
      </div>
    </section>

    <section className="landing-trust-strip"><p>No reemplaza al SII.</p><strong>Lo vuelve operable.</strong><span>Una fuente de verdad · Sin XML manual · Sin borrar historia</span></section>

    <section className="landing-capabilities" id="producto">
      <header><p className="landing-kicker">UNA OPERACIÓN, NO SEIS PLANILLAS</p><h2>Desde la venta hasta el cierre mensual.</h2><span>El lenguaje simple va primero. El XML, los códigos y el diagnóstico siguen disponibles cuando un especialista los necesita.</span></header>
      <div>{capabilities.map(({icon:Icon,title,text})=><article key={title}><span><Icon size={21}/></span><h3>{title}</h3><p>{text}</p></article>)}</div>
    </section>

    <section className="landing-flow">
      <div><p className="landing-kicker">UNA HISTORIA COMPLETA</p><h2>Cada cifra conserva su explicación.</h2><p>La venta, el documento, la respuesta del SII, el pago y el cierre permanecen relacionados. Si algo falla después de enviar, Completo consulta antes de repetir.</p><ul><li><Check/> Folios únicos y emisión idempotente</li><li><Check/> Documentos, sobres e intentos separados</li><li><Check/> Correcciones sin reescribir el original</li></ul></div>
      <ol><li><span>01</span><div><b>Ocurre la operación</b><p>Venta, compra, traslado o corrección.</p></div></li><li><span>02</span><div><b>Completo valida</b><p>Datos, montos, permisos y continuidad.</p></div></li><li><span>03</span><div><b>El SII responde</b><p>Estado trazado, incluso ante resultados ambiguos.</p></div></li><li><span>04</span><div><b>El mes queda explicado</b><p>Reportes y expediente listos para revisión.</p></div></li></ol>
    </section>

    <section className="landing-security" id="seguridad">
      <div><span><LockKeyhole size={25}/></span><p className="landing-kicker">DISEÑADO PARA INFORMACIÓN SENSIBLE</p><h2>Separado por empresa. Auditable por diseño.</h2></div>
      <div><article><ShieldCheck/><b>Secretos fuera del navegador</b><p>Certificados, contraseñas y CAF viven únicamente en servicios privados.</p></article><article><RefreshCcw/><b>Historia inmutable</b><p>Los documentos se corrigen con referencias; nunca desaparecen silenciosamente.</p></article><article><FileText/><b>Evidencia verificable</b><p>XML, PDF, eventos y paquetes conservan hashes y versiones para revisión.</p></article></div>
    </section>

    <section className="landing-demo">
      <div><p className="landing-kicker">MÍRALO FUNCIONAR</p><h2>Entra como dueño de una pyme.</h2><p>Recorre emisión, compras, caja, inventario, certificación y cierre mensual con una empresa ficticia. Nada de lo que hagas llegará al SII.</p></div>
      <Link className="landing-primary" href="/dashboard">Entrar al sandbox público <ArrowRight size={18}/></Link>
    </section>

    <footer className="landing-footer"><Link href="/" className="landing-brand"><span><ReceiptText size={18}/></span><strong>Completo <em>Fiscal</em></strong></Link><p>Producto en etapa pre-certificación · Chile · 2026</p><Link href="/dashboard">Sandbox público →</Link></footer>
  </main>;
}
