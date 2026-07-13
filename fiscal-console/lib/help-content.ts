export type HelpGuide = {
  summary: string;
  steps: string[];
  examples: { q: string; a: string }[];
};

const guide = (summary: string, steps: string[], q: string, a: string): HelpGuide => ({ summary, steps, examples: [{ q, a }] });

export const FISCAL_HELP: Record<string, HelpGuide> = {
  recurrencia: guide("Administra cobros mensuales sin emitir automáticamente.", ["Crea el acuerdo y fija cliente, concepto, monto y día.", "El worker genera un borrador idempotente.", "Revisa el borrador antes de convertirlo en DTE."], "¿Puede emitir una factura sin que yo la vea?", "No por defecto. Cada período genera un borrador revisable; la emisión automática requeriría una activación expresa y controles adicionales."),
  ventas_nueva: guide("Crea una propuesta comercial sin efecto tributario.", ["Identifica al cliente.", "Agrega concepto y monto.", "Guarda y luego comparte el enlace de aceptación."], "¿Esto consume un folio?", "No. Cotizaciones y órdenes son comerciales; el folio se consume sólo al emitir el DTE."),
  compras_nueva: guide("Crea una orden y déjala lista para aprobación.", ["Selecciona proveedor y concepto.", "Indica el monto comprometido.", "Si supera el límite, espera la aprobación antes de continuar."], "¿La orden prueba que ya pagué?", "No. La recepción, factura y pago se relacionan después como eventos separados."),
  inventario_movimiento: guide("Registra una entrada, salida o ajuste con causa.", ["Elige producto y sucursal.", "Selecciona el tipo correcto.", "Escribe el documento o motivo de respaldo."], "¿Puedo usar esto para trasladar?", "No manualmente. Usa Control de stock para que salida y entrada se creen juntas."),
  inventario_control: guide("Configura mínimos y traslados pareados.", ["Define un mínimo por producto y sucursal.", "Para trasladar, señala origen, destino y cantidad.", "Completo bloquea faltantes y registra ambos movimientos atómicamente."], "¿Qué pasa si falla la entrada del destino?", "No se registra tampoco la salida: el traslado es una sola operación."),
  caja_importar: guide("Prepara una cartola para conciliación sin conectarte al banco.", ["Carga CSV, Excel u OFX compatible.", "Revisa columnas, fechas y montos.", "Confirma sólo después de validar la vista previa."], "¿Completo ve mi cuenta bancaria?", "No. En V1 tú importas el archivo; no existe conexión bancaria directa."),
  caja_obligacion: guide("Registra una cuenta por cobrar o pagar.", ["Elige dirección: cobrar o pagar.", "Relaciona contraparte y documento de origen.", "Define monto y vencimiento."], "¿Esto mueve dinero?", "No. Sólo organiza el compromiso y su seguimiento."),
  caja_pago: guide("Aplica un pago total o parcial a una cuenta existente.", ["Indica la cuenta correcta.", "Registra monto, fecha y respaldo.", "Completo recalcula el saldo y rechaza sobrepagos."], "¿Un comprobante marca automáticamente como pagado?", "No. El comprobante queda pendiente de revisión antes de aplicar el pago."),
  emitir_boleta: guide("Registra una venta a consumidor final como boleta afecta o exenta.", ["Ingresa productos y precios finales.", "Revisa la clasificación tributaria.", "Confirma sólo cuando el total sea correcto."], "¿Puedo editarla después?", "No después de emitir. Cualquier corrección se hace mediante el documento tributario correspondiente."),
  emitir_factura: guide("Emite una factura nominativa con receptor y condiciones de pago.", ["Valida RUT y razón social.", "Confirma neto, IVA y exentos.", "Revisa vencimiento antes de firmar."], "¿Qué ocurre si el cliente está mal?", "Detén la emisión. Si ya fue emitida, corresponde una corrección tributaria, no editar el XML."),
  emitir_correccion: guide("Anula o corrige un DTE mediante nota de crédito o débito.", ["Selecciona el documento original.", "Escoge el efecto legal correcto.", "Revisa montos y referencias antes de emitir."], "¿Se borra el documento original?", "Nunca. La nota queda vinculada y ambos permanecen en la historia."),
  emitir_guia: guide("Respalda despachos, traslados y devoluciones.", ["Indica motivo y receptor o destino.", "Agrega transporte cuando corresponda.", "Verifica si la guía valoriza o no el movimiento."], "¿Una guía siempre es una venta?", "No. Puede respaldar movimientos internos, devoluciones o consignaciones sin venta."),
  aprobaciones: guide("Decisiones internas para operaciones sensibles.", ["Revisa operación y monto.", "Confirma que tienes el rol requerido.", "Aprueba o rechaza indicando el motivo."], "¿Se puede aprobar dos veces?", "No. La primera decisión queda cerrada e identificada; cualquier cambio requiere una nueva operación."),
  ventas: guide("Cotizaciones y órdenes antes de emitir un DTE.", ["Envía la propuesta al cliente.", "Registra aceptación o cambios.", "Convierte sólo al confirmar."], "¿La cotización usa folio SII?", "No. El folio se consume únicamente al emitir el documento tributario."),
  compras: guide("Solicitudes trazables desde aprobación hasta pago.", ["Crea la orden.", "Obtén aprobación si supera el límite.", "Relaciona recepción, factura y pago."], "¿Puedo pagar sin aprobación?", "No cuando la regla del negocio exige autorización; el intento queda bloqueado y trazado."),
  inventario: guide("Existencias explicadas mediante movimientos.", ["Las compras generan entradas.", "Ventas y traslados generan salidas.", "Un ajuste exige motivo y responsable."], "¿Puedo cambiar el saldo directamente?", "No. Se registra un movimiento compensatorio para no borrar historia."),
  caja: guide("Proyecta cobros y pagos por vencimiento.", ["Revisa cuentas abiertas.", "Importa y concilia cartolas.", "Atiende semanas con saldo proyectado negativo."], "¿Es el saldo de mi banco?", "No. Es una proyección basada en obligaciones registradas y la última evidencia conciliada."),
  inicio: guide("Resume lo urgente de tu operación fiscal.", ["Revisa alertas y estados.", "Usa los accesos rápidos para emitir o resolver pendientes."], "¿Por dónde parto?", "Abre primero cualquier tarjeta marcada para revisar."),
  emitir: guide("Eliges la intención y Completo determina el documento.", ["Venta a consumidor: boleta 39/41.", "Venta a empresa: factura 33/34.", "Corrección: nota 56/61.", "Traslado: guía 52."], "¿Tengo que saber el código?", "No. El asistente lo elige según lo que necesitas hacer."),
  documentos: guide("Historial inmutable de documentos emitidos.", ["Filtra por estado.", "Abre el detalle para XML, PDF y eventos.", "Para anular o corregir una boleta usa una nota; nunca borres el original."], "Me equivoqué en una boleta", "Ábrela y usa el flujo de corrección; no se edita el XML original."),
  documentos_detalle: guide("Explica un documento emitido y toda su historia.", ["Confirma receptor, montos y estado SII.", "Revisa eventos antes de repetir una acción.", "Descarga XML o PDF sólo como representación del documento conservado."], "¿Puedo cambiar algo desde aquí?", "No se reescribe un DTE emitido. Usa una nota de crédito o débito cuando corresponda."),
  recibidos: guide("Bandeja de facturas y notas recibidas.", ["Importa el XML, no sólo el PDF.", "Revisa emisor, monto y plazo.", "Acepta o reclama dejando trazabilidad."], "Sólo tengo el PDF", "Pídeles el XML; el PDF sirve de apoyo, no reemplaza la evidencia tributaria."),
  recibidos_detalle: guide("Revisa la evidencia antes de aceptar o reclamar una compra.", ["Compara proveedor, folio, fechas y totales con lo recibido.", "Verifica la firma y el XML original.", "Registra una decisión sólo cuando tengas respaldo."], "¿Aceptar significa pagar?", "No. La aceptación tributaria y el pago son procesos distintos y ambos quedan trazados."),
  clientes: guide("Antecedentes frecuentes para facturar.", ["Guarda RUT, razón social, giro, dirección y correo.", "Confirma antes de emitir."], "¿Puedo cambiar el cliente después?", "No en un DTE emitido; corresponde corregirlo documentalmente."),
  proveedores: guide("Ordena compras y diferencias por proveedor.", ["Asocia XML recibidos.", "Revisa documentos que sólo aparecen en RCV."], "Veo una compra que no reconozco", "No la uses como crédito fiscal; revísala y reclama si corresponde."),
  productos: guide("Catálogo con tributación y precio consistente.", ["Define afecto o exento.", "Boletas usan precio final; facturas pueden trabajar con neto."], "¿Quién decide el IVA?", "La clasificación guardada del producto, no quien cobra en caja."),
  folios: guide("Controla CAF, rangos y folios disponibles.", ["Vigila alertas de agotamiento.", "Nunca reutilices un folio consumido.", "CAF y claves privadas viven sólo en backend/vault."], "¿Puedo subir el CAF ahora?", "Sólo cuando certificado, respaldo y compuerta estén verdes."),
  envios: guide("Sigue sobres y Track ID enviados al SII.", ["Submitted no significa aceptado.", "Unknown exige consultar antes de reenviar.", "Nunca dupliques un sobre por timeout."], "Se cortó internet después de enviar", "Déjalo en unknown y reconcilia con el SII; no reenvíes a ciegas."),
  reportes: guide("Exporta ventas, compras y paquete para contador.", ["Elige período.", "Descarga CSV/XLSX/PDF o ZIP verificable.", "Conserva el hash del paquete."], "¿El reporte reemplaza al contador?", "No; reduce reconstrucción y deja la revisión preparada."),
  cierre: guide("Calcula y versiona el mes sin presentar el F29.", ["Completa documentos, RCV, BHE, Personas y pagos aplicables.", "Resuelve diferencias.", "Recalcula y congela la versión revisada."], "Cambió una compra atrasada", "Recalcula: se crea una nueva versión y la anterior permanece."),
  expediente: guide("Carpeta verificable de toda la evidencia del mes.", ["Disponible significa que existe fuente versionada.", "Falta versión bloquea el cierre.", "No conectado no bloquea si el módulo no aplica."], "¿Por qué no puedo descargar?", "Existe al menos una evidencia obligatoria pendiente."),
  pagos: guide("Concilia vouchers, ventas y respaldo fiscal.", ["Importa desde POS/proveedor.", "Relaciona cada voucher con una venta.", "Aplica always_issue o voucher_as_boleta según el tenant."], "¿Tarjeta siempre genera boleta?", "Depende del modelo autorizado/configurado; Completo evita duplicarla."),
  rcv: guide("Compara XML propios con el Registro de Compras y Ventas.", ["Importa un snapshot.", "Revisa coincidencias y diferencias.", "No corrijas automáticamente una diferencia."], "Aparece sólo en el SII", "Consigue el XML o clasifica la causa antes de usarla."),
  f29: guide("Propuesta explicada del impuesto mensual.", ["Compara cálculo Completo y propuesta SII.", "Abre diferencias por código.", "Recuerda: esta pantalla no presenta ni paga."], "¿Este monto ya fue declarado?", "No. Es informativo hasta realizar la presentación autorizada."),
  bhe: guide("Boletas de honorarios emitidas y recibidas.", ["Consulta el período.", "Revisa bruto, retención y líquido.", "La retención alimenta el cierre/F29."], "¿Honorarios de Plus es lo mismo?", "No; aquí son BHE del negocio, no cobros del estudio contable."),
  situacion: guide("Perfil y estado tributario consultado.", ["Revisa régimen, actividades y direcciones.", "Confirma cambios antes de configurar emisión."], "¿Puedo editar el SII desde aquí?", "No. Inicialmente es consulta y apoyo de onboarding."),
  sincronizaciones: guide("Historial de lecturas al SII.", ["Cada consulta crea una versión.", "Revisa fecha, resultado y hash.", "Un cambio del portal puede requerir intervención."], "¿Por qué no actualiza?", "Revisa el diagnóstico; no repetimos indefinidamente una sesión fallida."),
  certificacion: guide("Prepara y ensaya la certificación sin gastar CAF real.", ["Exige motor, portal HTTPS, certificado y respaldo.", "Ensaya cinco folios y fallas.", "Descarga el CAF real sólo con toda la compuerta verde."], "¿Cuándo empiezan las 24 horas?", "Cuando descargues los cinco folios reales del set."),
  configuracion: guide("Onboarding y secretos del emisor.", ["Completa datos tributarios.", "Activa sólo módulos contratados.", "Certificado, claves y CAF nunca llegan al navegador."], "¿Cada restaurante usa mi certificado?", "No. Cada contribuyente utiliza su autorización y credenciales propias."),
};

export const HELP_ROUTE_KEYS: Record<string,string> = {
  "/ventas/nueva":"ventas_nueva", "/compras/nueva":"compras_nueva",
  "/inventario/movimiento":"inventario_movimiento", "/inventario/control":"inventario_control",
  "/caja/importar":"caja_importar", "/caja/obligacion":"caja_obligacion", "/caja/pago":"caja_pago",
  "/emitir/boleta":"emitir_boleta", "/emitir/factura":"emitir_factura",
  "/emitir/correccion":"emitir_correccion", "/emitir/guia":"emitir_guia",
};

export function helpKeyForPath(pathname:string):string {
  const exact=HELP_ROUTE_KEYS[pathname];
  if(exact)return exact;
  if(pathname.startsWith("/documentos/"))return "documentos_detalle";
  if(pathname.startsWith("/recibidos/"))return "recibidos_detalle";
  const root=pathname==="/"?"inicio":pathname.split("/")[1]||"inicio";
  return FISCAL_HELP[root]?root:"inicio";
}
