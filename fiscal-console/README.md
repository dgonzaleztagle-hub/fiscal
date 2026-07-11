# Completo Fiscal Console

Consola única para el producto autónomo y su integración posterior con Completo
Restaurantes. La aplicación no recibe PFX, contraseñas, claves CAF ni credenciales SII;
todo material privado se resuelve en el backend.

```powershell
cd ..\dte-engine
python scripts\export_openapi.py build\openapi.json
cd ..\fiscal-console
npm run generate:api
npm run dev
```

El modo demo usa datos sintéticos y conserva un indicador visible para evitar confundirlo
con certificación o producción.

Para leer documentos del motor local sin exponer el token al navegador:

```powershell
$env:FISCAL_API_URL="http://127.0.0.1:8000"
$env:FISCAL_API_TOKEN="token-sintetico-local"
npm run dev
```

Estas variables son sólo de servidor. Si faltan o el motor no responde en cuatro segundos,
la tabla vuelve a datos demo y lo declara visualmente.
