# Auditoría integral — 2026-07-11

## Alcance y resultado

Se revisaron `dte-engine`, `fiscal-console` y `sii-reader` después de separarlos del
proyecto original. La pasada incluyó arquitectura, aislamiento multi-tenant, entrada XML,
dependencias, regresión documental, compilación de la consola y comparación secundaria
con LibreDTE. No se usaron CAF, certificados, RUT ni servicios SII reales.

Resultado: **sin hallazgos P0/P1 abiertos en el alcance offline**. El sistema sigue sin
estar autorizado para producción ni certificación real; esas compuertas dependen del
certificado, CAF y respuestas del SII.

## Cambios realizados

- Se extrajeron los estados, errores y records persistentes desde `folio_ledger.py` a
  `infrastructure/records.py`. Esto elimina 218 líneas de modelos mezclados con SQL y
  permite reemplazar SQLite por PostgreSQL sin cambiar el contrato de dominio.
- La persistencia quedó dividida en núcleo de folios, documentos, transmisión/entrega y
  recepción/compras. Los mixins conservan la misma conexión y frontera transaccional;
  `folio_ledger.py` bajó de 1.912 a 374 líneas sin introducir commits intermedios.
- Se extrajo la autenticación por tenant a `api/security.py`. La comparación del secreto
  sigue siendo constante y ahora tiene pruebas específicas para token válido, ausente,
  inválido y configuración incompleta.
- Se extrajeron los 30 contratos Pydantic a `api/contracts.py` y las proyecciones de
  registros a `api/projections.py`. Las rutas quedaron divididas por emisión, recepción,
  RCV, reportes, operación y portal público. `app.py` bajó de 1.546 a 94 líneas y ahora
  sólo compone dependencias, sin modificar rutas ni modelos OpenAPI.
- El parser CAF dejó de usar `xml.etree`: ahora usa `lxml` sin DTD, red ni resolución de
  entidades, con límite de 1 MB. Se añadieron regresiones XXE y de tamaño excesivo.
- Se actualizaron `cryptography` a `>=48.0.1,<49` y el entorno de auditoría a una versión
  corregida de `pip`. `pip-audit` quedó sin vulnerabilidades conocidas.
- Los usos de SHA-1 y RSA-1024 fueron clasificados y documentados en línea. No son una
  elección criptográfica interna: son interoperabilidad heredada exigida por CAF, TED y
  XMLDSig del SII; el RSA-1024 generado por la aplicación existe sólo en la demo sintética.
- Las consultas SQL dinámicas auditadas sólo interpolan la cantidad de placeholders `?`;
  tenant, RUT, IDs y tipos se entregan como parámetros y se validan antes de consultar.

## Evidencia ejecutada

| Componente | Compuerta | Resultado |
|---|---|---|
| Motor | suite Pytest completa | verde, 205 casos ejecutados |
| Motor | Ruff general y reglas de seguridad | verde |
| Motor | `pip check` / `pip-audit` | verde / 0 vulnerabilidades conocidas |
| Documentos | matriz 33, 34, 39, 41, 52, 56 y 61 | verde |
| Consola | ESLint + TypeScript + Next.js 16 build, 23 rutas | verde |
| Consola | `npm audit --omit=dev` | 0 vulnerabilidades |
| Reader | Pytest + Ruff | verde |
| LibreDTE | commit fijado y árbol limpio | verde |

La consola incorpora ESLint con los presets oficiales `core-web-vitals` y TypeScript de
Next 16, ejecutado con cero advertencias permitidas. El cliente OpenAPI generado queda
excluido porque no es código mantenido manualmente.

## Comparación LibreDTE

Se volvió a ejecutar `scripts/check_reference_baseline.py` contra un clon aislado y limpio:

- commit: `55d4718ba625e0f00ba7cc995837da5f7869ea4c`;
- familias declaradas: 33, 34, 39, 41, 52, 56 y 61;
- ningún código, fixture ni dependencia AGPL fue copiado al producto;
- la matriz propia de builders y XSD pasó completa después del refactor.

La comparación semántica dinámica previa de guías 52 sigue vigente: venta y traslado
interno coinciden en razón de traslado, totales y presencia/ausencia de precios. Para
recepción y reclamo, LibreDTE también requiere certificado y staging; no inventamos una
comparación E2E que todavía no puede ejecutarse.

Orden de autoridad mantenido: documentación, XSD y certificación SII; luego consulta
formal al SII; LibreDTE sólo como referencia secundaria.

## Deuda modular priorizada

No se dividieron artificialmente reglas tributarias sólo para bajar métricas. Las
validaciones de facturas, notas y guías son complejas por sus invariantes y hoy están
cubiertas por pruebas. Sí quedan dos concentraciones que deben reducirse por etapas:

1. Los comandos de boleta, factura y guía ya se construyen en mapeadores separados; al
   agregar nuevos impuestos se debe mantener esa frontera y no devolver lógica al router.
2. Reemplazar gradualmente los mixins SQLite por puertos de repositorio PostgreSQL cuando
   exista el esquema privado de Supabase; la división actual ya separa esas fronteras sin
   alterar la atomicidad local.

Estas tareas son P2 de mantenibilidad, no defectos funcionales. Hacer la separación en
un solo cambio gigante aumentaría el riesgo justo antes de la certificación; debe hacerse
verticalmente, con la suite verde después de cada repositorio/router extraído.

## Bloqueos reales antes del CAF

- certificado digital y custodia externa del PFX;
- endpoints y credenciales de certificación validados contra SII;
- consulta pública HTTPS desplegada;
- respaldo/restauración probado fuera del proceso local;
- ensayo E2E completo en certificación, incluido timeout ambiguo y reconciliación;
- aprobación explícita antes de descargar los cinco folios.
