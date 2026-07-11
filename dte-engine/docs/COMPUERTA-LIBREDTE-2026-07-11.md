# Compuerta LibreDTE — 2026-07-11

Referencia secundaria: `libredte-lib-core` commit
`55d4718ba625e0f00ba7cc995837da5f7869ea4c`, árbol limpio. No se incorporó código,
fixture ni dependencia AGPL al producto.

## Recepción y Registro Reclamo

LibreDTE expone pruebas de integración para enviar ACD y consultar fecha de recepción
SII. Ambas requieren certificado y staging reales. Su prueba de correo requiere
credenciales de buzón, deja mensajes sin marcar y contiene una aserción manual pendiente.

Completo cubre offline ACD, ERM, RCD, RFP y RFT con la matriz oficial, fecha autoritativa
como observación append-only, intentos durables `unknown`, reconciliación y resultados
por adjunto. No se intentó comparar respuestas reales sin certificado.

Resultado: sin discrepancia semántica contra LibreDTE; mayor cobertura local propia. La
autoridad sigue siendo el WS SII 1.1, no la implementación secundaria.

## Compuerta documental dinámica

Se ejecutó el builder LibreDTE temporal sobre dos casos sintéticos públicos:

| Caso | Tipo despacho | Motivo | Neto | IVA | Total | Precio línea |
|---|---:|---:|---:|---:|---:|---:|
| Guía que constituye venta | 1 | 1 | 31.500 | 5.985 | 37.485 | 70 |
| Traslado interno | ausente | 5 | 0 | 0 | 0 | ausente |

Completo mantiene exactamente esas invariantes. Los builders propios, XSD fijado y tests
siguen siendo la evidencia primaria.

## UI ↔ motor

El listado HTTP fue enriquecido con contraparte, fecha y total proyectados por backend.
La consola usa `FISCAL_API_URL` y `FISCAL_API_TOKEN` sólo en servidor; si el motor falla
en cuatro segundos vuelve a demo y lo declara visualmente. El navegador no recibe token
ni necesita analizar XML.
