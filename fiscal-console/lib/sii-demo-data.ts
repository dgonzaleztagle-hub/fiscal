export const rcvDocuments = [
  { direction: "Compra", type: 33, party: "Distribuidora Central SpA", folio: "7.841", net: 360000, vat: 68400, total: 428400, match: "Coincide" },
  { direction: "Compra", type: 34, party: "Servicios Frío Sur Ltda.", folio: "391", net: 0, vat: 0, total: 85000, match: "Coincide" },
  { direction: "Compra", type: 33, party: "Comercial Demo SpA", folio: "992", net: 100000, vat: 19000, total: 119000, match: "Sólo en SII" },
  { direction: "Venta", type: 39, party: "Resumen boletas electrónicas", folio: "1–48", net: 1024361, vat: 194629, total: 1218990, match: "Coincide" },
];

export const f29Lines = [
  { code: "Cód. 538", label: "Débito fiscal por ventas", completo: 194629, sii: 194629 },
  { code: "Cód. 520", label: "Crédito fiscal por compras", completo: 68400, sii: 68400 },
  { code: "Cód. 151", label: "Retención honorarios", completo: 6863, sii: 6863 },
  { code: "Cód. 563", label: "PPM neto determinado", completo: 24400, sii: 24400 },
];

export const bheRows = [
  { direction: "Recibida", person: "Valentina Muñoz", folio: "184", date: "11 jul 2026", gross: 45000, retention: 6863, net: 38137, status: "Vigente" },
  { direction: "Emitida", person: "Cliente Servicios Demo", folio: "72", date: "4 jul 2026", gross: 120000, retention: 18300, net: 101700, status: "Vigente" },
];

export const syncRows = [
  { resource: "RCV compras y ventas", at: "11 jul · 08:18", result: "24 registros", version: "snapshot v3", tone: "success" },
  { resource: "Propuesta F29", at: "11 jul · 08:19", result: "4 códigos conciliados", version: "snapshot v2", tone: "success" },
  { resource: "BHE emitidas/recibidas", at: "11 jul · 08:20", result: "2 boletas", version: "snapshot v2", tone: "success" },
  { resource: "Estado F22", at: "10 jul · 17:05", result: "Sin observaciones", version: "snapshot v1", tone: "neutral" },
];
