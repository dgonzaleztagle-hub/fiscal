import { FlaskConical } from "lucide-react";

const environments = {
  demo: { label: "Ambiente demo", detail: "Datos sintéticos · Ningún documento será enviado al SII" },
  certification: { label: "Certificación SII", detail: "Documentos de prueba · Sin validez tributaria" },
  production: { label: "Producción", detail: "Operación tributaria real" },
} as const;

export function EnvironmentBanner() {
  const raw = process.env.NEXT_PUBLIC_FISCAL_ENVIRONMENT ?? "demo";
  const environment = raw in environments ? raw as keyof typeof environments : "demo";
  const current = environments[environment];
  return (
    <div className={`environment environment-${environment}`} role="status">
      <FlaskConical size={16} aria-hidden="true" />
      <strong>{current.label}</strong>
      <span>{current.detail}</span>
    </div>
  );
}
