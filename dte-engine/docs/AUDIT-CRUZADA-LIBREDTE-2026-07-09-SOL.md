# Auditoría cruzada Sol — Completo DTE vs. LibreDTE y SII

> **Nota de vigencia (2026-07-11):** este informe conserva el estado histórico del 9
> de julio. Sus brechas de worker durable, DTE 33/34/41/52/56/61, recepción, RCV,
> backup local y reportes fueron implementadas después y constan en los baselines H3,
> H4 y H5. Siguen pendientes infraestructura cloud, vault/certificado reales y
> validación efectiva en certificación SII.

**Fecha:** 2026-07-09  
**Motor auditado:** `dte-engine`  
**LibreDTE usado como referencia:** `LibreDTE/libredte-lib-core`, commit
`55d4718ba625e0f00ba7cc995837da5f7869ea4c`  
**Set oficial:** `Set Prueba BE (2).txt`, SHA-256
`96B97F2DDC5663F3B9712936B9EBF86283431CEDF540962DA310BD14F093D1DB`

## Veredicto ejecutivo

El núcleo de boleta 39 está bien encaminado y ya no parece un experimento desechable:
CAF autenticado, TED, XMLDSig, sobre, folios idempotentes, persistencia inmutable,
RCOF, PDF417, transportes SII y aislamiento de lectura tienen una base propia sólida.
En control de folios e inmutabilidad el diseño es más estricto que la capa equivalente
observada en LibreDTE.

La auditoría, sin embargo, encontró que el ensayo denominado “E2E de certificación” daba
más seguridad de la que realmente probaba. También encontró tres fronteras que LibreDTE
trata explícitamente y el motor no cerraba: integridad de los DTE antes de armar el sobre,
carácter estrictamente diario del RCOF y consulta posterior del envío RCOF por
`QueryEstUp`. Estos puntos fueron corregidos.

**Decisión:** apto para seguir preparando la certificación; todavía **no es prudente
descargar el CAF real ni iniciar las 24 horas**. Los bloqueos restantes dependen de
credenciales/infraestructura real y de cerrar la discrepancia entre el formato 4.2 de
boleta y el XSD público del SII.

## Hallazgos reproducidos y corregidos

### [P0] El dry-run no reproducía fielmente el CASO-1

El set exige dos ítems: `Cambio de aceite` por $19.900 y `Alineacion y balanceo` por
$9.900. La prueba matricial sí contenía ambos, pero el supuesto ensayo E2E sólo generaba
el primero. El sobre simulado tenía cinco DTE, pero uno no correspondía al caso oficial.

**Corrección:** el dry-run ahora genera los dos ítems y el total $29.800.

### [P1] El sobre podía firmar DTE alterados, repetidos o de otro emisor

`EnvioBoletaBuilder` confiaba en cualquier instancia `SignedDte`. Podía crear un sobre
perfectamente firmado que contuviera un DTE adulterado, dos veces el mismo folio o un DTE
de otro RUT. El XSD no reemplaza estas verificaciones semánticas.

**Corrección:** antes de firmar el sobre se verifica cada XMLDSig contra el certificado
esperado, la identidad del `Documento`, RUT emisor, tipo 39 y unicidad de documento y
folio.

### [P1] El RCOF permitía mezclar jornadas

El builder calculaba `FchInicio=min(fechas)` y `FchFinal=max(fechas)`. El formato oficial
indica que, cuando el resumen es diario, ambas fechas deben ser iguales.

**Corrección:** el builder rechaza folios de más de una fecha.

### [P1] No existía consulta de estado del RCOF

El adaptador heredado autenticaba y subía el RCOF, pero no implementaba `QueryEstUp`.
Esto dejaba el Track ID sin reconciliación automática y contradecía el principio de no
reenviar a ciegas después de un resultado ambiguo.

**Corrección:** se agregó `get_upload_status()` con los cuatro parámetros del WSDL,
correlación de Track ID, conteos informados/aceptados/rechazados/reparos y clasificación
conservadora del resultado.

### [P1] Las respuestas REST no se correlacionaban con la solicitud

Upload y consulta aceptaban literalmente el RUT y Track ID contenidos en cualquier JSON
2xx. Un proxy defectuoso, respuesta cruzada o cambio inesperado podía asociar un envío a
otro contribuyente.

**Corrección:** se validan RUT emisor/enviador, Track ID numérico, forma de la respuesta,
listas de estadísticas y nombre seguro del archivo. Una respuesta no correlacionada
falla cerrada.

### [P2] La fecha de emisión no respetaba el rango documental publicado

El modelo aceptaba cualquier `date`. El formato 4.2 limita `FchEmis` a 2002-08-01 hasta
2050-12-31.

**Corrección:** el dominio aplica ese rango antes de reservar definitivamente un XML.

## Brechas abiertas antes de certificación real

### [P0 operativo] Falta ensayo privado con PFX, CAF y XSD reales

La suite sólo usa identidades sintéticas. El bootstrap sí exige XSD y valida antes de
persistir, pero el dry-run aislado usa transportes simulados y no acredita por sí mismo:

- apertura y autorización efectiva del PFX comprado;
- FRMA del CAF real con el certificado histórico SII correspondiente al `IDK`;
- aceptación efectiva de semilla/token por certificación;
- validez del sobre definitivo contra el material exacto usado por el SII;
- disponibilidad pública HTTPS de la representación.

El CAF de cinco folios no debe descargarse para resolver estos puntos: primero se prueba
PFX/autenticación y despliegue sin iniciar el reloj de 24 horas.

### [P1] Formato 4.2 y XSD público no están sincronizados

