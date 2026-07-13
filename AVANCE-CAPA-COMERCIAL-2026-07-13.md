# Avance capa comercial — 13 de julio de 2026

## Cerrado

- Dominio separado para cotizaciones, órdenes de venta y órdenes de compra.
- Persistencia SQLite tenant-first, numerada e idempotente.
- Máquina de estados y conversión explícita hacia documento fiscal.
- API versionada y contrato TypeScript regenerado desde OpenAPI.
- Inventario append-only por producto, sucursal y movimiento.
- Esquema PostgreSQL privado inicial para documentos comerciales.
- Consola navegable para ventas, compras, inventario y caja proyectada.
- Menú móvil completo mediante “Más secciones”.
- Cuentas por cobrar/pagar, pagos parciales, proyección y aprobaciones por rol.
- Flujos UI para crear cotización/orden, movimiento, obligación, pago e importar
  una cartola CSV en modo previo a conexión.
- Cotización pública con enlace de un solo uso, vencimiento y decisión trazada.
- Acuerdos recurrentes mensuales y worker idempotente que crea borradores
  revisables sin emitir DTE ni consumir folio.
- Portal público de cobro con datos bancarios, saldo, comprobante hasheado y
  revisión obligatoria antes de marcar un pago.
- Conversión idempotente de cotización aceptada a orden de venta.
- Mínimos reales y traslados de inventario pareados y atómicos.

## Verificación

- Motor completo: 244 pruebas aprobadas.
- Nuevos ledgers: idempotencia, aislamiento tenant y transiciones cubiertas.
- Consola: TypeScript, ESLint y build aprobados.
- Policía final: 48/48 recorridos aprobados en desktop y móvil. Detectó y se
  corrigió el menú móvil inicial y el solapamiento táctil de aprobaciones.
- Centro de ayuda alineado con los flujos nuevos, detalles documentales y
  portales públicos; una prueba impide que vuelvan a caer en ayuda genérica.

## Pendientes reales de la ampliación V1

- Zavu para correo/WhatsApp, documentado como integración externa pendiente.
- OCR con OpenAI, documentado como integración externa pendiente.
- Object storage/vault para comprobantes en PostgreSQL productivo; localmente
  se prueba contenido limitado y hasheado.
- Entitlements, SSO y multiempresa desde el control plane de Completo.
- Conversión final orden → guía/DTE requiere seleccionar el perfil emisor real;
  permanece bloqueada hasta conectar tenant, CAF y certificado.
- Política medible de uso razonable para API/OCR, sin cupos visibles.

Ninguno de estos puntos se considerará terminado por existir sólo una pantalla.
