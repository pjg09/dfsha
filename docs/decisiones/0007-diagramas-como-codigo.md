# 0007 · Diagramas como código, con Mermaid por defecto

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §4.1 (diagramas de componentes y de despliegue), §4.3 (diagramas legibles), §5.3; aclaración A3

## Contexto
La fase I exige diagramas legibles en un PDF (A3), y el informe final y la defensa de la fase II también
los necesitan. Los diagramas viven en `docs/diagramas/`, una carpeta común a todos los documentos, y
tienen que usar los mismos nombres que el código y los logs (ADR 0003).

## Opciones consideradas
1. **Herramienta gráfica (draw.io).** Total libertad de disposición, pero su XML no se puede revisar en
   un diff y los nombres se desincronizan del código sin que nadie lo note.
2. **Mermaid.** Es texto, GitHub lo muestra y cubre secuencia, flujo, estados y clases. No tiene un
   diagrama de despliegue UML propiamente dicho y deja poco control sobre la disposición.
3. **PlantUML.** Tiene UML completo, despliegue incluido, pero necesita Java o un servidor para exportar.

## Decisión
Mermaid por defecto: fuente `.mmd` en `docs/diagramas/` y exportación a SVG con `mermaid-cli` para el PDF.
**No es una restricción.** Si un diagrama sale mejor con otra herramienta (PlantUML, draw.io, Graphviz…),
se instala y se usa. Lo que importa es que el diagrama sea correcto y legible. La convención de nombres
`NN-nombre.<ext>` (`convenciones.md` §2) se aplica a cualquier herramienta, y la fuente editable se
versiona siempre junto a su exportación.

## Consecuencias
- Los cambios en los diagramas se revisan en un diff, igual que el código.
- **Límite:** Mermaid controla mal la disposición de los diagramas densos. El de despliegue es el
  candidato más probable a usar otra herramienta.
- **Pendiente:** fijar la versión de `mermaid-cli` cuando se instale.
