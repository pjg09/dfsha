# Glosario del proyecto

Vigente desde el 2026-10-21. **Es la fuente única de términos**: la documentación usa la columna
*Término*, el código usa la columna *Código* y nadie usa la columna *No usar*. Un término nuevo se añade
aquí **antes** de usarlo en el código o en los documentos. Las reglas de formato (mayúsculas, sufijos,
idioma) están en [`convenciones.md`](convenciones.md).

Columna *Código*: `snake_case` cuando el término es una variable o un módulo; `PascalCase` cuando es una
clase o un tipo. Un **(D)** indica que el término solo se usa si el diseño adopta ese mecanismo. Que esté
en el glosario no significa que ya se haya decidido.

## 1. Arquitectura y roles

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| sistema de archivos distribuido (DFS) | `dfsha` (paquete) | El sistema completo | — |
| cliente | `client`, `Client` | Proceso del usuario (CLI o biblioteca) que habla con el clúster | — |
| servidor de metadatos | `metadata`, `MetadataServer` | Rol del plano de control: espacio de nombres, ubicación de bloques, cerrojos y estado de los nodos | maestro, `master`, `namenode`, `NameNode` (estos solo al citar HDFS) |
| nodo de datos | `datanode`, `DataNode` | Rol que almacena y sirve bloques | servidor de datos, `chunkserver`, `storage_node`, `slave` |
| nodo | `node`, `node_id` | Cualquier proceso servidor del clúster, sea del rol que sea | — |
| rol | `role` | Función de un nodo: `metadata`, `datanode` o `client` | tipo de nodo |
| clúster | `cluster` | El conjunto de nodos de una instalación | — |
| plano de control | — (solo en documentos) | Operaciones sobre metadatos, coordinación y estado de los nodos | — |
| plano de datos | — (solo en documentos) | Transferencia de bloques entre el cliente y los nodos de datos | — |
| servicio entre servidores (S2S) | — (solo en documentos) | La arquitectura asignada: opción 1 del enunciado | — |
| registro de nodos | `node_registry`, `NodeRegistry` | Tabla de nodos conocidos y su estado, en el servidor de metadatos | directorio de nodos |
| descubrimiento | `discovery` | Cómo un proceso encuentra a otro sin direcciones fijas (RNF7) | `lookup` (reservado para la DHT de P2P) |
| alta de un nodo | `register` | Un nodo se anuncia al servidor de metadatos | `join` |
| líder | `leader` | Servidor de metadatos elegido por mayoría que ordena el log replicado y atiende las peticiones (ADR 0014) | maestro, `master`, primario |
| seguidor | `follower` | Servidor de metadatos que no es el líder: replica el log y redirige al líder (ADR 0014) | esclavo, `slave`, réplica (es otra cosa) |
| log replicado | `replicated_log` | Secuencia ordenada de cambios de metadatos que el consenso Raft copia en la mayoría | journal, `edit_log` (salvo al citar HDFS) |
| instantánea | `snapshot` | Copia completa del estado de los metadatos que permite recortar el log replicado | — |
| copia de seguridad | `backup` | Instantánea de los metadatos guardada fuera de las instancias, en S3, al final de cada sesión de trabajo (ADR 0035) | respaldo |

