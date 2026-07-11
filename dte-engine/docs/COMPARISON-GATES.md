# Compuertas comparativas

LibreDTE se usa sólo como segunda implementación para encontrar omisiones. No se
importa, enlaza ni copia código o fixtures AGPL al producto. La autoridad se resuelve
siempre en este orden: documentación, XSD y certificación SII; consulta formal al SII;
y finalmente LibreDTE como referencia secundaria.

## Al cerrar una familia documental

1. Generar casos sintéticos propios desde la documentación oficial.
2. Validar XSD, TED y XMLDSig con implementaciones independientes.
3. Ejecutar los casos equivalentes en el contenedor aislado de LibreDTE.
4. Comparar semánticamente tipos, totales, referencias, rangos y estados; nunca bytes.
5. Registrar commit, fuentes, hashes, diferencias y la decisión adoptada.

El baseline fijado vive en `comparison/baseline.json`. Antes de comparar:

```powershell
python scripts/check_reference_baseline.py `
  --libredte-path C:\ruta\al\clone\aislado
```

Un HEAD diferente o un árbol modificado detiene la compuerta. Los cambios remotos se
informan y revisan; nunca actualizan automáticamente el baseline.
