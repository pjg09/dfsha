# Replicación y fallos, con la versión final

- **Fecha:** 2026-11-08; ejecución válida de 05:07:53 a 05:10 UTC, después de una primera cortada (04:45–05:06)
- **Commit y versión:** imágenes `v0.13.1` (`17c5dbd`), la versión final de la etapa 10; `ejecutar.sh` de este directorio, que corrige el de la primera ejecución
- **Entorno:** aws · `metadata-1` a `metadata-3` (t3.small), `datanode-1` a `datanode-5` (t3.micro, volumen gp3 de 10 GiB cifrado), `client-1` (t3.small, ADR 0045); `us-east-1a`. Configuración por defecto, sin los parámetros de los experimentos.
- **Cubre:** prueba mínima «Replicación y fallos» de §5.2, repetida con la versión final. La primera ejecución está en [`2026-11-07-replicacion-y-fallos`](../2026-11-07-replicacion-y-fallos/).
- **Resultado esperado:** con un nodo de datos caído, lecturas y escrituras siguen funcionando, el líder re-replica sus bloques hasta volver a 3 réplicas, y cuando el nodo vuelve se borran las réplicas de más (fase I §9.2, §9.3 y Tabla 29).
- **Resultado obtenido:** coincide.
  - **Antes:** 100 bloques, todos con 3 réplicas.
  - **Durante la caída de `datanode-3`** (05:08:13), antes de que se declare caído: el `get` de `/grande.bin` (1 GiB) da el mismo SHA-256 (`adfb3af2…58c41811`), y un `put` de 64 MiB se confirma.
  - **Re-replicación:** el líder ordena 25 copias, una por bloque que tenía réplica en `datanode-3`, a las 05:08:43, 30 s después de la caída (umbral de caído). A los 47 s todos los bloques vuelven a tener 3 réplicas en los cuatro nodos vivos. El contador mira los discos cada 15 s más o menos, así que 47 s es una cota superior.
  - **Vuelta del nodo:** `datanode-3` vuelve con sus 25 réplicas, que sobran. El líder ordena borrarlas, y a los 16 s ningún bloque tiene más de 3.
  - **Lectura final:** el mismo SHA-256.

## La primera ejecución, cortada
`salida-1-criterio-con-recoleccion.txt` es la primera ejecución, con el script de 2026-11-07 sin cambios. El sistema hizo lo esperado, pero el script no podía terminar:
- **Lo que hizo el sistema:** `datanode-3` se paró a las 04:45:26. El líder lo declaró caído a las 04:45:56, y a las 04:46:08 registró que todos los bloques vivos volvían a tener 3 réplicas. Al cortar, los 100 bloques en disco tenían exactamente 3 réplicas.
- **Por qué no terminaba:** el contador recuerda todos los `block_id` que ha visto y cuenta como falto de réplicas a todo bloque que ya no está en ningún nodo. A las 04:45 terminó el periodo de gracia de 10 min de las versiones sustituidas por esta tanda de pruebas (`/grande.bin` v1 y otras), y la recolección de basura borró sus réplicas a partir de las 04:48. Esos bloques ya no estaban en ningún nodo, y el contador se quedó en 84 para siempre. El 2026-11-07 no pasó porque ninguna versión caducó durante la prueba.
- **Cómo se cortó:** a mano, a las 05:06, con el registro del contador añadido al final. Después se volvió a arrancar `datanode-3`.

`ejecutar.sh` de este directorio cambia dos cosas respecto al de 2026-11-07:
- Un bloque que ya no está en ningún nodo se muestra aparte («borrados por la recolección») y no cuenta como falto de réplicas. Con un solo nodo caído y R = 3, solo la recolección de basura puede borrar todas las réplicas de un bloque.
- Un `trap` vuelve a arrancar el nodo caído si el script se corta.

## Comandos
```bash
evidencias/2026-11-08-replicacion-y-fallos/ejecutar.sh > evidencias/2026-11-08-replicacion-y-fallos/salida.txt 2>&1
```

## Archivos
- `ejecutar.sh`: la prueba, con el criterio corregido.
- `salida.txt`: salida completa de la ejecución válida.
- `salida-1-criterio-con-recoleccion.txt`: la ejecución cortada, con el registro del contador.
