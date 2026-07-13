# Decisiones de producto — Completo Fiscal

## V1

- Completo Fiscal cubrirá el ciclo completo: cotización, emisión tributaria,
  facturación recurrente, cobranza, links de pago y conciliación bancaria.
- Incluirá precontabilidad verificable y explicada para el dueño, con paquete
  de cierre listo para revisión del contador.
- La emisión no se limitará comercialmente a 50 documentos como Nubox. Se
  diseñará una política de uso razonable que permita vender documentos
  tributarios ilimitados a pymes sin exponer la plataforma a abuso industrial.
- Comercialmente se ofrecerán documentos tributarios ilimitados, sin escalones
  visibles de 50, 100 o 500 documentos. El volumen industrial, integraciones
  abusivas o uso ajeno al giro normal de una pyme quedará sujeto a condiciones
  y precio empresarial.
- El certificado digital del primer año se incluirá únicamente cuando el
  cliente contrate y pague anticipadamente el paquete anual. En modalidad
  mensual, el certificado será adquirido por el cliente o cobrado aparte; en
  ambos casos quedará a su nombre y bajo su control.
- La conciliación bancaria V1 funcionará mediante importación de cartolas
  Excel, CSV u OFX. No habrá conexión directa con bancos ni integración Fintoc
  en el lanzamiento. El dominio interno conservará una interfaz de conectores
  para no bloquear una integración futura.
- Fiscal V1 incluirá cuentas por cobrar y un portal público de cobro mediante
  enlace seguro: documento, monto, vencimiento, datos bancarios del emisor,
  instrucciones y carga de comprobante. Completo no recibirá ni custodiará el
  dinero; conciliará posteriormente el pago con la cartola importada.
- La facturación recurrente creará borradores automáticamente como conducta
  predeterminada. La emisión tributaria automática deberá activarse de manera
  expresa por cliente y acuerdo recurrente, con límites, trazabilidad y opción
  de suspensión.
- Las cotizaciones tendrán un enlace público seguro para aceptar, rechazar o
  solicitar cambios. La aceptación quedará trazada y permitirá convertir el
  documento comercial en factura sin volver a ingresar sus datos.
- Fiscal V1 administrará cuentas por pagar derivadas de documentos recibidos:
  monto, vencimiento, pagos parciales, atraso y conciliación con cartolas
  importadas, sin alterar el XML tributario original.
- Fiscal V1 mostrará flujo de caja proyectado usando cuentas por cobrar,
  cuentas por pagar y movimientos conciliados de cartolas importadas. Se
  distinguirá visualmente de los saldos reales y permitirá anticipar semanas
  con déficit o excedente sin presentarse como información bancaria en línea.
- Fiscal V1 incluirá inventario básico integrado: catálogo, entradas por
  compras, salidas por ventas, ajustes trazables y alertas de stock. Bodegas
  avanzadas, producción, lotes y logística compleja quedarán para V2.
- Fiscal V1 incluirá órdenes de venta y mantendrá trazabilidad en el recorrido
  cotización → orden → guía de despacho → factura, permitiendo omitir etapas
  cuando el negocio no las necesite.
- Fiscal V1 incluirá órdenes de compra enviables al proveedor, vinculables con
  la factura recibida, sus pagos y la entrada correspondiente al inventario.
- Fiscal V1 tendrá aprobaciones internas simples y configurables por tipo de
  operación y monto. Una compra, pago o acción sensible podrá quedar pendiente
  del dueño o responsable autorizado, con identidad, fecha y decisión
  auditables.
- Fiscal V1 soportará múltiples sucursales por empresa, separando ventas,
  compras, caja e inventario por local y ofreciendo una vista consolidada. La
  configuración tributaria y los folios seguirán las reglas aplicables a cada
  emisor y sucursal.
- Una cuenta podrá administrar varios RUT únicamente cuando su plan incluya
  multiempresa. Cada empresa será un tenant fiscal aislado, aunque el usuario
  pueda cambiar entre ellas sin cerrar sesión.
