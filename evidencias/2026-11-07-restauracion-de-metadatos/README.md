# Restauración de los metadatos desde la copia de S3

- **Fecha:** 2026-11-07
- **Commit y versión:** imágenes `v0.9.1` (`7bdf5f5`); `deploy.sh restore` de `7bdf5f5`. La primera ejecución usó `v0.9.0`.
- **Entorno:** aws · `metadata-1` a `metadata-3`, los cinco nodos de datos y `client-1`
- **Cubre:** fallo provocado: pérdida del estado de etcd en los tres servidores de metadatos (fase I §4.2, fila «Los tres servidores de metadatos con sus volúmenes» de la §11.3, ADR 0035)
- **Resultado esperado:** al restaurar la última copia de S3 vuelven los archivos anteriores a la copia y se pierde lo posterior (L11). El nuevo líder tiene una época mayor que las anteriores, y los nodos de datos lo aceptan sin reiniciarse.
- **Resultado obtenido:** coincide con `v0.9.1`.
  - `/grande.bin` y `/marca.txt` vuelven, y `/despues-de-la-copia.txt` se pierde.
  - `get` de `/grande.bin` devuelve el mismo SHA-256 (`4993c4a8…66a4be1`): las claves de datos envueltas se restauran con los metadatos, y la clave de envoltura sigue en los servidores.
  - Nuevo líder con época 2 000 000 252, gracias a `--bump-revision`.
  - Los cinco nodos de datos envían su informe de bloques 0 a 1 s después de la elección.
  - De la parada a los servidores en marcha pasan 38 s, y otros 7 s hasta el nuevo líder.

## Primera ejecución: un fallo del nodo de datos
`salida-1-hilo-de-latidos.txt` es la primera ejecución, con `v0.9.0`.
- **Lo que pasó:** la restauración funcionó, pero `get` falló con `BLOCK_LOST`. Un líder que se estaba parando respondió `UNKNOWN` a `ReportBlocks`; la excepción salió del bucle de latidos y su hilo murió en los cinco nodos de datos. El nuevo líder nunca los vio vivos.
- **La corrección:** `fix(datanode)` en `v0.9.1`, con la prueba `tests/test_metadata_client.py`.
- **La comprobación:** en la segunda ejecución, el mismo `UNKNOWN` llegó a tres nodos de datos, que lo registraron y siguieron (`nodos-de-datos.txt`).

## Comandos
```bash
evidencias/2026-11-07-restauracion-de-metadatos/ejecutar.sh > evidencias/2026-11-07-restauracion-de-metadatos/salida.txt 2>&1
```

`deploy.sh restore` para los tres servidores de metadatos y aparta el directorio de etcd de cada uno a `etcd-anterior-<fecha>`, que equivale a perder su estado. Después restaura la instantánea con `etcdutl snapshot restore --bump-revision 1000000000 --mark-compacted` y vuelve a arrancarlos.

En `salida.txt`, el paso «Los nodos de datos aceptan al nuevo líder» salió vacío: el patrón buscaba líneas que el nodo de datos no escribe. Se corrigió en `ejecutar.sh`, y las líneas de esa ejecución se sacaron después de los logs, a `nodos-de-datos.txt`.

## Archivos
- `ejecutar.sh`: la prueba.
- `salida.txt`: segunda ejecución, con `v0.9.1`.
- `salida-1-hilo-de-latidos.txt`: primera ejecución, con `v0.9.0`, en la que el hilo de latidos murió.
- `nodos-de-datos.txt`: logs de los cinco nodos de datos desde el inicio de la segunda restauración.
