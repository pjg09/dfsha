# Escenario 3: un nodo falla después de recibir parte de un bloque

- **Fecha:** 2026-11-07
- **Commit y versión:** `8848cf8` · v0.12.0 (imágenes `0.12.0` en ECR)
- **Entorno:** aws · `datanode-4` se para con `docker stop --time 0` a los 3 s de empezar un `put` de 1 GiB desde `client-1`; otro proceso consulta el archivo mientras tanto
- **Cubre:** escenario 3 de la fase I §11.3 (condición de cierre de la etapa 9)
- **Resultado esperado:**
  - Lo recibido a medias se queda en el área temporal del nodo caído, sin renombrar ni avisar.
  - El cliente repite cada bloque fallido con un `block_id` nuevo y otros nodos, y la carga termina.
  - Los demás clientes no ven nada hasta la confirmación (G4).
  - Al volver, el nodo descarta su área temporal.
- **Resultado obtenido:** coincide.
  - **Carga:** seis bloques fallan en `datanode-4`, una sola vez cada uno, y se repiten en otros nodos. La carga se confirma en 8,0 s, y el archivo recuperado tiene el mismo SHA-256 que el original.
  - **Observador:** recibe `PATH_NOT_FOUND` hasta la consulta que responde a las 17:44:20, cuando el cliente recibe la confirmación, y la versión 1 desde entonces.
  - **Área temporal:** mientras `datanode-4` está caído, contiene dos bloques a medias (6 y 14 MiB) que nunca se renombraron. Al arrancar, los borra («Borrados 2 bloques a medias del área temporal»).

## Ejecuciones anteriores
- **`salida-1-observador-ambiguo.txt`** (`v0.11.1`): la carga terminó bien, pero el observador anotaba la hora de inicio de cada consulta, que tarda unos 3 s. Una respuesta posterior a la confirmación aparecía con una hora anterior. Ahora anota la hora de inicio y la de respuesta.
- **`salida-2-mismo-nodo.txt`** (`v0.11.1`): **la carga falló.** El líder seguía contando `datanode-4` como vivo (hasta 9 s) y, por ser el de más espacio libre, lo dio como primaria en las cuatro reservas del bloque 58. La §11.3 dice que al repetir se reciben otros nodos. Se corrigió con el ADR 0044, en la `v0.12.0`. Incluso en esa ejecución se cumplió G4: el observador nunca vio el archivo.

## Comandos
```bash
evidencias/2026-11-07-escenario-3/ejecutar.sh > evidencias/2026-11-07-escenario-3/salida.txt 2>&1
```

## Archivos
- `ejecutar.sh`: la prueba.
- `salida.txt`: ejecución con la `v0.12.0`.
- `salida-1-observador-ambiguo.txt` y `salida-2-mismo-nodo.txt`: ejecuciones anteriores, con la `v0.11.1`.