## 2. Datos y almacenamiento

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| archivo | `file` | Unidad de datos que ve el usuario | fichero (en los documentos se escribe «archivo») |
| directorio | `directory` | Nodo interno del espacio de nombres | carpeta, `folder`, `dir` (salvo en el comando `rmdir`/`mkdir`) |
| espacio de nombres | `namespace` | Árbol de directorios y archivos de **un** usuario (RF1) | — |
| ruta | `path` | Ruta **lógica** dentro del espacio de nombres: `/docs/a.txt` | — |
| ruta local | `local_path` | Ruta en el disco de un nodo o del cliente | — |
| bloque | `block`, `Block` | Fragmento de tamaño fijo de un archivo; unidad de reparto y replicación | `chunk`, trozo, fragmento, segmento |
| identificador de bloque | `block_id` | Identifica un bloque en todo el clúster | — |
| índice de bloque | `block_index` | Posición del bloque dentro de su archivo, desde 0 | — |
| tamaño de bloque | `block_size_bytes` | Tamaño máximo de un bloque | — |
| tamaño | `size_bytes` | Tamaño de cualquier cosa, siempre en bytes | `length`, `len` |
| ubicación de bloque | `block_location`, `BlockLocation` | Qué nodos de datos tienen un bloque | — |
| almacén de bloques | `block_store`, `BlockStore` | Componente del nodo de datos que guarda los bloques en disco | — |
| metadatos | `metadata` | Datos sobre archivos y bloques, no su contenido | — |
| propietario | `owner` | Usuario dueño de un archivo o directorio | dueño |
| hash | `sha256` (como sufijo: `block_sha256`, `file_sha256`) | Resumen SHA-256 para verificar integridad | `checksum`, `digest`, `md5` |
| integridad | `integrity` | El contenido no se alteró ni quedó incompleto | — |
| versión de archivo | `file_version`, `version` | Lista ordenada de `block_id` de un archivo. Cada escritura confirmada crea una nueva, con un número mayor (ADR 0009) | revisión |
| copia en escritura | `copy_on_write` | Escribir creando bloques nuevos en vez de modificar los existentes; un bloque escrito no cambia nunca (ADR 0009) | escritura en el sitio |
| bloque huérfano | `orphan` (estado) | Bloque que no pertenece a ninguna versión viva ni a una escritura en curso | — |
| recolección de basura | `garbage_collection` | Borrado de bloques huérfanos y de versiones sustituidas tras el periodo de gracia (ADR 0018, ADR 0025) | limpieza, purga |
| periodo de gracia | `grace_period_s` | Tiempo que se conserva una versión borrada o sustituida para sus lectores abiertos (ADR 0025) | — |

## 3. Replicación

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| réplica | `replica` | Cada copia de un bloque guardada en un nodo de datos | copia (en sentido técnico) |
| factor de replicación | `replication_factor` | Número de réplicas objetivo de cada bloque | — |
| réplica primaria | `primary` | Réplica que recibe el bloque del cliente y lo reenvía en paralelo a las secundarias (ADR 0012) | líder (reservado para Raft), `master` |
| réplica secundaria | `secondary` | Réplica que recibe el bloque de la primaria (ADR 0012) | `slave`, `follower` (reservado para Raft) |
| cadena de replicación | `replication_pipeline` | Reenvío de un bloque de un nodo de datos al siguiente **(D)** | — |
| réplica desactualizada | `stale` (estado) | Réplica que se perdió escrituras confirmadas | obsoleta |
| re-replicación | `re_replicate` | Crear réplicas nuevas para recuperar el factor de replicación tras una caída | reparación |
| resincronización | `resync` | Poner al día una réplica desactualizada que vuelve | — |
| quórum | `quorum`, `write_quorum`, `read_quorum` | Número mínimo de réplicas que deben responder. DFSha usa `write_quorum` = 2 y no tiene quórum de lectura (ADR 0012) | mayoría (salvo si es exactamente ⌊N/2⌋+1) |

## 4. Operaciones (RF1–RF3)

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| listar / cambiar de directorio / crear directorio / borrar directorio / borrar archivo | `ls`, `cd`, `mkdir`, `rmdir`, `rm` | Comandos de RF1, con los nombres del enunciado | — |
| mover | `mv` | Mover o renombrar un archivo o directorio dentro del espacio de nombres, de forma atómica (ADR 0025) | `rename` (renombrar es mover) |
| carga | `put` | Enviar un archivo completo al DFS (RF2) | subida, `upload`, `send` |
| recuperación | `get` | Traer un archivo completo del DFS (RF2) | descarga, `download`, `receive`, `recv` |
| abrir / cerrar / leer / escribir | `open`, `close`, `read`, `write` | Primitivas de RF3 | — |
| descriptor de archivo | `file_handle`, `FileHandle` | Lo que devuelve `open()` y usan `read()`/`write()` | `fd` |
| desplazamiento | `offset` | Posición en bytes dentro de un archivo | posición |
| modo de escritura | `write_mode`, `WriteMode` | Qué tipo de escritura hace `write()` | — |
| creación | `create` | `write()` sobre un archivo que no existe | — |
| reemplazo | `replace` | `write()` que sustituye el contenido completo | sobrescritura, `overwrite` |
| anexado | `append` | `write()` que añade al final | — |
| modificación parcial | `partial` (p. ej. `WRITE_MODE_PARTIAL`) | `write()` que cambia parte del contenido en cualquier `offset`; reescribe como bloques nuevos los bloques afectados (ADR 0009) | parche, `patch` |
| rango de bloques | `block_range` | Índices de bloque consecutivos que cubre un arrendamiento (ADR 0011) | — |

