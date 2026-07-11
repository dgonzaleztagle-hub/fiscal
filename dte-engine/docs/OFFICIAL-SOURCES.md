# Fuentes normativas verificadas

Descarga realizada el 2026-07-08. Los archivos PDF no se versionan en el repositorio;
los hashes permiten detectar reemplazos silenciosos en el sitio del SII.

| Documento | URL | SHA-256 |
|---|---|---|
| Formato DTE 2.5 (2026-02) | https://www.sii.cl/factura_electronica/factura_mercado/formato_dte_202602.pdf | `D4E3CC80A0AF9E821B097CA581FC58AC2B9A62E57778B5C5D65D68D6418FBAD4` |
| Validaciones DTE (2026-06) | https://www.sii.cl/servicios_online/docs/instructivo_sobre_validaciones_dte.pdf | `50E5B92321E0C5FAB2051CB1D0BD3739193C4CA81321F9DC695BFD28F5E3A41C` |
| Instructivo emisión boleta | https://www.sii.cl/factura_electronica/factura_mercado/Instructivo_Emision_Boleta_Elect.pdf | `0B1588115EF00862D4025BB7565FA0B06E5166463379E90104AC8E6FABA1FBB0` |
| Instructivo emisión DTE | https://www.sii.cl/factura_electronica/factura_mercado/instructivo_emision.pdf | `D8F6DA7DE906830D23ACE311E72C37298ED5C1B518F541814D75811B0C57A5C7` |
| Formato boleta 4.2 (2025-09-08) | https://www.sii.cl/factura_electronica/factura_mercado/formato_boleta_electronica.pdf | Pendiente de archivar |
| Paquete XSD EnvioBOLETA | https://www.sii.cl/servicios_online/docs/xml/schema_envio_bol.zip | `CD9BBB1297CF9C6E6CB887F4D1686C91C8476E8C01AFAAFC5D0948F48BEC044D` |
| Paquete XSD DTE | https://www.sii.cl/servicios_online/docs/xml/schema_dte.zip | `FB1C77D9152AB60F0A91107929307B6CBBF01EFF39B26B0A9F79EE9795234357` |

## Paquete DTE fijado — 2026-07-10

Los cuatro archivos exigidos por el SII para validar `EnvioDTE` se conservan en
`src/completo_dte/resources/sii/schema_dte_v10/`, junto con su procedencia:

- `DTE_v10.xsd`: `7D34C27956F1A22692C334D407F8B04F1FDF39BF1C39941F636BD8BB169E9110`;
- `EnvioDTE_v10.xsd`: `33EA8DD38C895C359DDDBCD21FEB5ACF8A4717F7F67524A6B0DD9A83D76920EB`;
- `SiiTypes_v10.xsd`: `7A76C185045ABED4CECBC4EEF5328895B3D85AEEDD4F4BF4BECE5BB8ED7C8008`;
- `xmldsignature_v10.xsd`: `427E3225CD379AE92BAE464B892DBF964665AF92D453AC61774CFFAB38B95EDB`.

Facturas 33/34, líneas mixtas, ajustes de detalle y sobres firmados validan sin
transformaciones de compatibilidad contra estos originales.

## Paquete XSD oficial localizado

El 2026-07-09 se localizó el enlace vigente desde la página oficial
`https://www.sii.cl/servicios_online/1039-formato_xml-1184.html`. El ZIP contiene:

- `EnvioBOLETA_v11.xsd`, SHA-256
  `FFD30D054E7736C88EFF090993A1470B91C940D99C7371C0795A366BD858C12A`;
- `xmldsignature_v10.xsd`.

El XSD oficial no puede cargarse directamente con libxml2 moderno: en
`DescuentoPct` deriva de `PctType`, cuyo mínimo es `0.01`, y vuelve a declarar un mínimo
`0.00`. XML Schema prohíbe relajar una restricción heredada. Para comprobar el resto del
documento se generó una copia temporal de compatibilidad cambiando exclusivamente ese
valor a `0.01`, SHA-256
`1853487826B1A1318D287CC08F7294BC8FC23C2E5C3A7C817473BDCC89CC6A91`.
El `EnvioBOLETA` del motor validó contra esa copia. El original oficial se conserva como
fuente de verdad y la transformación no debe hacerse silenciosamente en producción.

## API de boleta

La documentación Swagger de certificación se publica en
`https://www4c.sii.cl/bolcoreinternetui/api/`. El 2026-07-09 se verificó la versión
1.0.5 y sus operaciones de semilla, token, envío y consulta por Track ID. El gateway
implementado usa exclusivamente esas rutas en certificación/producción.

El RCOF utiliza la vía DTE heredada publicada por el SII: `CrSeed`,
`GetTokenFromSeed`, multipart `DTEUpload` y consulta `QueryEstUp`. Se mantiene en un
adaptador distinto para no mezclar protocolos ni tokens.

## Validación histórica de referencia

Para evitar avanzar a ciegas mientras el enlace oficial de schemas devuelve 404, se
consultaron como referencia los archivos públicos de LibreDTE:

- `EnvioBOLETA_v11.xsd`, SHA-256
  `DAF4DE535A50F91CBBE91854F811B0C89375A7DF5E04B5A89FE624120F6F1E00`.
- `xmldsignature_v10.xsd`, SHA-256
  `427E3225CD379AE92BAE464B892DBF964665AF92D453AC61774CFFAB38B95EDB`.

No se agregaron esos archivos al repositorio ni como dependencia. El `EnvioBOLETA`
sintético generado por este motor validó contra ese schema sin errores. La comprobación
ya se repitió con el paquete oficial usando la compatibilidad documentada arriba.

La revisión comparativa encontró certificados históricos asociados a IDK 100 y 300 en el
repositorio de referencia. No se incorporaron porque aún falta confirmar una fuente
oficial del SII. El trust store del motor ya permite cargarlos por configuración,
verificar su fingerprint y rechazar sustituciones o IDK desconocidos.
