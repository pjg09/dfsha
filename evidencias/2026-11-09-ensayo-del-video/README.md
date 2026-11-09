# Ensayo del vídeo

- **Fecha:** 2026-11-09, de 02:32 a 02:51 UTC
- **Commit y versión:** imágenes `v0.13.2` (`17c5dbd`); repositorio en `faae18f`
- **Entorno:** aws · los 9 hosts, tras el arranque en frío de la sesión del laboratorio (02:26 UTC)
- **Cubre:** el ensayo de las escenas del vídeo (etapa 12) con las órdenes del guion: carga y recuperación de 1 GiB, RF3, dos clientes sobre el mismo bloque, caída de un nodo de datos, caída del líder de metadatos y seguridad. No es una prueba mínima nueva; deja dos hallazgos que el informe y la defensa deben conocer.
- **Resultado obtenido:** las escenas hacen lo que el guion necesita, y aparecen dos hallazgos:
  1. **La elección tarda más si el etcd congelado es también el líder de Raft.** En las dos mediciones precisas (`eleccion-medida.txt`), el etcd del líder de DFSha era el líder de Raft de etcd: el nuevo líder de DFSha se eligió a los 8,1 s del congelado y el modo seguro terminó 2,9 s después, unos 11 s en total. Confirma la hipótesis de las repeticiones 4 y 5 de E7 (7,7 y 8,5 s), frente a los 5,1–5,3 s de las repeticiones 1 a 3.
  2. **Con un servidor de metadatos congelado, cada orden de la CLI tarda unos 13 s.** Cada orden `dfsha` es un proceso nuevo y empieza por el primer servidor de su lista (`metadata-1`). Si ese servidor está congelado, acepta la conexión y no responde, y el cliente espera el plazo completo de la llamada (`RPC_TIMEOUT_S`, 10 s) antes de pasar al siguiente. En el primer ensayo, `metadata-1` quedó congelado y los 12 `mkdir` siguientes tardaron 13 s cada uno hasta el final. Dentro de un mismo proceso (`dfsha shell`) el cliente recuerda al líder nuevo y solo paga la espera una vez. Con un servidor parado (conexión rechazada) el cambio es inmediato.
- **Otros resultados:**
  - **Carga y recuperación:** `put` de 1 GiB en 7,6 s y `get` en 8,4 s, el mismo SHA-256; las réplicas pasan de 213 a 405.
  - **Concurrencia:** `LOCK_CONFLICT`, `VERSION_CONFLICT` y bloque final `P1-cambia-el-bloque-3+P2`.
  - **Caída de un nodo de datos:** declarado caído a los 30,4 s; 91 bloques re-replicados en 21 s; al volver, 91 réplicas de más borradas. Con otro nodo parado, `get` de 1 GiB en 8,3 s con el mismo hash.
  - **Seguridad:** una marca repetida 52 429 veces no aparece en ninguna réplica; sin certificado de cliente la conexión se cierra; con él, TLS 1.3.

## Fallos del propio ensayo
- El primer script se cortó en la escena 4b por una variable sin definir, y se repitió desde ahí (`salida.txt`).
- La escena 4b del primer script enviaba al shell las pausas como órdenes (`sleep-12`), así que no probaba la concurrencia; se repitió en `salida-2.txt`.
- En la escena 5 del primer script, el disco de `client-1` se llenó con copias de pruebas anteriores y las tres lecturas fallaron por `No space left on device`. Se borraron las copias locales y la escena se repitió en `salida-2.txt`.

## Archivos
- `salida.txt`: primer ensayo, de la escena 2 a la 7.
- `salida-2.txt`: segundo ensayo: concurrencia, lecturas con un nodo caído y caída del líder con un `dfsha shell` abierto.
- `eleccion-medida.txt`: dos mediciones de la elección con el líder congelado, con la hora del congelado tomada en el propio host y el líder de Raft de etcd en ese momento.
