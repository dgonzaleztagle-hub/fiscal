import { notFound } from "next/navigation";
import { PaymentProofUpload } from "@/components/payment-proof-upload";

type Portal = { counterparty_name: string; source_ref: string; amount: number; paid: number; outstanding: number; due_on: string; bank_name: string; account_type: string; account_number_masked: string; account_holder: string };

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const base = process.env.FISCAL_API_URL;
  if (!base) notFound();
  const response = await fetch(new URL(`/v1/public/collections/${encodeURIComponent(token)}`, base), { cache: "no-store" });
  if (!response.ok) notFound();
  const p = await response.json() as Portal;
  return <main className="public-quote">
    <header><span>Completo Fiscal</span><p>Portal seguro de cobro</p></header>
    <section className="panel">
      <p className="eyebrow">Cuenta pendiente</p><h1>{p.counterparty_name}</h1><p>{p.source_ref} · vence {p.due_on}</p>
      <div className="public-quote-total"><span>Saldo pendiente</span><strong>${p.outstanding.toLocaleString("es-CL")}</strong></div>
      <div className="bank-details"><strong>Datos para transferir</strong><p>{p.bank_name} · {p.account_type}</p><p>{p.account_number_masked} · {p.account_holder}</p></div>
      <PaymentProofUpload token={token} outstanding={p.outstanding} />
      <details className="public-help"><summary>¿Necesitas ayuda?</summary><p>Adjunta un PDF, JPG o PNG de hasta 5 MB. El comprobante queda pendiente de revisión: subirlo no marca automáticamente la cuenta como pagada.</p><strong>Completo no recibe, mueve ni custodia tu dinero.</strong></details>
    </section>
    <footer>Completo no recibe ni custodia el dinero</footer>
  </main>;
}
