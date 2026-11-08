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

## Comandos
```bash
evidencias/2026-11-07-escenario-2/ejecutar.sh > evidencias/2026-11-08-escenario-2/salida.txt 2>&1
deploy/aws/run.sh ssh metadata-1 "sudo docker logs --since 2026-11-08T04:43:00Z --until 2026-11-08T04:44:40Z metadata-1 2>&1 | grep -E 'Re-replicación|declarado caído|menos de 3|vuelven a tener|vuelve a enviar'" > evidencias/2026-11-08-escenario-2/lider.txt
```

## Archivos
- `salida.txt`: salida completa.
- `lider.txt`: órdenes de re-replicación del líder durante la prueba; la primera del bloque `a025530c…` va hacia `datanode-5`, y la segunda, 60 s después, hacia `datanode-1`. Las demás son las de los bloques antiguos de `datanode-5`.
