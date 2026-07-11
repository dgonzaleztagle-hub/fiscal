# Baseline Hito 3 — notas 56/61 y guía 52

## Notas de crédito y débito

Fuentes oficiales verificadas el 2026-07-10:

- Formato DTE 2.5 (2026-02), códigos de referencia 1, 2 y 3.
- Guías SII de anulación, corrección de texto y corrección de montos.
- Preguntas frecuentes SII sobre rechazo y nulidad de DTE.

Reglas fijadas:

- código 1: anulación completa; nota 61 anula factura 33/34 o nota 56;
- código 2: nota 61 corrige texto de factura 33/34;
- código 3: nota 61 disminuye y nota 56 aumenta montos de factura 33/34;
- texto y monto no se corrigen simultáneamente;
- la nota debe seleccionar el documento emitido original y mantener trazabilidad;
- Completo no permite acreditar más que el saldo vigente.

La implementación actual habilita los tres códigos para los casos comunes fijados:

- código 1 se deriva automáticamente del XML original y copia sus montos;
- código 2 sólo permite cambiar giro, dirección o comuna y genera total cero;
- código 3 recibe la diferencia monetaria y controla el saldo acreditable.

No se permite combinar texto y monto en una misma nota.

## Compuerta dinámica LibreDTE

Se instaló un runtime exclusivamente temporal, sin PATH global ni servicios:

- PHP 8.5.8 NTS x64, ZIP SHA-256
  `63A3F6493F37C9FF3E288EC16621222A6CDA5167DD1ABFFEC0019E7F18C8E7E9`;
- Composer 2.10.2, SHA-256
  `5EE7125F8A30A34D246CEFDC0BC85B8A783B28F2AEC968994118512350D28027`;
- resolución temporal de dependencias, `composer.lock` SHA-256
  `43D35CED434419010A9F4FF62F5509C6ACD1006EBD1C42596FA0AAA2148D8648`.

LibreDTE permaneció en commit
`55d4718ba625e0f00ba7cc995837da5f7869ea4c` y árbol limpio. La ejecución con el mismo
caso 33 confirmó neto `31500`, IVA `5985` y total `37485`.

Para corrección de texto, LibreDTE produjo nota 61, `CodRef=2`, una línea descriptiva y
total cero, coincidiendo semánticamente. Sin embargo incluyó `PrcItem=0`; el XSD oficial
rechaza ese valor porque el mínimo es `0.000001`. Completo omite `QtyItem` y `PrcItem`
en la línea puramente textual, conserva `MontoItem=0` y valida contra `DTE_v10.xsd`.
La autoridad oficial prevalece sobre la referencia secundaria.

## Guía de despacho 52

La Resolución Ex. SII 154 de 2025 agregó origen/destino efectivos, chofer,
transportista, patente de vehículo/carro y fechas de salida/llegada. La Resolución Ex.
SII 52 del 10 de abril de 2026 postergó su entrada en vigencia al **1 de noviembre de
2026**.

El formato PDF 2.5 ya describe patente de carro y fechas/horas del traslado, pero el
paquete oficial `DTE_v10.xsd` descargado y fijado el 2026-07-10 todavía no contiene
esos elementos. Decisión conservadora:

- el dominio ya reserva esos campos para no romper el contrato en noviembre;
- el builder los rechaza explícitamente mientras el XSD oficial fijado no los admita;
- no se enviarán etiquetas no reconocidas anticipadamente;
- una actualización futura exigirá nueva descarga, hash, pruebas XSD y compuerta
  comparativa antes de habilitarlas.

Los nueve motivos permanecen alineados con `DispatchReason`; el código 7 se presenta
como “Devolución de Mercaderías”. El builder 52 está habilitado localmente para el XSD
vigente y cubre:

- venta valorizada con `TipoDespacho`, neto, IVA y total;
- traslado interno con emisor igual a receptor, sin `TipoDespacho`, sin precio y total
  cero;
- transporte vigente: patente, transportista, chofer y destino;
- TED, XMLDSig, validación `DTE_v10.xsd`, sobre `EnvioDTE`, ledger idempotente, API y
  representación PDF carta.

La ejecución dinámica de LibreDTE para su caso sintético de traslado interno confirmó
la misma semántica: `IndTraslado=5`, `TipoDespacho` ausente, cantidad conservada,
`PrcItem` ausente, `MontoItem=0` y `MntTotal=0`. Sus fixtures de venta tipo 52 usan
neto `31500`, IVA `5985` y total `37485`, coincidente con el cálculo propio usado en la
compuerta de facturas. No se copió código ni fixture al producto.

No se descargará un CAF 52 real hasta que el entorno HTTPS, certificado privado,
respaldo y controles previos de certificación estén verdes.
