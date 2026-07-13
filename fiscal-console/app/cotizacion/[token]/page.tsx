import { notFound } from "next/navigation";
import { PublicQuoteDecision } from "@/components/public-quote-decision";
import { fiscalPublicEngineUrl } from "@/lib/fiscal-runtime";

type Quote = { number: number; counterparty_name: string; issued_on: string; valid_until: string | null; currency: string; total: number; lines: Array<{ description: string; quantity: string; subtotal: number }> };

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const base = fiscalPublicEngineUrl();
  let quote: Quote;
  if (!base) {
    if (token !== "demo") notFound();
    quote = { number: 18, counterparty_name: "CLIENTE DEMOSTRACIÓN SPA", issued_on: "2026-07-13", valid_until: "2026-07-28", currency: "CLP", total: 475000, lines: [{ description: "Servicio mensual Completo Fiscal", quantity: "1", subtotal: 475000 }] };
  } else {
    const response = await fetch(new URL(`/v1/public/commercial/${encodeURIComponent(token)}`, base), { cache: "no-store" });
    if (!response.ok) notFound();
    quote = await response.json() as Quote;
  }
  return <main className="public-quote">
    <header><span>Completo Fiscal</span><p>Cotización #{quote.number}</p></header>
    <section className="panel">
      <p className="eyebrow">Propuesta comercial</p><h1>{quote.counterparty_name}</h1>
      <small>Emitida {quote.issued_on} · válida hasta {quote.valid_until ?? "sin fecha"}</small>
      <div className="public-quote-lines">{quote.lines.map((line, index) => <article key={index}><div><strong>{line.description}</strong><p>Cantidad {line.quantity}</p></div><b>${line.subtotal.toLocaleString("es-CL")}</b></article>)}</div>
      <div className="public-quote-total"><span>Total</span><strong>${quote.total.toLocaleString("es-CL")}</strong></div>
      <PublicQuoteDecision token={token} />
      <details className="public-help"><summary>¿Necesitas ayuda?</summary><p>Puedes aceptar o rechazar esta propuesta una sola vez. Si necesitas cambiar productos, montos o fechas, contacta a quien la emitió antes de decidir.</p><strong>Esta cotización no es una boleta ni factura y no consume folio SII.</strong></details>
    </section>
    <footer>Enlace seguro de un solo uso · no es un documento tributario</footer>
  </main>;
}
