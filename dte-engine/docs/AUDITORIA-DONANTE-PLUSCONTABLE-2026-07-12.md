# Auditoría donante PlusContable — 2026-07-12

## Propósito

Esta auditoría determina qué conocimiento operacional probado de `pluscontable.cl` debe
reconstruirse dentro de Completo Fiscal. PlusContable lleva meses en uso real y sus flujos
fueron diseñados con un contador; por eso se trata como un donante funcional valioso. No se
convertirá en dependencia, no se modificará y no se copiará como un producto para estudios
contables.

El destinatario de Completo Fiscal es primero el dueño o administrador de una pyme. La meta
es que llegue al cierre del mes con sus documentos ordenados, diferencias explicadas y un
paquete que reduzca la revisión manual del contador. Completo no reemplazará el juicio ni la
responsabilidad profesional del contador y no presentará declaraciones sin un flujo futuro,
expreso y autorizado.

## Qué es realmente PlusContable

La revisión de rutas, pantallas, tablas, funciones programadas, cálculos y exportadores muestra
que Plus contiene tres productos superpuestos:

1. Una cartera para que una oficina contable administre muchos clientes, tareas, cobros y
   documentos.
2. Una máquina de cumplimiento mensual y anual: F29, F22, vencimientos, conciliaciones,
   honorarios y reportes.
3. Una gestión básica de personas: fichas, contratos, eventos mensuales y cotizaciones.

Sólo la segunda pertenece directamente a Fiscal. La tercera debe vivir en Completo Personas
y aportar resultados resumidos a Fiscal. La primera pertenece al negocio del contador y no
debe confundirse con las necesidades del dueño de una pyme.

## Hallazgo principal

Fiscal ya posee una base técnicamente más segura para documentos tributarios: DTE emitidos y
recibidos, XML inmutable, RCV versionado, conciliación, BHE, propuesta F29, auditoría y paquete
para contador. Plus no reemplaza esa base. Lo que aporta es el conocimiento de cómo cerrar el
mes en la práctica: qué totales mirar, qué saldos arrastrar, qué vencimientos alertar, qué
estados distinguir y qué información necesita revisar un humano.

El trasplante correcto es portar esas reglas al backend de Fiscal con casos de regresión y
versiones de fórmula. Copiar las fórmulas React tal como están dejaría decisiones tributarias
en el navegador, permitiría resultados distintos entre versiones y perdería trazabilidad.

## Inventario útil y decisión

| Activo probado en Plus | Decisión | Destino en Completo |
| --- | --- | --- |
| Desglose de ventas y compras por tipos 33, 34, 39, 41, 46, 48, 56 y 61 | Reconstruir ahora | Motor de cierre mensual Fiscal |
| Notas de crédito restadas y notas de débito sumadas en montos; conteos documentales separados | Reconstruir con fixtures | Agregador documental y propuesta F29 |
| Débito, crédito, remanente anterior y nuevo remanente | Reconstruir con trazabilidad | Ledger de períodos fiscales |
| PPM sobre base de ventas definida por Plus | Usar como baseline probado y verificar contra fuente SII vigente | Regla versionada de propuesta F29 |
| Cambio de sujeto, retenciones, impuesto único, segunda categoría y otros impuestos | Reconstruir por capacidades activables | Líneas avanzadas del cierre/F29 |
| Recargos tardíos y condonación | Posponer hasta fijar fuentes y vigencia | Simulador informativo, nunca pago automático |
| Sincronización de propuesta F29 y comparación con cálculo propio | Conservar y completar | Vista F29 y sistema de diferencias |
| Arrastre y reconciliación de saldos | Copiar el patrón, no los honorarios de la oficina | Remanentes y obligaciones mensuales |
| Alertas por vencimiento y precarga de obligaciones | Adaptar | Calendario y checklist del tenant |
| F22 y declaraciones juradas por régimen, estado y fecha límite | Adaptar como preparación anual | `Preparación de renta`, no presentador F22 |
| Bóveda documental por empresa, categoría y período | Fusionar con evidencia existente | Documentos y expediente mensual |
| Informes PDF por cliente/período | Adaptar a paquete verificable | Exportación para dueño y contador |
| Fichas, contratos, eventos y cotizaciones previsionales | No duplicar en Fiscal | Completo Personas; Fiscal recibe resumen |
| Honorarios cobrados por el estudio contable a sus clientes | No trasladar | No corresponde a BHE de la pyme |
| CRM de clientes, órdenes internas, academia y comunidad | No trasladar | Fuera del producto Fiscal |
| RUT y claves SII visibles/copìables en UI | Prohibido trasladar | Vault y referencias opacas en backend |

## Reglas halladas que merecen regresión exacta

Plus arma totales de ventas con facturas, boletas, facturas de compra, notas y documentos
exentos. Para montos, las notas de crédito tipo 61 disminuyen el período; para cantidad de
documentos se contabilizan de manera explícita y no se ocultan dentro del neto. Compras usa
la misma idea con su conjunto de tipos admitidos. La propuesta combina:

