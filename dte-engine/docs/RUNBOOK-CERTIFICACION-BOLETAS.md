# Runbook — certificación de boletas

## Antes de descargar el CAF

El cockpit debe mostrar verdes motor, ensayo de cinco folios, consulta HTTPS,
certificado en vault y respaldo/restauración. El CAF real permanece bloqueado mientras
exista cualquier control pendiente. Ejecutar los cuatro escenarios offline y conservar
sus hashes.

## Ventana real de 24 horas

1. Crear respaldo verificado y registrar operador/hora.
2. Descargar una sola vez el CAF de cinco folios.
3. Importarlo por el canal privado y comprobar RUT, tipo 39, rango y FRMA.
4. Generar los cinco casos asignados, validar XSD/TED/XMLDSig y representación.
5. Construir un solo `EnvioBOLETA` y el RCOF del mismo día.
6. Subir el sobre, registrar Track ID y después subir el RCOF.
7. Reconciliar ambos hasta estado terminal y guardar el paquete de evidencia.
8. Solicitar revisión al SII informando el Track ID correcto.

## Timeout después del upload

Nunca reenviar inmediatamente. Marcar `unknown`, conservar request/hash/hora y consultar
estado con el identificador disponible. Sólo un diagnóstico inequívoco de “no recibido”
autoriza un nuevo intento. No reservar ni emitir folios sustitutos.

## Rechazo del sobre

Conservar XML y respuesta originales. Clasificar si el rechazo es de carátula, schema,
firma, TED o datos del set; corregir código/configuración y generar una nueva evidencia.
No editar un XML firmado ni reutilizar su identificador con contenido diferente.

## Rechazo del RCOF

No reenviar boletas aceptadas. Comparar fecha, folios utilizados, totales y secuencia;
corregir únicamente el resumen y reconciliarlo de manera independiente.

## Detención obligatoria

Detener la ventana ante folios duplicados, firma no verificable, RUT cruzado, respaldo
inválido, consulta pública caída o imposibilidad de distinguir certificación y producción.
No improvisar envíos manuales fuera del ledger.
