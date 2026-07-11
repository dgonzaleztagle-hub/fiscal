# Comparación previa a certificación — motor DTE, LibreDTE y Completo

> Auditoría posterior y correcciones adicionales: véase
> `AUDIT-CRUZADA-LIBREDTE-2026-07-09-SOL.md`.

**Fecha:** 2026-07-09  
**LibreDTE revisado:** `LibreDTE/libredte-lib-core` commit
`55d4718ba625e0f00ba7cc995837da5f7869ea4c`  
**Regla:** referencia arquitectónica y de casos límite; no se copia ni integra código AGPL.

## Veredicto actualizado

El motor propio ya cubre correctamente el núcleo de una boleta 39: modelo, totales,
CAF/TED, firma del documento, sobre, folios transaccionales, idempotencia y aislamiento
por tenant. No necesita rediseño.

RCOF/RVD, autenticación SII, envío, Track ID, consulta de estado y ledger de intentos ya
están implementados. LibreDTE confirma esas fronteras y aporta casos de prueba, pero no
cambia la arquitectura elegida. Los bloqueantes restantes son representación/consulta
pública, envío automático del RCOF, integración outbox en Completo y prueba con credencial
real.

## Matriz de responsabilidades

| Responsabilidad | Motor propio | LibreDTE observado | Acción |
|---|---|---|---|
| Boleta afecta 39 | Implementada | Builder + normalizador + validador separados | Mantener diseño propio |
| Cinco casos SII | 5/5 como regresión | Fixtures amplios por documento | Añadir casos límite después del set |
| Neto/IVA/exento | Implementado con precios brutos | Normalización dedicada | Añadir descuentos/recargos cuando corresponda |
| Referencia SET | Implementada | Referencias genéricas | Suficiente para certificación |
| Unidad de medida | Implementada | Detalle genérico | Suficiente para certificación |
| CAF y TED | Validación FRMA, rango, RUT y tipo | CAF manager + timbraje | Motor propio es más estricto en confianza |
| Folios | Ledger transaccional e idempotente | Manager en memoria/lote | Mantener ledger propio |
| XMLDSig | Documento y sobre | Documento y sobre | Añadir cadena/revocación del certificado |
| XSD | Oficial localizado; anomalía documentada | Schemas empaquetados | Implementar compatibilidad explícita |
| EnvioBOLETA | Construido y firmado | Sobre validado y despachado | Persistir sobre e intentos |
| RCOF/RVD | Implementado, firmado y validado con XSD oficial | `ConsumoFolios`, rangos continuos y firma | Alineado |
| Semilla/token | API REST oficial + cache 55 min | Autenticador separado y token cacheado | Alineado |
| Upload | Multipart REST de boletas + ledger inmutable | Transporte separado del builder | Propio y más conservador |
| Track ID/estado | Persistencia, consulta y clasificación fail-safe | Estados tipados | Alineado; código desconocido queda `unknown` |
| Ticket/PDF417 | No implementado | Renderers separados | Necesario antes del V°B° |

## Segunda pasada: hallazgos aplicados

- LibreDTE separa normalización del documento y representación. Mantendremos el XML como
  fuente inmutable y el ticket como una proyección reemplazable.
- Su renderer genera PDF417 desde el TED aplanado. Nuestro renderer deberá usar exactamente
  el TED firmado ya persistido, nunca reconstruirlo desde la venta.
- Su mapeo distingue aceptado, reparo, rechazo y en proceso. Se incorporó esa reducción al
  gateway propio, pero cualquier código nuevo queda `unknown` y exige revisión.
- El upload observado reintenta ciertos fallos de transporte. Nuestro ledger conserva una
  regla más estricta: si pudo haberse recibido el cuerpo, no se reenvía hasta reconciliar.
- El SII vigente exige representación legible, timbre PDF417 y una consulta pública. Éstos
  ya están implementados; el PDF417 se decodifica en tests con una biblioteca independiente.
- Completo conserva una ventaja propia que no depende de LibreDTE: folios, documentos,
  sobres e intentos viven en ledger transaccional; XML/eventos están protegidos contra
  edición y las migraciones aplicadas quedan fijadas por hash.
- La integración restaurante mantiene la caja desacoplada: venta y outbox son atómicas,
  mientras que firma/envío ocurren fuera de la transacción operacional.

## Hallazgos concretos de LibreDTE que debemos incorporar como pruebas

1. El RCOF agrupa por tipo de documento y suma neto, IVA, exento y total.
2. Los folios utilizados deben compactarse en rangos continuos; por ejemplo
   `1-3` y `5-5`, nunca fingir un rango `1-5` si el 4 no fue usado.
3. `FoliosUtilizados = FoliosEmitidos + FoliosAnulados`.
4. Autenticación y transporte son componentes distintos de la generación XML.
5. La semilla expira rápidamente; el token puede cachearse, separado por certificado y
   ambiente.
6. Certificación y producción necesitan configuración y endpoints imposibles de mezclar.
7. Las respuestas del SII pueden traer problemas de encoding pese a declarar UTF-8.
8. Un timeout posterior al upload no autoriza a reenviar a ciegas: primero se reconcilia
   el estado remoto.

## Estado real de Completo

La integración no parte de cero. `plataforma-restaurante` ya tiene:

- tenancy y sucursales;
- POS y turnos de caja;
- venta atómica `create_pos_sale`;
- precios y nombres congelados en `order_items`;
- cálculo del total en servidor;
- método de pago;
- propina separada de la venta;
- `sii_emission_model` por tenant (`voucher_as_boleta` o `always_boleta`);
- entitlement comercial `facturacion`.

Todavía no existen físicamente las tablas DTE previstas en `DB-DESIGN.md` ni un outbox
fiscal. El POS hoy registra la venta, caja e inventario, pero no genera una orden fiscal
durable para un worker.

## Frontera mínima de integración

Completo no debe construir XML ni conocer CAF/certificados. En la misma transacción de
`create_pos_sale` debe crear un evento de outbox fiscal inmutable:

```text
venta POS confirmada
  -> snapshots de ítems y total
  -> decidir boleta versus voucher según método/modelo
  -> fiscal_outbox(order_id, tenant_id, branch_id, idempotency_key, payload)
  -> worker llama al motor DTE
  -> motor asigna folio, firma, envía y devuelve estado
  -> Completo proyecta estado en dte_documents/dte_document_events
```

No se debe llamar al SII dentro de la transacción SQL ni bloquear el cobro esperando una
respuesta externa.

## Datos que faltan en Completo

Antes de integrar se deben agregar al catálogo o al snapshot de venta:

- clasificación tributaria de cada ítem (`afecto`/`exento`);
- unidad de medida opcional;
- configuración fiscal del tenant y sucursal;
- política explícita para pagos electrónicos/voucher;
- correlación única `order_id -> documento fiscal`;
- estado `no_dte_voucher` para evitar doble tributación.

La clave idempotente recomendada es:

```text
completo:{tenant_id}:order:{order_id}:dte:39
```

## Orden recomendado antes del CAF real

1. Aplicar y probar la migración outbox/RLS en Supabase staging.
2. Conectar el worker cloud por tenant y desplegar consulta HTTPS.
3. Probar PFX real + autenticación de certificación sin descargar CAF.
4. Congelar versión y ensayar restauración/reintentos.
5. Recién entonces descargar los cinco folios reales e iniciar las 24 horas.
