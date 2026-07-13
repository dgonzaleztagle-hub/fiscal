export const receivedDemo = [
  { id: "demo-33-7841", type: 33, folio: 7841, issuer: "DISTRIBUIDORA CENTRAL SPA", rut: "76.345.210-8", date: "10 jul 2026", total: "$428.400", status: "Por revisar", tone: "warning", net: "$360.000", vat: "$68.400" },
  { id: "demo-34-391", type: 34, folio: 391, issuer: "SERVICIOS FRÍO SUR LTDA.", rut: "77.120.934-2", date: "9 jul 2026", total: "$85.000", status: "Aceptado", tone: "success", net: "$85.000", vat: "$0" },
  { id: "demo-61-88", type: 61, folio: 88, issuer: "DISTRIBUIDORA CENTRAL SPA", rut: "76.345.210-8", date: "8 jul 2026", total: "$23.800", status: "Por asociar", tone: "neutral", net: "$20.000", vat: "$3.800" },
] as const;

export function receivedDemoById(id: string) { return receivedDemo.find(row => row.id === id) ?? receivedDemo[0]; }
