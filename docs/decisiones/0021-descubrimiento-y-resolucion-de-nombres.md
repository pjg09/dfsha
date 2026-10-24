# 0021 · Descubrimiento: el cliente solo conoce los servidores de metadatos; nombres por `/etc/hosts`

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF7, §4.2 (escenario 4); aclaración A6; completa lo que el ADR 0003 dejó pendiente; C7, C20, C26

## Contexto
El ADR 0003 dejó pendiente cómo se resuelven en AWS los nombres `<rol>-<n>`. Según A6, el cliente puede
conocer el servidor de metadatos como punto de entrada, pero no dónde están los bloques. La IP pública de
las instancias cambia en cada sesión del Learner Lab (C26).

## Opciones consideradas
1. **`/etc/hosts` generado** por el script de despliegue a partir de las etiquetas de EC2
   (`Name=dfsha-<rol>-<n>`) y las IP privadas.
2. **Zona privada de Route 53.** Es DNS de verdad, y la cuenta del lab responde a Route 53: el Readme
   solo prohíbe registrar dominios, y `list-hosted-zones` funciona (comprobado el 2026-10-23). Pero es
   una pieza propia de AWS que el entorno local no tiene, no se ha probado a crear una zona privada y
   tiene coste. Como la IP privada se conserva al parar y arrancar, `/etc/hosts` solo cambia al
   sustituir una instancia.
3. **Registro con IP en el servidor de metadatos.** Resuelve los nodos de datos, pero no a los propios
   servidores de metadatos.

## Decisión
**Lo que conoce el cliente:**
- Se configura solo con la lista de servidores de metadatos: `DFSHA_METADATA_ADDRS=metadata-1:<puerto>,metadata-2:<puerto>,metadata-3:<puerto>`.
- Pregunta a cualquiera de ellos; si no es el líder, este le indica cuál lo es (ADR 0014).

**Lo que se descubre en tiempo de ejecución:**
- Las ubicaciones de los bloques se piden siempre al servidor de metadatos, con `GetBlockLocations` en `open()`.
- Los nodos de datos se dan de alta con su nombre de host, y el servidor de metadatos devuelve nombres, no IP.

**Resolución de nombres a IP:** opción 1, `/etc/hosts` regenerado en cada despliegue.

**Escenario 4:** el cliente solo conoce los nombres de los servidores de metadatos. Cada ubicación de
bloque la obtiene del líder al abrir el archivo, y si una réplica falla vuelve a preguntar.

## Consecuencias
- **Se gana:** no hay ninguna IP en el repositorio ni en el cliente, y todo sigue funcionando aunque cambie la IP pública.
- **Se pierde:** sustituir una instancia obliga a regenerar `/etc/hosts` en todas; no es DNS dinámico.
- **Sin comprobar en el lab:** según la documentación de AWS, la IP privada se conserva al parar y arrancar una instancia.
- **Cambia la convención de nombres:** las listas de direcciones van en variables terminadas en `_addrs` (`convenciones.md` §2).