## 5. Consistencia y concurrencia

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| consistencia | `consistency` | Qué versión de los datos puede ver cada lector | coherencia |
| modelo de consistencia | `consistency_model` | La garantía declarada (RNF3 y §7 del enunciado) | — |
| consistencia de apertura-cierre | `close_to_open` | `open()` fija la versión que se lee; una escritura es visible desde su confirmación en `close()` (ADR 0010) | — |
| escritura en curso | `pending` (estado) | Escritura iniciada que todavía no es visible | — |
| área temporal | `staging` | Lugar del nodo de datos donde se escribe un bloque antes de verificarlo y renombrarlo (ADR 0013) | temporal, `tmp` |
| confirmar | `commit` | Hacer visible y definitiva una escritura de forma atómica | publicar, `publish`, `finalize` |
| escritura confirmada | `committed` (estado) | Escritura visible para los lectores según el modelo declarado | — |
| abortar | `abort` | Descartar una escritura en curso | cancelar, `rollback` |
| atómico | `atomic` | Ocurre del todo o no ocurre | — |
| cerrojo | `lock` | Exclusión mutua sobre un archivo o un bloque (RF3) | **bloqueo** (se confunde con «bloque») |
| liberar cerrojo | `unlock` | Soltar un cerrojo | `release` |
| cerrojo exclusivo / compartido | `exclusive` / `shared` | Un solo escritor / varios lectores. DFSha solo usa el exclusivo (ADR 0011) | — |
| arrendamiento | `lease` | Cerrojo con caducidad automática; en DFSha, exclusivo de escritura sobre un rango de bloques (ADR 0011) | concesión |
| tiempo de vida | `ttl_s` | Duración de un arrendamiento | — |
| conflicto | `conflict` | Dos operaciones incompatibles sobre el mismo recurso | colisión |
| idempotente | `idempotent` | Repetirla tiene el mismo efecto que hacerla una vez | — |
| identificador de petición | `request_id` | Identifica una petición para poder reintentarla sin duplicar su efecto | — |

## 6. Tolerancia a fallos

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| fallo | `failure` | Un nodo deja de prestar servicio | error (reservado para respuestas de error), caída en código |
| latido | `heartbeat` | Mensaje periódico de un nodo de datos que demuestra que sigue vivo | ping |
| informe de bloques | `block_report` | Lista de bloques que tiene un nodo de datos; se envía al darse de alta y periódicamente (ADR 0018) | — |
| aviso de bloque recibido | `block_received` | Mensaje de un nodo de datos al servidor de metadatos cuando guarda una réplica verificada (ADR 0013) | — |
| orden | `DataNodeCommand` | Instrucción que el servidor de metadatos envía a un nodo de datos en la respuesta a su latido: `REPLICATE`, `DELETE`, `VERIFY` o `SEND_BLOCK_REPORT` (ADR 0018) | comando (reservado para el CLI), tarea |
| código de motivo | `reason` (en `google.rpc.ErrorInfo`) | Código propio en `UPPER_SNAKE` que detalla un error gRPC: `LOCK_CONFLICT`, `SAFE_MODE_ACTIVE`… Las convenciones (§1 y §2) lo llaman también «código de error» | — |
| detector de fallos | `failure_detector` | Componente que decide si un nodo está caído | — |
| estado del nodo | `node_state`, `NodeState` | Vivo, sospechoso o caído | — |
| vivo / sospechoso / caído | `alive` / `suspect` / `dead` | Estados posibles de un nodo | `up`/`down`, activo/inactivo |
| elección de líder | `leader_election` | Proceso de Raft que escoge un líder nuevo entre los servidores de metadatos (ADR 0014) | — |
| arranque en frío | `cold_start` | Arranque simultáneo de todo el clúster, por ejemplo cuando el Learner Lab vuelve a arrancar las instancias (C27) | — |
| modo seguro | `safe_mode`; código de motivo `SAFE_MODE_ACTIVE` | Estado del líder tras cada elección: atiende lecturas y mensajes de los nodos de datos, rechaza las operaciones que cambian metadatos y no declara caído a ningún nodo ni re-replica. Termina cuando cada bloque tiene una réplica en un nodo con latido, o al vencer el tope (ADR 0031) | `safemode` (solo al citar HDFS), modo de mantenimiento |
| réplica corrupta | `corrupt_replica` | Réplica cuyo contenido no coincide con su `block_sha256`. Deja de entregarse y se sustituye por una copia sana (ADR 0032) | bloque corrupto (lo corrupto es la réplica, no el bloque) |
| verificador de bloques | `block_verifier` | Proceso de cada nodo de datos que recalcula periódicamente el hash de sus bloques (ADR 0032) | `scrubber`, `scanner` (solo al citar HDFS) |
| desfase de reloj | `clock_skew`; margen `clock_skew_tolerance_s` | Diferencia entre los relojes de dos nodos, acotada con chrony (ADR 0033) | deriva (es otra cosa) |
| tiempo de espera | `timeout_s` | Límite de espera de una operación | — |
| plazo | `deadline` | Instante límite de una llamada gRPC | — |
| reintento | `retry` | Repetir una operación que falló | — |
| recuperación | `recovery` | Volver a un estado correcto después de un fallo | restauración |
| disponibilidad | `availability` | Capacidad de servir peticiones a pesar de los fallos (RNF2) | — |
| punto único de fallo (SPOF) | — (solo en documentos) | Componente cuya caída detiene todo el sistema | — |

