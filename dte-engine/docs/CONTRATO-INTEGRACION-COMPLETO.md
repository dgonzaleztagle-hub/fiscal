# Contrato de integración con Completo

La venta se cobra primero y la boleta se emite en segundo plano. Completo no llama al SII
dentro de `create_pos_sale` ni de `settle_table`: en la misma transacción del cobro crea
una fila inmutable en una outbox fiscal. Un worker reclama esa fila y llama a este motor
con el UUID de la transacción como `Idempotency-Key`.

## Decisión de emisión

- Sin entitlement `facturacion`: no crear obligación fiscal.
- Tarjeta + `voucher_as_boleta`: registrar `not_required`, porque el voucher es el
  documento que corresponde bajo la configuración del tenant.
- Cualquier otro medio, o `always_boleta`: crear obligación tipo 39.
- La propina queda fuera del total tributario.
- Una venta sandbox jamás usa CAF productivo.

## Snapshot obligatorio

La outbox conserva tenant/RUT, sucursal, venta o cuenta de mesa, fecha, medio de pago,
modelo de emisión y cada línea con nombre, cantidad, precio bruto, indicador afecto/exento
y unidad. No se reconstruye desde el catálogo después: el producto puede cambiar.

## Estados

`pending -> processing -> issued -> submitted -> accepted`

Ramas controladas: `not_required`, `rejected`, `retryable_error` y `unknown`. `unknown`
exige reconciliación antes de reintentar. El XML y el Track ID son inmutables.

## Campos que Completo aún debe materializar

- perfil tributario del tenant (RUT, razón social, giro, código de actividad, dirección,
  comuna y resolución);
- clasificación tributaria y unidad de medida del producto;
- outbox + intentos + vínculo a documento/folio/Track ID;
- worker server-side con secreto por tenant;
- vista operacional para pendientes y rechazos.

El certificado, CAF y sus contraseñas permanecen en el motor/gestor de secretos, nunca en
Supabase legible por el navegador.