El PDF oficial versión 4.2 (2025-09-08) incluye campos que el motor todavía no modela:
`MedioPago`, `RutProvSW`, `RznSocProvSW`, correo y teléfono del receptor. Además, para
operaciones sobre 135 UF exige medio de pago e identificación del receptor.

El ZIP oficial `schema_envio_bol.zip` descargado en esta auditoría conserva hash
`CD9BBB1297CF9C6E6CB887F4D1686C91C8476E8C01AFAAFC5D0948F48BEC044D`, fecha interna
2010 y no contiene `RutProvSW` ni `MedioPago`. Por eso no corresponde agregar campos a
ciegas hasta confirmar qué schema/validación aplica hoy el ambiente de certificación.

Los cinco casos asignados están muy por debajo de 135 UF, por lo que `MedioPago` no
bloquea este set. `RutProvSW` sí debe confirmarse antes del envío real: para desarrollo
propio el formato ordena informar el RUT del emisor y omitir el nombre del proveedor.

### [P1] Los componentes todavía no forman un worker operacional único

Existen builders, ledger, upload y consultas, pero no un proceso persistente que haga:

```text
DTE locales pendientes
  -> lote máximo 500 por RUT
  -> validar + persistir EnvioBOLETA
  -> upload con intento durable
  -> polling por Track ID
  -> RCOF del día y SecEnvio correcto
  -> polling QueryEstUp
  -> proyectar resultado a Completo
```

El puente actual de Completo llega hasta emisión/firma local. No debe presentarse todavía
como ciclo fiscal autónomo terminado.

### [P1] Confianza y custodia del certificado

Se valida vigencia, RSA, clave privada y correspondencia de clave, pero faltan cadena de
confianza, entidad acreditada, usos de clave y revocación. Además, el bootstrap local lee
PFX/contraseña desde archivo/entorno; producción multi-tenant necesita vault, rotación,
auditoría de acceso y separación por emisor.

### [P1] Conservación y recuperación

SQLite es correcto para laboratorio, no para 10–100 tenants cloud. El SII exige conservar
los XML por seis años. Faltan PostgreSQL, copias cifradas, restauración probada, retención,
monitoreo de CAF bajo y recuperación ante caída. La URL pública debe conservar consulta
al menos tres meses y evitar enumeración, condición que el identificador opaco ya ayuda a
cumplir.

## Comparación honesta con LibreDTE

| Área | Completo DTE | LibreDTE observado | Evaluación |
|---|---|---|---|
| Boleta 39 y set asignado | Directo, pequeño, tipado | Pipeline genérico con más fixtures | Completo suficiente para este set |
| CAF/TED | FRMA fijada por IDK antes de timbrar | Gestión CAF madura | Completo es conservador en confianza |
| Folios/idempotencia | Ledger transaccional e inmutable | Gestores más generales | Ventaja arquitectónica de Completo |
| Sobre | Ahora valida firma, emisor y duplicados | Builder/validador separados | Brecha principal cerrada |
| RCOF | Diario, rangos, firma y estado | Builder y respuesta maduros | Alineado en el caso actual |
| Transporte/estados | REST boleta + DTE heredado, fail-safe | Cobertura histórica más amplia | LibreDTE sigue siendo referencia útil |
| Casos DTE | Sólo 39; descuento por monto | 33/34/39/41/46/52/56/61 y más | Gran brecha de producto, no del set |
| Recepción/intercambio | No implementado | respuestas, recibos, email, AEC/RCV | Necesario para Completo Fiscal |
| Persistencia multi-tenant | Contratos listos; SQLite local | Librería, no SaaS propio | Falta infraestructura cloud real |
| Licencia | Código propio | AGPL-3.0-or-later | Usar ideas/casos; no incorporar código |

## Lo que el modelo anterior hizo bien

- detectó y corrigió persistencia previa a XSD e idempotencia desligada del payload;
- separó autenticación REST de la vía DTE heredada;
- implementó estados `unknown` para evitar reenvíos ciegos;
- hizo inmutables documentos, eventos y payloads de sobres;
- aisló XML por tenant y consulta pública por identificador opaco;
- generó PDF417 desde el TED persistido y lo decodificó con una librería independiente;
- dejó el motor separado de Completo y la venta desacoplada mediante outbox.

El error no fue una mala arquitectura. Fue declarar como “E2E” una prueba que todavía
saltaba controles importantes y no reproducía exactamente uno de los cinco casos.

## Evidencia de esta pasada

- 86 pruebas pasan.
- `ruff check src tests`: sin hallazgos.
- `pip check`: dependencias consistentes (ejecutado antes de las correcciones; éstas no
  modificaron dependencias).
- ZIP XSD oficial: hash confirmado sin cambios.
- Fuentes oficiales contrastadas:
  - https://www.sii.cl/factura_electronica/factura_mercado/formato_boleta_electronica.pdf
  - https://www.sii.cl/factura_electronica/consumo_folios.pdf
  - https://www.sii.cl/servicios_online/1039-guia_emitir_boleta_servicio-1184.html
  - https://www4c.sii.cl/bolcoreinternetui/api/

## Orden de cierre recomendado

1. Confirmar con PFX real la autenticación de certificación, sin descargar CAF.
2. Resolver `RutProvSW` contra el comportamiento real del ambiente y congelar el XML
   exacto de Roda.
3. Desplegar y probar la consulta HTTPS/PDF de certificación.
4. Implementar el worker de sobres/RCOF/polling sobre el ledger.
5. Ejecutar un ensayo privado completo con XSD y respaldos reales.
6. Recién entonces descargar el CAF de cinco folios y comenzar la ventana de 24 horas.