## 7. Seguridad

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| usuario | `user`, `user_id` | Titular de un espacio de nombres | cuenta |
| autenticación | `authenticate`, módulo `auth` | Comprobar quién es el usuario o el nodo | `login` (solo como comando del CLI) |
| autorización | `authorize` | Comprobar si puede hacer una operación | — |
| permiso | `permission` | Derecho concreto sobre un recurso | privilegio |
| credencial | `credential` | Lo que presenta alguien para autenticarse | — |
| contraseña | `password` | — | `pass`, `pwd` |
| token de acceso | `access_token` | Prueba de autenticación con caducidad | — |
| token de bloque | `block_token` | Autorización firmada por el servidor de metadatos para leer o escribir un bloque concreto; la verifica el nodo de datos (ADR 0022) | — |
| cifrado en tránsito | `tls` | Protección del canal: cliente↔nodos y entre nodos (RNF6) | — |
| TLS mutuo | `mtls` | Las dos partes presentan certificado; se usa entre nodos (ADR 0023) | — |
| certificado / autoridad certificadora | `cert` / `ca` | — | — |
| cifrado en reposo | `encryption_at_rest` | Bloques cifrados en el disco del nodo de datos (RNF6) | — |
| cifrado de sobre | `envelope_encryption` | Los datos se cifran con una clave de datos, que a su vez se guarda cifrada con una clave de envoltura (ADR 0024) | — |
| clave de datos | `data_key` | Clave aleatoria de un archivo que cifra sus bloques (ADR 0024) | clave de cifrado (es ambiguo), `encryption_key` |
| clave de envoltura | `wrapping_key` | Clave de los servidores de metadatos que cifra las claves de datos (ADR 0024) | clave maestra, `master_key` |
| secreto | `secret` | Cualquier valor que no se puede versionar | — |

## 8. Despliegue

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| instancia | `instance` | Máquina virtual EC2 | servidor (es ambiguo) |
| contenedor / imagen | `container` / `image` | De Docker | — |
| volumen EBS | — (en documentos se escribe siempre «volumen EBS») | Disco de una instancia | — |
| volumen Docker | — (en documentos se escribe siempre «volumen Docker») | Almacenamiento de un contenedor | — |
| nombre de host | `hostname` | `<rol>-<n>` (ver convenciones §4) | — |
| dirección | `addr` | `host:puerto` | `url` (salvo URLs HTTP completas), `endpoint` |
| puerto | `port` | — | — |
| grupo de seguridad | `security_group` | Cortafuegos de AWS | — |
| entorno | `environment`: `local` o `aws` | Dónde se ejecuta el clúster | — |

## 9. Pruebas y medición

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| prueba | `test` | Comprobación automatizada | test (en los documentos se escribe «prueba») |
| escenario | `scenario` | Situación que se reproduce: caída, concurrencia… (§4.2 y §5.2 del enunciado) | caso |
| experimento | `experiment` | Medición repetible con parámetros declarados | benchmark (en documentos) |
| carga de trabajo | `workload` | Operaciones que genera un experimento | — |
| evidencia | `evidence` | Salida registrada que demuestra un resultado | prueba (es ambiguo) |
| latencia | `latency_ms` | Tiempo de respuesta de una operación | — |
| tasa de transferencia | `throughput_mb_s` | Datos por unidad de tiempo | **rendimiento** (en el proyecto «rendimiento» es la propiedad general, RNF5) |
| rendimiento | — (solo en documentos) | Propiedad general: latencia, tasa de transferencia y concurrencia | `performance` en identificadores |
| concurrencia | `concurrency` | Operaciones simultáneas sobre los mismos datos | paralelismo (es otra cosa) |
