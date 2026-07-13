"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, CheckCircle2, Info, ShieldCheck } from "lucide-react";

export function BoletaWizard() {
  const [name, setName] = useState("Menú del día");
  const [quantity, setQuantity] = useState(1);
  const [price, setPrice] = useState(12990);
  const [exempt, setExempt] = useState(false);
  const [validated, setValidated] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [issued, setIssued] = useState<{ id: string; folio: string } | null>(null);
  const [error, setError] = useState("");
  const draftLoaded = useRef(false);
  const idempotencyKey = useRef<string | null>(null);
  useEffect(() => {
    const stored = window.sessionStorage.getItem("completo-fiscal:boleta-draft");
    if (stored) {
      try {
        const draft = JSON.parse(stored);
        Promise.resolve().then(() => {
          setName(draft.name ?? "Menú del día");
          setQuantity(draft.quantity ?? 1);
          setPrice(draft.price ?? 12990);
          setExempt(draft.exempt ?? false);
        });
      } catch { window.sessionStorage.removeItem("completo-fiscal:boleta-draft"); }
    }
    draftLoaded.current = true;
  }, []);
  useEffect(() => {
    if (!draftLoaded.current) return;
    window.sessionStorage.setItem(
      "completo-fiscal:boleta-draft", JSON.stringify({ name, quantity, price, exempt })
    );
  }, [name, quantity, price, exempt]);
  const total = useMemo(() => Math.max(0, quantity * price), [quantity, price]);
  const type = exempt ? 41 : 39;

  async function issueInSandbox() {
    setIssuing(true); setError("");
    try {
      idempotencyKey.current ??= crypto.randomUUID();
      const response = await fetch("/api/demo/fiscal-documents", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey.current }, body: JSON.stringify({ documentType: type, receiver: "Consumidor final", itemName: name, quantity, unitPrice: price }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "No fue posible emitir");
      setIssued({ id: payload.id, folio: payload.folio });
      window.sessionStorage.removeItem("completo-fiscal:boleta-draft");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "No fue posible emitir"); }
    finally { setIssuing(false); }
  }

  return <div className="page section-page wizard-page">
    <Link href="/emitir" className="back-link"><ArrowLeft size={15} /> Volver a tipos de documento</Link>
    <header className="page-header"><div><p className="eyebrow">Emisión guiada · Paso 1 de 3</p><h1>Registrar una venta</h1><p>Completo elegirá la boleta correcta según la tributación de cada producto.</p></div><span className="demo-action">Ensayo sin folios</span></header>
    <div className="wizard-grid">
      <form className="panel wizard-form" onSubmit={(event) => { event.preventDefault(); setValidated(true); }}>
        <div className="form-heading"><div><span>1</span><div><strong>Detalle de la venta</strong><p>Ingresa los valores tal como los vio el cliente.</p></div></div></div>
        <label>Producto o servicio<input value={name} maxLength={80} required onChange={(event) => { setName(event.target.value); setValidated(false); }} /></label>
        <div className="field-pair"><label>Cantidad<input type="number" min="0.001" step="0.001" value={quantity} required onChange={(event) => { setQuantity(Number(event.target.value)); setValidated(false); }} /></label><label>Precio final unitario<input type="number" min="0" step="1" value={price} required onChange={(event) => { setPrice(Number(event.target.value)); setValidated(false); }} /></label></div>
        <label className="tax-choice"><input type="checkbox" checked={exempt} onChange={(event) => { setExempt(event.target.checked); setValidated(false); }} /><span><strong>Este producto está exento de IVA</strong><small>Márcalo sólo si su clasificación tributaria fue configurada como exenta.</small></span></label>
        <div className="form-notice"><Info size={17} /><p>El precio se ingresa con impuestos incluidos. El motor calcula y redondea los montos tributarios.</p></div>
        <button className="primary-button" type="submit">Revisar antes de emitir</button>
        {validated && !issued && <button className="secondary-button" type="button" disabled={issuing} onClick={issueInSandbox}>{issuing ? "Procesando…" : "Emitir en sandbox"}</button>}
        {error && <p className="form-error">{error}</p>}
        {issued && <div className="validation-success" role="status"><CheckCircle2 size={18}/><div><strong>Boleta procesada por el backend</strong><p>Folio sintético {issued.folio} · respuesta aceptada por el simulador SII.</p><Link href={`/documentos/${issued.id}`}>Abrir documento →</Link></div></div>}
      </form>
      <aside className="panel tax-preview"><p className="eyebrow">Resultado tributario</p><div className="document-preview"><span>{type}</span><div><strong>{exempt ? "Boleta exenta electrónica" : "Boleta electrónica"}</strong><p>Se elegirá automáticamente al confirmar.</p></div></div><dl><div><dt>Ítem</dt><dd>{name || "Sin nombre"}</dd></div><div><dt>Subtotal</dt><dd>{formatCurrency(total)}</dd></div>{!exempt && <><div><dt>Neto incluido</dt><dd>{formatCurrency(Math.round(total / 1.19))}</dd></div><div><dt>IVA incluido</dt><dd>{formatCurrency(total - Math.round(total / 1.19))}</dd></div></>}<div className="total-row"><dt>Total</dt><dd>{formatCurrency(total)}</dd></div></dl>{validated ? <div className="validation-success"><CheckCircle2 size={18} /><div><strong>Borrador coherente</strong><p>El backend reservará un folio sintético, firmará la simulación y registrará sus eventos. Nunca se conecta al SII.</p></div></div> : <div className="preview-guard"><ShieldCheck size={17} /> Nada se emitirá desde esta pantalla.</div>}</aside>
    </div>
  </div>;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(value || 0);
}
