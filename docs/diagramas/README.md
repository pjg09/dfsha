# Diagramas

Fuentes y exportaciones de las figuras de los documentos del proyecto. Las reglas están en el
[ADR 0034](../decisiones/0034-documento-de-la-fase-1-y-figuras.md):
- La fuente editable se versiona junto a su exportación.
- Lo que se entrega es un **PNG a escala 2 con fondo blanco**.
- En las figuras de la fase I, `NN` es el número de la figura en [`fase-1.md`](../fase-1.md).

## Catálogo

| Fig. | Archivo | Herramienta | Sección de `fase-1.md` |
|---|---|---|---|
| 1 | `01-casos-de-uso` | Mermaid | §2.4 |
| 2 | `02-componentes` | Mermaid | §3.1 |
| 3 | `03-despliegue` | HTML | §3.6 |
| 4 | `04-particion` | HTML | §4.1 |
| 5 | `05-modelo-metadatos-parte-1` y `-parte-2` (dos imágenes, un solo título) | Mermaid | §4.2 |
| 6 | `06-secuencia-carga` | Mermaid | §6.1 |
| 7 | `07-secuencia-lectura` | Mermaid | §6.2 |
| 8 | `08-secuencia-escritura` | Mermaid | §6.3 |
| 9 | `09-secuencia-borrado` | Mermaid | §6.4 |
| 10 | `10-estados-escritura` | Mermaid | §8.4 |
| 11 | `11-replica-corrupta` | Mermaid | §8.5 |
| 12 | `12-estados-nodo` | Mermaid | §9.2 |
| 13 | `13-modo-seguro` | Mermaid | §9.5 |
| 14 | `14-seguridad` | Mermaid | §10 |
| 15 | `15-escenario-concurrencia` | Mermaid | §11.1 |
| 16 | `16-escenario-replica` | Mermaid | §11.2 |
| 17 | `17-escenario-fallo-parcial` | Mermaid | §11.3 |
| 18 | `18-escenario-descubrimiento` | Mermaid | §11.4 |

`mermaid-config.json` es la configuración común de todas las figuras Mermaid: tema neutro, apto para
imprimir, y letra de 18 px.

## Criterios
- **Cada figura cabe en una página** con la letra legible: alto/ancho ≤ 1,38 (página carta; 1,55 en A4).
  Si no cabe, primero se reorganiza y, si no basta, se parte en varias imágenes con un solo título,
  como la Figura 5.
- **Disposición vertical** siempre que se pueda: una figura muy ancha queda con la letra ilegible al
  ajustarla al ancho de la página.
- **Revisar el PNG** después de exportarlo: texto cortado, cajas desordenadas o huecos vacíos.
- **No cambiar la numeración.** Si cambia una figura, se sustituye su PNG con el mismo nombre.

## Cómo exportar

Las herramientas no se versionan: se instalan en un directorio temporal y usan el Chrome del sistema
(`/usr/bin/google-chrome`).

**Mermaid** (`@mermaid-js/mermaid-cli` 12.0.0):

```bash
T=$(mktemp -d) && cd "$T"
PUPPETEER_SKIP_DOWNLOAD=1 npm install --no-audit --no-fund @mermaid-js/mermaid-cli@12.0.0
printf '{"executablePath":"/usr/bin/google-chrome","args":["--no-sandbox"]}' > puppeteer.json
cd -   # volver a docs/diagramas
"$T/node_modules/.bin/mmdc" -p "$T/puppeteer.json" -c mermaid-config.json \
  -i 06-secuencia-carga.mmd -o 06-secuencia-carga.png -s 2 -b white
```

**HTML** (figuras 3 y 4):

```bash
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --force-device-scale-factor=2 --window-size=1100,925 \
  --screenshot="$PWD/03-despliegue.png" "file://$PWD/03-despliegue.html"
```

El alto de la ventana se ajusta mirando el PNG: si es corto, la figura se corta; si es largo, sobra
espacio en blanco. Valores actuales: `1100,925` para la 3 y `1150,560` para la 4.

## Trampas de Mermaid
- Una flecha que sale de un `subgraph`, en vez de un nodo, deja huecos vacíos. Hay que conectar nodos.
- La `direction` de un `subgraph` se ignora si alguno de sus nodos enlaza con nodos de fuera.
- Cada relación en cadena añade una fila de alto. Una relación cuyo dato ya se ve en un campo (por
  ejemplo, una clave foránea en un diagrama ER) puede quitarse para que la figura quepa.
- Invertir el sentido de una relación sin flecha (`A --- B` frente a `B --- A`) cambia la fila en la
  que se dibuja cada nodo.
- Las notas largas en diagramas de secuencia se cortan por los lados: hay que acortarlas o hacer que
  abarquen dos participantes.
- **No se entregan SVG:** `mermaid-cli` escribe el texto dentro de `foreignObject`, que Word no muestra.
- El motor de disposición ELK no viene incluido en `mermaid-cli`: `layout: elk` se ignora sin avisar.
