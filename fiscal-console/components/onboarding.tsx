import { CheckCircle2, Circle, KeyRound, ShieldCheck, Users } from "lucide-react";

const checklist = [
  ["Organización y administrador", "Datos básicos y acceso principal", true, "Cliente"],
  ["Perfil tributario", "RUT, razón social, giro y actividades", true, "Cliente"],
  ["Representación ante el SII", "Usuarios autorizados y elegibilidad", false, "Acompañado"],
  ["Certificado digital", "Carga privada directamente al vault", false, "Acompañado"],
  ["Sucursales fiscales", "Direcciones y códigos SII", false, "Cliente"],
  ["Consulta pública HTTPS", "Portal verificable antes de certificar", false, "Completo"],
  ["CAF y certificación", "Proceso propio de cada contribuyente", false, "Acompañado"],
] as const;

export function Onboarding() {
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">Activación modular</p><h1>Onboarding de Completo Fiscal</h1><p>Solicitamos sólo lo necesario para los módulos contratados. POS no es requisito para usar Fiscal.</p></div><span className="demo-action">Tenant sintético</span></header><div className="onboarding-grid"><section className="panel onboarding-checklist"><div className="onboarding-progress"><div><strong>2 de 7 pasos preparados</strong><p>La certificación se acompaña personalmente.</p></div><span>29%</span></div><div className="completion"><span style={{ width: "29%" }} /></div>{checklist.map(([title, detail, done, owner]) => <article className="onboarding-row" key={title}>{done ? <CheckCircle2 className="done" size={19} /> : <Circle size={19} />}<div><strong>{title}</strong><p>{detail}</p></div><small>{owner}</small></article>)}</section><aside className="panel onboarding-safety"><ShieldCheck size={27} /><p className="eyebrow">Datos sensibles</p><h2>El navegador nunca recibe secretos</h2><p>Certificados, contraseñas y claves CAF se cargan mediante un canal privado al backend y permanecen fuera de Supabase público.</p><div><KeyRound size={17} /><span><strong>Certificado</strong><small>Pendiente · no comprado</small></span></div><div><Users size={17} /><span><strong>Acompañamiento</strong><small>Contacto personal antes del SII</small></span></div><button className="secondary-button" disabled>Disponible al configurar vault</button></aside></div></div>;
}
