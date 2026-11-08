# Escenario 2 (consistencia), con la versión final

- **Fecha:** 2026-11-08, de 04:42:59 a 04:45:02 UTC
- **Commit y versión:** imágenes `v0.13.1` (`17c5dbd`), la versión final de la etapa 10; scripts de `32c0dba`
- **Entorno:** aws · `metadata-1` a `metadata-3` (t3.small), `datanode-1` a `datanode-5` (t3.micro, volumen gp3 de 10 GiB cifrado), `client-1` (t3.small, ADR 0045); `us-east-1a`. Configuración por defecto, sin los parámetros de los experimentos.
- **Cubre:** prueba mínima «Consistencia» de §5.2 (escenario 2, fase I §11.2), repetida con la versión final. La primera ejecución está en [`2026-11-07-escenario-2`](../2026-11-07-escenario-2/).
- **Resultado esperado:** con una réplica desconectada durante una escritura, la escritura se confirma con W = 2, la ubicación solo muestra réplicas que avisaron, la lectura ve la versión nueva (G2), el líder re-replica, y el nodo que vuelve no cambia nada.
- **Resultado obtenido:** coincide.
  - **Escritura:** `datanode-5` se paró a las 04:43:08, y el líder lo seguía contando como vivo. Como primaria del bloque 5, el cliente no pudo conectarse y repitió el bloque en otros nodos (ADR 0044). Como secundaria, tres primarias no pudieron reenviarle cuatro bloques y respondieron con 2 réplicas.
  - **Confirmación:** `datanode-5` no aparece en ninguna ubicación.
  - **Lectura:** el `get` da el mismo SHA-256 que el original (G2).
  - **Re-replicación:** los cuatro bloques con 2 réplicas se ordenan copiar a las 04:43:13, antes de que `datanode-5` se declare caído (04:43:37). Tres llegan enseguida. El cuarto, el bloque 0, se ordenó copiar a `datanode-5`, que el líder aún contaba como vivo. La copia falló, y el líder no la volvió a ordenar hasta pasados 60 s (`REPLICATION_TIMEOUT_S`), esta vez hacia `datanode-1`, a las 04:44:13. Por eso la ubicación de las 04:43:28 todavía muestra el bloque 0 con 2 réplicas. A las 04:44:16 todos los bloques vivos vuelven a tener 3. No incumple ninguna garantía, pero alarga 60 s la ventana con 2 réplicas: queda anotado en `docs/fase-2/notas.md`.
  - **Vuelta del nodo:** `datanode-5` se da de alta e informa de 103 bloques antiguos, y las ubicaciones de la versión nueva no cambian.

## Con la corrección del ADR 0048 (`v0.13.2`)
La `v0.13.2` cambia la re-replicación del líder: el origen y el destino de una copia solo pueden ser nodos con un latido de 4,5 s o menos, y una copia sin aviso se repite a los 15 s, no a los 60 (ADR 0048). Se repitió la prueba dos veces:
- **`salida-2-v0.13.2.txt`** (05:36–05:38 UTC), con `datanode-5` como antes. **No reproduce el caso:** `datanode-5` ya no era el nodo con más espacio libre, la ubicación no lo eligió para ningún bloque, y todos los bloques se confirmaron con 3 réplicas. El resto de la prueba coincide con lo esperado.
- **`salida-3-v0.13.2-mas-espacio-libre.txt`** (05:41–05:43 UTC), parando `datanode-3`, que en ese momento era el de más espacio libre (8 983 MB, frente a 8 136–8 375 en los demás). **Reproduce el caso:**
  - **Escritura:** el líder seguía contando a `datanode-3` como vivo y lo eligió en todos los bloques. Como primaria (bloques 0, 3 y 6), el cliente repitió el bloque en otros nodos (ADR 0044). Como secundaria, cinco bloques se confirmaron con 2 réplicas.
  - **Re-replicación:** a las 05:42:05, 6 s después de la parada y antes de que `datanode-3` pasara a sospechoso, el líder ordena las 5 copias, todas hacia `datanode-5` y **ninguna hacia `datanode-3`**, aunque era el de más espacio libre. A las 05:42:08 todos los bloques vivos vuelven a tener 3 réplicas: **3 s con 2 réplicas, frente a 61 s con la `v0.13.1`**.
  - **Lectura:** el `get` da el mismo SHA-256 (G2). `datanode-3` se declara caído a las 05:42:29, sus bloques antiguos se re-replican, y a las 05:42:41 todo vuelve a tener 3 réplicas.
  - **Registro del líder:** `lider-3-v0.13.2.txt`.

## Comandos
```bash
evidencias/2026-11-07-escenario-2/ejecutar.sh > evidencias/2026-11-08-escenario-2/salida.txt 2>&1
deploy/aws/run.sh ssh metadata-1 "sudo docker logs --since 2026-11-08T04:43:00Z --until 2026-11-08T04:44:40Z metadata-1 2>&1 | grep -E 'Re-replicación|declarado caído|menos de 3|vuelven a tener|vuelve a enviar'" > evidencias/2026-11-08-escenario-2/lider.txt
```

```bash
evidencias/2026-11-07-escenario-2/ejecutar.sh > evidencias/2026-11-08-escenario-2/salida-2-v0.13.2.txt 2>&1
OFF=datanode-3 evidencias/2026-11-08-escenario-2/ejecutar.sh > evidencias/2026-11-08-escenario-2/salida-3-v0.13.2-mas-espacio-libre.txt 2>&1
```

## Archivos
- `salida.txt`: salida completa.
- `lider.txt`: órdenes de re-replicación del líder durante la prueba; la primera del bloque `a025530c…` va hacia `datanode-5`, y la segunda, 60 s después, hacia `datanode-1`. Las demás son las de los bloques antiguos de `datanode-5`.
- `ejecutar.sh` y `ubicaciones.py`: los de 2026-11-07, con el nodo que se desconecta configurable (`OFF`, `datanode-5` por defecto).
- `salida-2-v0.13.2.txt` y `salida-3-v0.13.2-mas-espacio-libre.txt`: las dos ejecuciones con la `v0.13.2`.
- `lider-3-v0.13.2.txt`: registro del líder durante la tercera, con las órdenes de re-replicación.
