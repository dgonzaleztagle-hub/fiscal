"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, Building2, CheckCircle2, Info, ShieldCheck } from "lucide-react";

export function InvoiceWizard() {
  const [receiver, setReceiver] = useState("CLIENTE SINTÉTICO SPA");
  const [rut, setRut] = useState("11.111.111-1");
  const [activity, setActivity] = useState("Servicios empresariales");
  const [address, setAddress] = useState("Av. Providencia 1234");
  const [commune, setCommune] = useState("Providencia");
  const [email, setEmail] = useState("facturas@cliente.demo");
  const [name, setName] = useState("Servicio mensual");
  const [quantity, setQuantity] = useState(1);
  const [netPrice, setNetPrice] = useState(10000);
  const [exempt, setExempt] = useState(false);
  const [credit, setCredit] = useState(false);
  const [validated, setValidated] = useState(false);
  const net = useMemo(() => Math.max(0, quantity * netPrice), [quantity, netPrice]);
  const vat = exempt ? 0 : Math.round(net * 0.19);
  const type = exempt ? 34 : 33;

  const resetValidation = () => setValidated(false);
  return <div className="page section-page wizard-page">
    <Link href="/emitir" className="back-link"><ArrowLeft size={15} /> Volver a tipos de documento</Link>
    <header className="page-header"><div><p className="eyebrow">Emisión guiada · Facturas 33/34</p><h1>Facturar a una empresa</h1><p>El receptor, los precios netos y la forma de pago se validan antes de reservar un folio.</p></div><span className="demo-action">Ensayo sin folios</span></header>
    <div className="wizard-grid">
      <form className="panel wizard-form" onSubmit={(event) => { event.preventDefault(); setValidated(true); }}>
        <div className="form-heading"><div><span>1</span><div><strong>Receptor y detalle</strong><p>Los datos obligatorios evitan una factura incompleta.</p></div></div></div>
        <div className="field-pair"><label>RUT receptor<input value={rut} required onChange={(event) => { setRut(event.target.value); resetValidation(); }} /></label><label>Razón social<input value={receiver} maxLength={100} required onChange={(event) => { setReceiver(event.target.value); resetValidation(); }} /></label></div>
        <label>Giro del receptor<input value={activity} maxLength={40} required onChange={(event) => { setActivity(event.target.value); resetValidation(); }} /></label>
        <div className="field-pair"><label>Dirección<input value={address} maxLength={70} required onChange={(event) => { setAddress(event.target.value); resetValidation(); }} /></label><label>Comuna<input value={commune} maxLength={20} required onChange={(event) => { setCommune(event.target.value); resetValidation(); }} /></label></div>
        <label>Correo de intercambio<input type="email" value={email} maxLength={80} required onChange={(event) => { setEmail(event.target.value); resetValidation(); }} /></label>
        <label>Producto o servicio<input value={name} maxLength={80} required onChange={(event) => { setName(event.target.value); resetValidation(); }} /></label>
        <div className="field-pair"><label>Cantidad<input type="number" min="0.001" step="0.001" value={quantity} required onChange={(event) => { setQuantity(Number(event.target.value)); resetValidation(); }} /></label><label>Precio neto unitario<input type="number" min="0" step="1" value={netPrice} required onChange={(event) => { setNetPrice(Number(event.target.value)); resetValidation(); }} /></label></div>
        <div className="field-pair"><label>Tributación<select value={exempt ? "exempt" : "affected"} onChange={(event) => { setExempt(event.target.value === "exempt"); resetValidation(); }}><option value="affected">Afecto a IVA</option><option value="exempt">Exento de IVA</option></select></label><label>Condición de pago<select value={credit ? "credit" : "cash"} onChange={(event) => { setCredit(event.target.value === "credit"); resetValidation(); }}><option value="cash">Contado</option><option value="credit">Crédito</option></select></label></div>
        {credit && <label>Fecha de vencimiento<input type="date" defaultValue="2026-08-10" required onChange={resetValidation} /></label>}
        <div className="form-notice"><Info size={17} /><p>A diferencia de una boleta, aquí el precio afecto se ingresa neto. El IVA se calcula sobre el neto total y se redondea en pesos.</p></div>
        <button className="primary-button" type="submit">Validar borrador</button>
      </form>
      <aside className="panel tax-preview"><p className="eyebrow">Resultado tributario</p><div className="document-preview"><span>{type}</span><div><strong>{exempt ? "Factura exenta electrónica" : "Factura electrónica"}</strong><p>{credit ? "Venta a crédito · con vencimiento" : "Venta al contado"}</p></div></div><div className="receiver-preview"><Building2 size={17} /><div><strong>{receiver || "Receptor sin nombre"}</strong><p>{rut || "RUT pendiente"} · {commune || "Comuna pendiente"}</p><small>{email || "Correo pendiente"}</small></div></div><dl><div><dt>Neto</dt><dd>{formatCurrency(net)}</dd></div>{!exempt && <div><dt>IVA 19%</dt><dd>{formatCurrency(vat)}</dd></div>}<div className="total-row"><dt>Total</dt><dd>{formatCurrency(net + vat)}</dd></div></dl>{validated ? <div className="validation-success"><CheckCircle2 size={18} /><div><strong>Borrador coherente</strong><p>El motor 33/34, TED, firma, PDF e intercambio están activos. En demo no se consume CAF.</p></div></div> : <div className="preview-guard"><ShieldCheck size={17} /> Nada se emitirá desde esta pantalla.</div>}</aside>
    </div>
  </div>;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(value || 0);
}
