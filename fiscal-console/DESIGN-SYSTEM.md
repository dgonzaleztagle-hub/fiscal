# Sistema visual Completo

Este dashboard es la referencia visual para Completo Fiscal y la futura renovación de
Completo Gastro. La estructura es compartida; cada producto cambia contenido y densidad,
no la gramática de interfaz.

## Paleta maestra

- Navy `#1B2A4A`: marca, navegación y acciones primarias.
- Gold `#F2B705`: selección, progreso y detalles de alta recordación; nunca superficies
  extensas ni texto pequeño sobre blanco.
- Cream `#FAF8F5`: lienzo cálido común al ecosistema.
- White `#FFFFFF`: tarjetas y superficies de trabajo.

Los estados conservan colores independientes: verde para éxito, ámbar para espera,
coral para atención/error y azul para información. El color de marca no debe ocultar
el significado operacional.

Los valores portables viven en `app/design-tokens.css`. Gastro debe consumir esos tokens
antes de migrar componentes para evitar volver a dispersar colores en estilos locales.

## Reglas de aplicación

1. El amarillo ocupa menos del 10% del viewport y funciona como firma, no como relleno.
2. Las acciones principales son navy; el amarillo marca selección, progreso y foco.
3. Sidebar navy, lienzo cream y tarjetas blancas forman el shell común.
4. Espaciado, radios, sombras, tablas, filtros y estados se comparten entre productos.
5. Fiscal usa lenguaje más sobrio; Gastro puede usar fotografía y contenido cálido sin
   alterar navegación, jerarquía o comportamiento responsive.
6. Ninguna pantalla nueva define hexadecimales propios salvo un estado documentado.