- IVA débito de ventas e IVA crédito respaldado por compras;
- remanente del período anterior y cálculo del remanente siguiente;
- cambio de sujeto como crédito o débito según el rol;
- PPM, retenciones de segunda categoría e impuesto único;
- impuestos específicos configurados y retenciones adicionales;
- honorarios/BHE asociados al período;
- recargos y condonaciones cuando el pago está fuera de plazo.

Estos comportamientos deben convertirse en casos de prueba anonimizados antes de escribir el
nuevo calculador. El valor de Plus está en la combinación y en los bordes operacionales, no
en reutilizar sus componentes visuales.

## Diseño de producto resultante

### Inicio: “Cómo viene este mes”

La portada debe contestar, sin lenguaje contable: cuánto se vendió, cuánto se compró con
respaldo, cuánto impuesto se estima, qué falta resolver y cuál es la próxima fecha importante.
Una diferencia no será sólo un número rojo: dirá, por ejemplo, “el SII registra una factura
de compra cuyo XML aún no tenemos”.

### Cierre mensual

Será el centro de la maquinaria nueva y unirá emisión, recibidos, RCV, BHE, pagos electrónicos
y Personas. Tendrá un recorrido estable:

1. Completar evidencias faltantes.
2. Conciliar documentos propios con snapshots SII.
3. Revisar ventas, compras, crédito, débito, retenciones y remanentes.
4. Explicar cada diferencia y registrar quién decidió qué hacer.
5. Congelar una versión del cierre y preparar el paquete para el contador.

El dueño verá primero explicaciones y acciones. Los códigos F29, fuentes y cálculos exactos
estarán disponibles en una vista avanzada, no escondidos ni impuestos como lenguaje inicial.

### Propuesta F29

La pantalla existente deja de ser una demostración aislada y pasa a ser una proyección del
cierre. Cada línea conservará valor calculado, valor consultado al SII, fórmula/version,
fuentes utilizadas y causa de la diferencia. Actualizar datos generará una nueva versión; no
reescribirá una revisión anterior.

### Expediente del mes

En vez de la carpeta genérica de Plus, Fiscal mostrará qué evidencia existe y cuál falta:
XML emitidos y recibidos, RCV, BHE, pagos/vouchers, resumen de Personas, ajustes documentados
y reportes. Un PDF u OCR puede ayudar a clasificar, pero nunca reemplaza el XML cuando éste
es la evidencia tributaria.

### Preparación de renta

F22 no se copiará como una grilla para un contador que administra cientos de clientes. Para
el dueño será una preparación anual: períodos cerrados, declaraciones o antecedentes
esperados según su régimen, documentos pendientes y paquete anual. Inicialmente será sólo
lectura, preparación y seguimiento.

## Arquitectura que debe sostenerlo

Se añadirá un agregado `fiscal_period` por tenant, año y mes. Cada cálculo producirá un
snapshot inmutable con:

- versión de fórmula y fecha de cálculo;
- hashes e identificadores de los documentos y snapshots de entrada;
- líneas calculadas en pesos enteros, nunca `float`;
- comparación con valores SII y diferencias clasificadas;
- ajustes humanos como eventos separados, con actor, razón y evidencia;
- estado de revisión: abierto, incompleto, listo para revisión, revisado y congelado.

El cálculo debe ser idempotente: las mismas entradas y la misma versión producen el mismo
resultado. La llegada tardía de un XML o un nuevo snapshot RCV crea otra versión. Nunca se
edita un DTE, snapshot ni cierre congelado para hacer cuadrar una pantalla.

Completo Personas será dueño de contratos, asistencia, eventos, remuneraciones y
cotizaciones. Entregará a Fiscal un resumen mensual versionado de remuneraciones,
retenciones y obligaciones. Fiscal no tendrá una segunda ficha de trabajador.

La conciliación de pagos/vouchers será transversal y servirá tanto a Gastro como a Fiscal
standalone. Debe registrar terminal, operador/adquirente, código de autorización, referencia,
monto, fecha, liquidación y relación con venta/DTE. Así se podrá explicar ventas pagadas con
tarjeta y detectar diferencias sin obligar a la caja a digitar nuevamente lo que una
integración ya conoce.

## Orden recomendado de incorporación

### Etapa 1 — Congelar el conocimiento de Plus

Crear fixtures sintéticos que cubran períodos con nota de crédito, nota de débito, ventas
exentas, remanente, cambio de sujeto, PPM, BHE, impuestos adicionales y saldos arrastrados.
Reproducir con ellos los resultados observados en Plus. Documentar cualquier ambigüedad; no
resolverla por intuición.

### Etapa 2 — Motor de cierre versionado

Crear el dominio y persistencia de períodos, entradas, líneas, diferencias, revisiones y
snapshots. Alimentarlo desde los documentos, recibidos, RCV y BHE ya presentes en Fiscal.
Contrastar las reglas tributarias variables con documentación o ambiente SII antes de
tratarlas como vigentes.

### Etapa 3 — Experiencia del dueño

