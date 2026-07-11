# Completo SII Reader

Worker aislado de solo lectura. Inicia una sesión autorizada por tenant, consulta recursos
del SII y produce snapshots inmutables para el motor/consola. No contiene lógica de emisión.

## Primera entrega

1. Contratos tipados de snapshot y ejecución.
2. Vault como interfaz; ninguna contraseña en configuración o payload HTTP.
3. RCV como primer recurso conectado.
4. F29, BHE, F22 y perfil tributario sobre la misma sesión efímera.
5. Intervención humana ante CAPTCHA o autenticación adicional.

El código legacy es referencia de discovery. No se copiarán credenciales, DOM/JSON reales,
técnicas de evasión ni el servidor Flask original.
