# 0034 · Documento de la fase I en Markdown y figuras exportadas a PNG

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §4.1 (diagramas de componentes y de despliegue), §4.3 (documento con diagramas legibles y referencias), §5.3; aclaraciones A3 y A4; sustituye al ADR 0007

## Contexto
El usuario decidió cómo se construye el documento de la fase I:
- todo en un solo archivo, `docs/fase-1.md`, escrito de una vez y listo para pasarlo a Word y de ahí a PDF (A3);
- las referencias aparte, en `docs/referencias.md`;
- citas en formato IEEE.

Hay dos cosas que contradicen lo vigente:
- `CONTRIBUTING.md` y `convenciones.md` situaban el documento en un directorio, `docs/fase-1/`.
- El ADR 0007 fijaba que los diagramas se exportan a SVG. Al generar las figuras se comprobó que `mermaid-cli` escribe el texto de los SVG dentro de `foreignObject`, que Word no suele mostrar. El riesgo es que una figura aparezca sin texto en el PDF sin que nadie lo note.

Además, el ADR 0007 dejaba pendiente fijar la versión de `mermaid-cli`. Por otro lado, la figura de partición (`04-particion`) no salió legible con Mermaid, porque no deja controlar la disposición.

## Opciones consideradas
**Ubicación del documento:**
1. **Directorio `docs/fase-1/`**, como decían las convenciones. Solo tendría sentido con varios archivos.
2. **Un archivo `docs/fase-1.md`** y otro `docs/referencias.md`, como pidió el usuario.

**Formato de exportación de las figuras:**
- **a) SVG.** Es vectorial, pero el texto puede desaparecer al insertarlo en Word.
- **b) PNG a escala 2.** Se ve igual en todas partes, y con escala 2 se lee bien impreso.

## Decisión
Opción 2 y formato b.

**Documento:**
- `docs/fase-1.md` es el documento de la fase I. Los encabezados Markdown son los títulos, y las tablas van en el propio documento.
- Las tablas llevan el título encima y las figuras debajo, numeradas en orden, como en IEEE.
- Cada figura tiene en el texto una marca visible (🟥 **[ INSERTAR AQUÍ LA FIGURA N ]**) con el nombre de su archivo, y los datos de la portada van con marcas `[[COMPLETAR: …]]`.
- `docs/referencias.md` reúne todas las fuentes usadas, en formato IEEE y con la misma numeración que el documento. De cada fuente dice dónde se cita y cómo se comprobó, y también incluye las consultadas que no se citan.
- Para pasarlo a Word sin perder las tablas se convierte con Pandoc o desde una vista previa de Markdown, nunca pegando el texto en bruto.

**Figuras** (sustituye al ADR 0007):
- **Herramienta.** Mermaid por defecto, con la fuente `.mmd` en `docs/diagramas/`. No es una restricción: si una figura sale mejor con otra herramienta, se usa. `04-particion` y `03-despliegue` se hacen en HTML y se convierten a PNG con Chrome en modo headless, porque Mermaid no deja controlar su disposición.
- **Exportación.** La exportación entregable es **PNG a escala 2 con fondo blanco**. No se entregan SVG.
- **Versión.** `@mermaid-js/mermaid-cli` 12.0.0, con el Chrome del sistema y la configuración común `docs/diagramas/mermaid-config.json`: tema neutro, apto para imprimir, y letra de 18 px.
- **Archivos.** La convención `NN-nombre.<ext>` vale para cualquier herramienta, y la fuente editable se versiona siempre junto a su exportación. En las figuras del documento de la fase I, `NN` coincide con el número de la figura.
- **Legibilidad.** Se prefiere la disposición vertical. Una figura muy ancha queda con la letra ilegible al ajustarla al ancho de la página.

## Consecuencias
- **Se gana:**
  - Las figuras se ven igual en Word, en el PDF y en GitHub.
  - Las fuentes siguen siendo texto y se revisan en un diff.
  - Las referencias se pueden comprobar una a una.
- **Se pierde:**
  - El PNG no es vectorial y pesa más que el SVG.
  - Cambiar una figura obliga a volver a exportarla.
  - Pasar el documento a Word necesita Pandoc o una vista previa, porque pegar el Markdown en bruto rompe las tablas.
- **Cambia la convención:**
  - En `CONTRIBUTING.md` y `convenciones.md`, el documento de la fase I pasa a ser `docs/fase-1.md`, y aparece `docs/referencias.md`.
  - La fila de diagramas especifica la exportación a PNG.
  - El informe de la fase II mantiene su ubicación hasta que se decida su formato.
