# Policía obsesiva del sandbox

Esta pasada simula a una persona insistente que recorre Completo Fiscal de punta a punta. Abre todas las pantallas, comprueba cada enlace interno, aprieta todos los botones habilitados y exige que cada acción cambie la interfaz, navegue, valide un formulario o haga una solicitud útil.

Además ejecuta los flujos completos: boletas 39/41, facturas 33/34, notas 56/61, las cinco variantes de guía 52, recepción y decisión de XML, maestros, recurrencia, portales públicos, comprobantes y los cuatro desenlaces de certificación. Después recarga para comprobar persistencia y ensaya doble envío para verificar idempotencia.

## Cinturón de seguridad

La policía se ejecuta con `FISCAL_RUNTIME_MODE=demo` y una URL de motor deliberadamente inválida. El runtime ignora toda credencial de motor en modo demo. La prueba falla ante cualquier request a `sii.cl`, respuesta 4xx/5xx, error de consola, ruta huérfana o botón silencioso. No consume CAF, certificado ni folios reales.

## Ejecución

Desde `fiscal-console`:

```powershell
npm run test:police:obsessive
```

La suite normal continúa cubriendo responsive, accesibilidad y recorridos específicos. Esta pasada es más lenta y se ejecuta una vez en Chromium de escritorio para evitar repetir el mismo censo en cada dispositivo.

## Criterio de cierre

El resultado aceptable es cero llamadas SII, cero errores HTTP o de consola, cero rutas rotas, cero botones silenciosos y todos los escenarios verdes. Un hallazgo se corrige y la pasada completa vuelve a ejecutarse; no se acepta como excepción visual.
