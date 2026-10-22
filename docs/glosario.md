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
| versión | `version` | Número que crece con cada escritura confirmada de un archivo o bloque **(D)** | revisión |

## 3. Replicación

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| réplica | `replica` | Cada copia de un bloque guardada en un nodo de datos | copia (en sentido técnico) |
| factor de replicación | `replication_factor` | Número de réplicas objetivo de cada bloque | — |
| réplica primaria | `primary` | La réplica que ordena las escrituras de un bloque **(D)** | líder (reservado para la elección de líder), `master` |
| réplica secundaria | `secondary` | Réplica que aplica lo que le indica la primaria **(D)** | `slave`, `follower` |
| cadena de replicación | `replication_pipeline` | Reenvío de un bloque de un nodo de datos al siguiente **(D)** | — |
| réplica desactualizada | `stale` (estado) | Réplica que se perdió escrituras confirmadas | obsoleta |
| re-replicación | `re_replicate` | Crear réplicas nuevas para recuperar el factor de replicación tras una caída | reparación |
| resincronización | `resync` | Poner al día una réplica desactualizada que vuelve | — |
| quórum | `quorum`, `write_quorum`, `read_quorum` | Número mínimo de réplicas que deben responder **(D)** | mayoría (salvo si es exactamente ⌊N/2⌋+1) |

## 4. Operaciones (RF1–RF3)

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| listar / cambiar de directorio / crear directorio / borrar directorio / borrar archivo | `ls`, `cd`, `mkdir`, `rmdir`, `rm` | Comandos de RF1, con los nombres del enunciado | — |
| carga | `put` | Enviar un archivo completo al DFS (RF2) | subida, `upload`, `send` |
| recuperación | `get` | Traer un archivo completo del DFS (RF2) | descarga, `download`, `receive`, `recv` |
| abrir / cerrar / leer / escribir | `open`, `close`, `read`, `write` | Primitivas de RF3 | — |
| descriptor de archivo | `file_handle`, `FileHandle` | Lo que devuelve `open()` y usan `read()`/`write()` | `fd` |
| desplazamiento | `offset` | Posición en bytes dentro de un archivo | posición |
| modo de escritura | `write_mode`, `WriteMode` | Qué tipo de escritura hace `write()` | — |
| creación | `create` | `write()` sobre un archivo que no existe | — |
| reemplazo | `replace` | `write()` que sustituye el contenido completo | sobrescritura, `overwrite` |
| anexado | `append` | `write()` que añade al final | — |
| modificación parcial | `partial` (p. ej. `WRITE_MODE_PARTIAL`) | `write()` que cambia solo algunos bloques **(D)** | parche, `patch` |

## 5. Consistencia y concurrencia

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| consistencia | `consistency` | Qué versión de los datos puede ver cada lector | coherencia |
| modelo de consistencia | `consistency_model` | La garantía declarada (RNF3 y §7 del enunciado) | — |
| escritura en curso | `pending` (estado) | Escritura iniciada que todavía no es visible | — |
| área temporal | `staging` | Lugar donde se guardan los bloques antes de confirmarlos **(D)** | temporal, `tmp` |
| confirmar | `commit` | Hacer visible y definitiva una escritura de forma atómica | publicar, `publish`, `finalize` |
| escritura confirmada | `committed` (estado) | Escritura visible para los lectores según el modelo declarado | — |
| abortar | `abort` | Descartar una escritura en curso | cancelar, `rollback` |
| atómico | `atomic` | Ocurre del todo o no ocurre | — |
| cerrojo | `lock` | Exclusión mutua sobre un archivo o un bloque (RF3) | **bloqueo** (se confunde con «bloque») |
| liberar cerrojo | `unlock` | Soltar un cerrojo | `release` |
| cerrojo exclusivo / compartido | `exclusive` / `shared` | Un solo escritor / varios lectores **(D)** | — |
| arrendamiento | `lease` | Cerrojo con caducidad automática **(D)** | concesión |
| tiempo de vida | `ttl_s` | Duración de un arrendamiento | — |
| conflicto | `conflict` | Dos operaciones incompatibles sobre el mismo recurso | colisión |
| idempotente | `idempotent` | Repetirla tiene el mismo efecto que hacerla una vez | — |
| identificador de petición | `request_id` | Identifica una petición para poder reintentarla sin duplicar su efecto | — |

## 6. Tolerancia a fallos

| Término | Código | Significado en DFSha | No usar |
|---|---|---|---|
| fallo | `failure` | Un nodo deja de prestar servicio | error (reservado para respuestas de error), caída en código |
| latido | `heartbeat` | Mensaje periódico de un nodo de datos que demuestra que sigue vivo | ping |
| informe de bloques | `block_report` | Lista de bloques que tiene un nodo de datos **(D)** | — |
| detector de fallos | `failure_detector` | Componente que decide si un nodo está caído | — |
| estado del nodo | `node_state`, `NodeState` | Vivo, sospechoso o caído | — |
| vivo / sospechoso / caído | `alive` / `suspect` / `dead` | Estados posibles de un nodo | `up`/`down`, activo/inactivo |
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
| cifrado en tránsito | `tls` | Protección del canal: cliente↔nodos y entre nodos (RNF6) | — |
| TLS mutuo | `mtls` | Las dos partes presentan certificado **(D)** | — |
| certificado / autoridad certificadora | `cert` / `ca` | — | — |
| cifrado en reposo | `encryption_at_rest` | Bloques cifrados en el disco del nodo de datos (RNF6) | — |
| clave de cifrado | `encryption_key` | Clave que cifra los datos en reposo | — |
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