- El contador podrá ser invitado sin costo como colaborador externo con acceso
  a revisión, exportaciones y observaciones. No podrá emitir documentos,
  aprobar pagos ni ejecutar acciones operativas salvo permisos expresos,
  acotados y auditables del dueño.
- Completo Fiscal se venderá como un producto funcionalmente completo, sin
  ocultar herramientas ni imponer cupos de documentos. El precio crecerá por
  estructura y costo real —RUT adicionales, sucursales, usuarios o uso
  intensivo de API— y no por bloquear artificialmente funciones esenciales.
- Fiscal V1 incluirá OCR con visión de bajo costo —inicialmente GPT-5.4 nano,
  sujeto a evaluación— para fotografías y PDF. La extracción será estructurada,
  validará RUT y sumas y requerirá confirmación ante baja confianza. El XML
  firmado seguirá siendo la fuente tributaria cuando exista. Se ofrecerá sin
  cupos visibles, bajo política de uso razonable.
- Las comunicaciones de cobranza V1 utilizarán correo y WhatsApp. Zavu será el
  proveedor inicial mediante un adaptador sustituible: correo como respaldo
  formal y WhatsApp como aviso rápido, sólo con consentimiento y plantillas
  permitidas. Los estados de entrega y fallos quedarán trazados; una caída del
  proveedor no afectará la emisión tributaria.
- La integración Zavu probada en RishteDar será el patrón donante para Fiscal:
  remitentes explícitos y separados por canal, plantillas WhatsApp `UTILITY`,
  normalización de teléfonos, escape de HTML, sandbox sin envíos reales,
  webhook HMAC que falla cerrado, idempotencia y verificación del estado final
  de entrega (nunca considerar `queued` como entrega confirmada). Se adaptará al
  modelo multi-tenant y no se copiarán secretos ni identidad de RishteDar.
- Incluir emisión masiva mediante Excel/CSV y una API pública, tenant-first e
  idempotente, para Gastro, POS e integraciones de terceros.
- Completo Personal no se considerará vendible hasta generar y validar el
  archivo Previred definitivo y la Declaración Jurada 1887, además del LRE ya
  implementado.
- Personal V1 tendrá aceptación interna trazable para liquidaciones, vacaciones
  y documentos cotidianos. Generará contratos y finiquitos, pero los actos que
  requieren formalidad especial terminarán mediante un flujo asistido en Mi DT.
  La firma electrónica certificada de un proveedor externo será una integración
  opcional posterior; Completo no presentará su aceptación interna como firma
  certificada ni como reemplazo de la ratificación legal.
- Personal V1 permitirá migrar trabajadores y reconstruir sus datos base desde
  archivos LRE y Previred, con validación, vista previa y confirmación antes de
  crear fichas o antecedentes laborales.
- El reloj de asistencia propio permanecerá como herramienta operacional de
  Gastro para turnos, atrasos, horas y planificación. No se venderá ni
  comunicará como sistema electrónico autorizado por la DT. Una certificación
  bajo la Resolución Exenta N°38 sólo se reconsiderará en una versión futura si
  la demanda y los ingresos justifican su auditoría externa y renovación.
- Toda pantalla nueva debe salir con ayuda contextual en lenguaje simple. Los
  recorridos de policía validarán que no herede silenciosamente la guía de
  Inicio; los portales públicos tendrán su ayuda integrada en la misma página.

## V2

- Incorporar contabilidad formal: plan de cuentas, comprobantes y asientos,
  libro diario, libro mayor, balances, estados financieros y procesos
  contables relacionados.
- Incorporar cesión de facturas y los flujos de factoring/AEC relacionados,
  después de estabilizar y certificar el núcleo tributario de la V1.
- Mantener una experiencia simple para el dueño y una vista profesional
  separada para contador, sin convertir el lenguaje contable en requisito de
  uso cotidiano.