Convertir Dashboard, F29 y Reportes en un flujo real de cierre mensual. Añadir expediente,
explicaciones, checklist, bloqueo por faltantes y exportación. Mantener el detalle técnico en
capas avanzadas.

### Etapa 4 — Pagos y Personas

Añadir conciliación de vouchers/liquidaciones e importar el resumen mensual de Personas.
Esto permitirá que Gastro alimente Fiscal automáticamente y que un negocio standalone pueda
registrar o importar sus pagos sin depender de Gastro.

### Etapa 5 — Preparación anual

Construir preparación de renta y declaraciones juradas como calendario/evidencia. No
automatizar presentación F22 hasta realizar una auditoría legal y técnica independiente.

## Criterio de aceptación

La cosecha se considerará correcta cuando un período sintético complejo produzca el mismo
resultado esperado que las reglas probadas de Plus, pero desde un servicio backend
determinista; cuando cada cifra pueda explicarse hasta sus documentos de origen; cuando un
nuevo snapshot no destruya la versión anterior; y cuando el dueño pueda completar el cierre
sin comprender códigos tributarios, dejando al contador un paquete corto de validación en
vez de una reconstrucción manual del mes.

## Decisión final

PlusContable aporta más de lo que parecía, pero no convierte a Fiscal en un software de
contabilidad general ni en un ERP contable. Lo convierte en un sistema de **operación fiscal
y precontabilidad verificable**: emite, recibe, concilia, explica, prepara y conserva evidencia.
Esa frontera es suficientemente potente para ahorrar trabajo real al negocio y al contador,
sin prometer libros mayores, balances, estados financieros ni declaraciones automáticas que
todavía no construimos.

## Avance implementado el 12 de julio

La primera etapa dejó de ser sólo planificación:

- se creó un calculador backend determinista con la familia de reglas observada en Plus:
  notas 56/61, afecto/exento, IVA débito/crédito, remanente, cambio de sujeto, PPM,
  retenciones, otros impuestos, recargos y condonación;
- se fijó la versión `plus-baseline-2026-07-v1` y se añadieron casos sintéticos de regresión;
- cada resultado incluye hash de fuentes, hash de cálculo y diferencias semánticas contra una
  propuesta SII opcional;
- se incorporó persistencia append-only SQLite y PostgreSQL para snapshots y revisiones;
- recalcular las mismas entradas es idempotente y una entrada distinta crea una nueva versión;
- el workflow de revisión sólo admite `opened → marked_ready → reviewed → frozen` y valida el
  tenant en cada transición;
- la API permite calcular/persistir, listar versiones y registrar revisiones, sin presentar ni
  rectificar declaraciones;
- la consola incorporó `Cierre mensual / Cómo viene este mes`, validada visualmente en escritorio
  y móvil, con navegación hacia la propuesta F29 y sidebar persistente.

Quedan para la siguiente pasada el expediente mensual, la conciliación detallada de
vouchers/liquidaciones y el contrato de resumen con Completo Personas. Ninguna de estas piezas
requiere certificado, CAF ni acceso al SII real.

### Segunda pasada del 12 de julio

- se implementó el expediente mensual con inventario determinista de documentos, RCV, cierre,
  BHE, Personas y pagos;
- el expediente distingue una evidencia obligatoria faltante de un módulo no aplicable o aún no
  conectado, evitando bloquear tenants por servicios que no contrataron;
- el ZIP para contador ahora incluye `expediente/expediente.json` y fija su hash de evidencia en
  el manifiesto verificable;
- se añadió la pantalla `Expediente mensual`, revisada en escritorio y móvil, con descarga
  bloqueada mientras falte evidencia y retorno al cierre sin perder navegación;
- comenzó la conciliación de pagos electrónicos: identidad única de voucher, asociación a venta,
  diferencias de monto y tratamiento separado para `always_issue` y `voucher_as_boleta`;
- se agregaron esquemas privados e inmutables para vouchers y snapshots de conciliación, sin
  exponerlos al frontend ni convertir un voucher automáticamente en un DTE.

### Cierre de la capa previa a Policía

- pagos electrónicos quedó completo desde importación idempotente hasta snapshot conciliado,
  consulta tenant-first y visualización desde el motor;
- `voucher_as_boleta` evita un DTE duplicado y `always_issue` exige encontrar la boleta;
- el expediente consume automáticamente la última conciliación de pagos;
- Completo Personas dispone de un contrato mensual versionado, hasheado e inmutable, sin copiar
  fichas de trabajadores a Fiscal;
- impuesto único y otras retenciones de Personas alimentan el cierre desde servidor y no desde
  valores inventados por el navegador;
- cierre, F29, expediente y pagos consultan el motor cuando está configurado; el fallback demo es
  explícito y un motor conectado sin datos muestra cero/vacío, nunca cifras sintéticas;
- las secciones conectadas son renderizadas dinámicamente para no congelar datos del build;
- el flujo completo fue probado con motor demo real: voucher importado, venta conciliada, resumen
  Personas, cierre recalculado y expediente actualizado.
