"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Info, MapPin, PackageCheck, ShieldCheck, Truck } from "lucide-react";

type Reason = "sale" | "pending" | "internal" | "return" | "consignment";

const reasons: Record<Reason, { code: number; label: string; valued: boolean }> = {
  sale: { code: 1, label: "Venta ya realizada", valued: true },
  pending: { code: 2, label: "Venta por efectuar", valued: true },
  consignment: { code: 3, label: "Consignación", valued: true },
  internal: { code: 5, label: "Traslado entre bodegas propias", valued: false },
  return: { code: 7, label: "Devolución", valued: true },
};

export function DispatchWizard() {
  const [reason, setReason] = useState<Reason>("sale");
  const [account, setAccount] = useState("2");
  const [receiver, setReceiver] = useState("CLIENTE SINTÉTICO SPA");
  const [rut, setRut] = useState("11.111.111-1");
  const [destination, setDestination] = useState("Bodega Central 200");
  const [commune, setCommune] = useState("Providencia");
  const [plate, setPlate] = useState("ABCD12");
  const [quantity, setQuantity] = useState(2);
  const [price, setPrice] = useState(10000);
  const [validated, setValidated] = useState(false);
  const selected = reasons[reason];
  const net = useMemo(() => selected.valued ? Math.max(0, quantity * price) : 0, [selected, quantity, price]);
  const vat = Math.round(net * .19);
  const reset = () => setValidated(false);

  return <div className="page section-page wizard-page">
    <Link href="/emitir" className="back-link"><ArrowLeft size={15} /> Volver a tipos de documento</Link>
    <header className="page-header"><div><p className="eyebrow">Emisión guiada · Guía 52</p><h1>Respaldar un traslado</h1><p>Describe por qué se mueven los bienes. Completo adapta los campos y evita valorizaciones contradictorias.</p></div><span className="demo-action">Ensayo sin folios</span></header>
    <div className="wizard-grid">
      <form className="panel wizard-form" onSubmit={(event) => { event.preventDefault(); setValidated(true); }}>
        <div className="form-heading"><div><span>1</span><div><strong>Motivo y destino</strong><p>El motivo define si la guía lleva montos o sólo cantidades.</p></div></div></div>
        <label>¿Por qué se trasladan los bienes?<select value={reason} onChange={(event) => { const value = event.target.value as Reason; setReason(value); if (value === "internal") { setReceiver("SOFTWARE SINTÉTICO SPA"); setRut("12.345.678-5"); } reset(); }}>{Object.entries(reasons).map(([key, value]) => <option value={key} key={key}>{value.label}</option>)}</select></label>
        {reason !== "internal" && <label>Despacho por cuenta de<select value={account} onChange={(event) => { setAccount(event.target.value); reset(); }}><option value="1">Receptor</option><option value="2">Emisor hacia el receptor</option><option value="3">Emisor hacia otro destino</option></select></label>}
        <div className="field-pair"><label>RUT receptor<input value={rut} required onChange={(event) => { setRut(event.target.value); reset(); }} /></label><label>Razón social<input value={receiver} required maxLength={100} onChange={(event) => { setReceiver(event.target.value); reset(); }} /></label></div>
        <div className="field-pair"><label>Dirección de destino<input value={destination} maxLength={70} onChange={(event) => { setDestination(event.target.value); reset(); }} /></label><label>Comuna de destino<input value={commune} maxLength={20} onChange={(event) => { setCommune(event.target.value); reset(); }} /></label></div>
        <div className="field-pair"><label>Patente del vehículo<input value={plate} maxLength={8} onChange={(event) => { setPlate(event.target.value.toUpperCase()); reset(); }} /></label><label>Cantidad de unidades<input type="number" min="0.001" step="0.001" value={quantity} onChange={(event) => { setQuantity(Number(event.target.value)); reset(); }} /></label></div>
        {selected.valued && <label>Precio neto unitario<input type="number" min="0" step="1" value={price} onChange={(event) => { setPrice(Number(event.target.value)); reset(); }} /></label>}
        <div className="form-notice"><Info size={17} /><p>{selected.valued ? "Esta guía queda valorizada: informará neto, IVA y total." : "El traslado interno conserva cantidades, omite el precio y lleva total cero. El receptor debe ser el mismo emisor."}</p></div>
        <button className="primary-button" type="submit">Validar borrador</button>
      </form>
      <aside className="panel tax-preview"><p className="eyebrow">Resultado del traslado</p><div className="document-preview"><span>52</span><div><strong>Guía de despacho electrónica</strong><p>Motivo SII {selected.code} · {selected.label}</p></div></div><div className="receiver-preview"><MapPin size={17} /><div><strong>{destination || "Destino pendiente"}</strong><p>{commune || "Comuna pendiente"}</p><small>{receiver} · {rut}</small></div></div><div className="receiver-preview"><Truck size={17} /><div><strong>{plate || "Sin patente"}</strong><p>{reason === "internal" ? "TipoDespacho no aplica" : `Responsable del despacho: ${account}`}</p></div></div><dl><div><dt>Neto</dt><dd>{money(net)}</dd></div><div><dt>IVA 19%</dt><dd>{money(vat)}</dd></div><div className="total-row"><dt>Total</dt><dd>{money(net + vat)}</dd></div></dl>{validated ? <div className="validation-success"><CheckCircle2 size={18} /><div><strong>Guía coherente</strong><p>Builder 52, TED, firma y sobre EnvioDTE están activos. En demo no se consume CAF.</p></div></div> : <div className="preview-guard"><ShieldCheck size={17} /> Nada se emitirá desde esta pantalla.</div>}<div className="form-notice"><PackageCheck size={16} /><p>Los nuevos campos de carro y horarios permanecen bloqueados hasta que el SII publique un XSD compatible.</p></div></aside>
    </div>
  </div>;
}

function money(value: number) {
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(value || 0);
}
