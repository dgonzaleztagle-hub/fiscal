export type FiscalStatus = "accepted" | "submitted" | "attention" | "draft";

export type DemoDocument = {
  id: string;
  kind: string;
  label: string;
  folio: string;
  receiver: string;
  amount: number;
  status: FiscalStatus;
  statusLabel: string;
  issuedAt: string;
};

export const demoDocuments: DemoDocument[] = [
  {
    id: "demo-39-1842",
    kind: "39",
    label: "Boleta electrónica",
    folio: "1.842",
    receiver: "Consumidor final",
    amount: 28650,
    status: "accepted",
    statusLabel: "Aceptada",
    issuedAt: "Hoy, 12:46",
  },
  {
    id: "demo-33-204",
    kind: "33",
    label: "Factura electrónica",
    folio: "204",
    receiver: "Arquitectura Norte SpA",
    amount: 475000,
    status: "accepted",
    statusLabel: "Aceptada",
    issuedAt: "Hoy, 11:18",
  },
  {
    id: "demo-39-1841",
    kind: "39",
    label: "Boleta electrónica",
    folio: "1.841",
    receiver: "Consumidor final",
    amount: 14990,
    status: "submitted",
    statusLabel: "En revisión SII",
    issuedAt: "Hoy, 10:54",
  },
  {
    id: "demo-61-42",
    kind: "61",
    label: "Nota de crédito",
    folio: "42",
    receiver: "Comercial La Plaza Ltda.",
    amount: 89250,
    status: "attention",
    statusLabel: "Requiere revisión",
    issuedAt: "Ayer, 17:32",
  },
  {
    id: "demo-52-18",
    kind: "52",
    label: "Guía de despacho",
    folio: "18",
    receiver: "Sucursal Providencia",
    amount: 0,
    status: "draft",
    statusLabel: "Borrador",
    issuedAt: "Ayer, 15:07",
  },
];

export const navigationSections = {
  emitir: {
    eyebrow: "Emisión guiada",
    title: "¿Qué documento necesitas emitir?",
    description: "Elige por intención. Completo Fiscal se encarga del tipo tributario y sus referencias.",
  },
  documentos: {
    eyebrow: "Ventas",
    title: "Documentos emitidos",
    description: "Boletas, facturas, notas y guías con su estado real ante el SII.",
  },
  recibidos: {
    eyebrow: "Compras",
    title: "Documentos recibidos",
    description: "Importa XML, revisa plazos y deja trazabilidad de aceptación o reclamo.",
  },
  clientes: {
    eyebrow: "Directorio",
    title: "Clientes",
    description: "Receptores frecuentes y antecedentes listos para facturar sin volver a escribirlos.",
  },
  proveedores: {
    eyebrow: "Directorio",
    title: "Proveedores",
    description: "Centraliza compras, documentos pendientes y diferencias por proveedor.",
  },
  productos: {
    eyebrow: "Catálogo tributario",
    title: "Productos y servicios",
    description: "Define afecto, exento, unidad y precio para emitir con reglas consistentes.",
  },
  folios: {
    eyebrow: "Continuidad operacional",
    title: "Folios y CAF",
    description: "Supervisa disponibilidad por documento sin exponer las claves privadas del CAF.",
  },
  envios: {
    eyebrow: "Comunicación SII",
    title: "Envíos y seguimiento",
    description: "Sobres, Track ID, reparos y resultados ambiguos en una sola línea de tiempo.",
  },
  reportes: {
    eyebrow: "Cierre mensual",
    title: "Reportes",
    description: "Ventas, compras, IVA, exentos y paquetes verificables para tu contador.",
  },
  rcv: {
    eyebrow: "Snapshot SII",
    title: "Registro de compras y ventas",
    description: "Contrasta lo que informa el SII con los XML y operaciones preservadas por Completo.",
  },
  f29: {
    eyebrow: "Declaración mensual",
    title: "Propuesta F29",
    description: "Entiende débito, crédito y retenciones antes de revisar la declaración en el SII.",
  },
  bhe: {
    eyebrow: "Honorarios y retenciones",
    title: "Boletas de honorarios",
    description: "Consulta emitidas y recibidas, con retenciones conciliadas por período.",
  },
  situacion: {
    eyebrow: "Perfil del contribuyente",
    title: "Situación tributaria",
    description: "Actividades, régimen, declaraciones y señales administrativas consultadas al SII.",
  },
  sincronizaciones: {
    eyebrow: "Operación del conector",
    title: "Sincronizaciones SII",
    description: "Historial de lecturas, snapshots y cambios detectados sin mezclarlo con la emisión DTE.",
  },
  certificacion: {
    eyebrow: "Cockpit controlado",
    title: "Certificación SII",
    description: "Ensaya cada paso antes de descargar folios reales o iniciar una ventana oficial.",
  },
  configuracion: {
    eyebrow: "Administración",
    title: "Configuración fiscal",
    description: "Emisor, sucursales, certificado, resolución y accesos de tu organización.",
  },
} as const;

export type NavigationSection = keyof typeof navigationSections;
