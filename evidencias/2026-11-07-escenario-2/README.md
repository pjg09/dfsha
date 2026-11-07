# Consistencia: escenario 2, una réplica está desconectada durante una escritura

- **Fecha:** 2026-11-07
- **Commit y versión:** `2fb2416` · v0.11.1 (imágenes `0.11.1` en ECR)
- **Entorno:** aws · se para `datanode-5` con `docker stop --time 0` justo antes de un `put` de 128 MiB (8 bloques) desde `client-1`
- **Cubre:** prueba mínima «Consistencia» de §5.2, escenario 2 de la fase I §11.2
- **Resultado esperado:**
  - La primaria reenvía a la réplica desconectada y responde OK con W = 2.
  - `CommitFile` confirma la versión nueva, y sus ubicaciones solo incluyen las réplicas que avisaron, así que ningún lector intenta leer la versión nueva de la réplica desconectada.
  - A los 30 s, el nodo se declara caído y los bloques con 2 réplicas se re-replican.
  - Al volver, el nodo no tiene nada de la versión nueva: no hay réplicas distintas de un mismo bloque.
- **Resultado obtenido:** coincide.
  - **Escritura:** el líder seguía contando `datanode-5` como vivo y lo incluyó en varias asignaciones. Como secundaria, `datanode-2` no pudo reenviarle tres bloques y respondió OK con las dos réplicas restantes. Como primaria (bloques 2 y 5), el cliente reservó el bloque de nuevo en otros nodos, como en el escenario 3.
  - **Confirmación:** la versión 1 se confirma con los bloques 0, 2 y 5 en 2 réplicas y los demás en 3. `datanode-5` no aparece en ninguna ubicación.
  - **Lectura:** el `get` de la versión nueva da el mismo SHA-256 que el original (G2).
  - **Re-replicación:** a los 45 s de la caída, todos los bloques tienen 3 réplicas.
  - **Vuelta del nodo:** `datanode-5` se da de alta e informa de sus 55 bloques antiguos; las ubicaciones de la versión nueva no cambian.

`datanode-2` y `datanode-3` aparecen en todos los bloques porque la ubicación elige a los nodos con más espacio libre (§4.3), y en ese momento eran los que menos réplicas tenían.

## Comandos
```bash
evidencias/2026-11-07-escenario-2/ejecutar.sh > evidencias/2026-11-07-escenario-2/salida.txt 2>&1
```

## Archivos
- `ejecutar.sh`: la prueba.
- `ubicaciones.py`: las ubicaciones que anuncia el servidor de metadatos para cada bloque, en `client-1`.
- `salida.txt`: salida completa, con el log del cliente (`-v`) y los avisos de las primarias.
