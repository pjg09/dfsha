# Replicación y fallos: caída de un nodo de datos

- **Fecha:** 2026-11-07
- **Commit y versión:** `2fb2416` · v0.11.1 (imágenes `0.11.1` en ECR); líder `metadata-2`
- **Entorno:** aws · se para `datanode-3` con `docker stop --time 0` y se vuelve a arrancar; las lecturas y escrituras salen de `client-1`
- **Cubre:** prueba mínima «Replicación y fallos» de §5.2: fase I §9.2, §9.3 y la fila «Un nodo de datos» de la Tabla 29
- **Resultado esperado:**
  - Durante la caída, las lecturas siguen (otra réplica) y las escrituras también (W = 2 de 3).
  - A los 30 s sin latido el nodo se declara caído y sus bloques se re-replican.
  - Cuando vuelve, sus réplicas de más se borran, sin bajar nunca de R = 3.
- **Resultado obtenido:** coincide.
  - **Durante la caída:** un `get` de 1 GiB da el mismo SHA-256 (`4b214ab4…7be4`), y un `put` de 64 MiB se confirma.
  - **Re-replicación:** el líder ordena 40 copias entre las 17:16:23 y las 17:16:33, a los 28 s de terminar el `docker stop` (el último latido fue algo antes). A los 45 s de la caída, los 79 bloques vuelven a tener 3 réplicas sin `datanode-3`, frente a 40 con solo 2 al principio.
  - **Vuelta del nodo:** al arrancar `datanode-3` con sus 40 bloques, el líder borra 40 réplicas de más antes de la primera comprobación, y ningún bloque queda con más ni con menos de 3.
  - **Lectura final:** el mismo SHA-256.

## Primera ejecución: el cliente se quedó sin memoria
`salida-1-cliente-sin-memoria.txt` es la primera ejecución, con la `v0.11.1.dev2` (mismo código que `v0.11.0`). La re-replicación y el borrado de las réplicas de más funcionaron igual, pero el `get` durante la caída murió sin mensaje: el kernel de `client-1` lo mató por falta de memoria.
- **Causa:** cada lectura fallida de una réplica dejaba un ciclo de referencias que retenía el bloque de 16 MiB leído después.
- **Medición:** con un nodo caído, el pico pasaba de unos 300 MiB a más de 500 MiB.
- **Corrección:** `fix(client)` en `v0.11.1`, con una prueba que la detecta. El detalle está en `docs/fase-2/notas.md`.

## Comandos
```bash
evidencias/2026-11-07-replicacion-y-fallos/ejecutar.sh > evidencias/2026-11-07-replicacion-y-fallos/salida.txt 2>&1
```

`ejecutar.sh` cuenta las réplicas por `block_id` en el disco de cada nodo, con un proceso en segundo plano que empieza en el momento de la caída. El criterio es que cada bloque que hay en disco tenga 3 réplicas en los nodos contados. Cada comprobación tarda unos 10 s (cinco conexiones SSH), así que las horas tienen esa resolución. Antes de esta ejecución se borró `/durante-la-caida.bin`, de la primera: sus bloques siguen vivos durante el periodo de gracia y también cuentan.

## Archivos
- `ejecutar.sh`: la prueba.
- `salida.txt`: ejecución con la `v0.11.1`.
- `salida-1-cliente-sin-memoria.txt`: primera ejecución, en la que el `get` murió por falta de memoria.
