# Convenciones del proyecto

Vigentes desde el 2026-10-21. Cualquier cambio se registra antes con un ADR nuevo en
[`decisiones/`](decisiones/) y después se actualiza este documento.

Términos del dominio: ver [`glosario.md`](glosario.md). Este documento fija **cómo** se
nombran las cosas; el glosario fija **qué palabra** se usa para cada concepto.

## 1. Idioma

| Qué | Idioma | Ejemplo |
|---|---|---|
| Identificadores: paquetes, módulos, clases, funciones, variables, `.proto`, rutas de API, servicios Docker, variables de entorno | **Inglés** | `BlockStore.read_block()` |
| Códigos de error | **Inglés**, `UPPER_SNAKE` | `LOCK_CONFLICT` |
| Comentarios y docstrings | **Español** | `# Rechaza la escritura si el lease caducó` |
| Mensajes para el usuario (salida del CLI, texto de los errores) y logs | **Español** | `Bloque 3 replicado en datanode-2` |
| Documentación, README, informe, ADR | **Español** | — |
| Mensajes de commit | Tipo en inglés y descripción en **español** (ver [`CONTRIBUTING.md`](../CONTRIBUTING.md)) | `fix(datanode): verifica el hash antes de confirmar` |

Reglas:
- Los identificadores, nombres de fichero y nombres de host van **solo en ASCII**: sin tildes, sin `ñ` y sin espacios.
- No se mezclan idiomas dentro de un identificador: `get_bloque` está prohibido.
- Abreviaturas permitidas **solo** las de esta lista: `id`, `addr`, `config`, `auth`, `tls`,
  `mtls`, `cert`, `ca`, `rpc`, `api`, `cli`, `ttl`, `sha256`, `db`. Todo lo demás se escribe completo
  (`directory`, no `dir`; `replication`, no `repl`).

## 2. Nombres por tipo de artefacto

### Ficheros y carpetas
| Artefacto | Convención | Ejemplo |
|---|---|---|
| Carpetas y ficheros que no son Python (docs, scripts, configuración, despliegue) | `kebab-case` | `docs/fase-1/`, `scripts/deploy-aws.sh` |
| Paquetes y módulos Python | `snake_case` (Python no admite guiones en `import`) | `dfsha/datanode/block_store.py` |
| Tests | `tests/test_<módulo>.py` (pytest exige el prefijo) | `tests/test_replication.py` |
| Ficheros `.proto` | `snake_case.proto`, en una carpeta que coincide con el paquete | `proto/dfsha/v1/metadata.proto` |
| Registro de decisiones (ADR) | `NNNN-titulo-en-kebab.md`, numeración correlativa que nunca se reutiliza | `docs/decisiones/NNNN-politica-de-replicacion.md` |
| Diagramas | `NN-nombre.<ext>` para la fuente editable; la exportación lleva el mismo nombre | `docs/diagramas/02-despliegue.mmd` → `02-despliegue.png` |
| Evidencias de pruebas | Carpeta `AAAA-MM-DD-<escenario>` | `evidencias/2026-11-05-caida-datanode/` |
| Resultados de experimentos | `AAAA-MM-DD-<experimento>.csv` | `bench/resultados/2026-11-06-latencia-lectura.csv` |

### Código Python (PEP 8)
| Elemento | Convención | Ejemplo |
|---|---|---|
| Funciones, métodos, variables | `snake_case`, empezando por un verbo canónico (§3) | `get_block_locations()` |
| Clases | `PascalCase`, en singular | `BlockStore`, `LeaseManager` |
| Constantes | `UPPER_SNAKE` | `DEFAULT_BLOCK_SIZE_BYTES` |
| Booleanos | prefijo `is_`, `has_` o `can_` | `is_committed`, `has_lease` |
| Privados | prefijo `_` | `_verify_sha256()` |
| Magnitudes con unidad | **la unidad como sufijo, siempre** | `block_size_bytes`, `timeout_s`, `latency_ms`, `throughput_mb_s` |

### gRPC / Protocol Buffers
| Elemento | Convención | Ejemplo |
|---|---|---|
| Paquete | `dfsha.v1` (versión en el paquete) | `package dfsha.v1;` |
| Servicio | `PascalCase` con sufijo `Service`, uno por rol | `MetadataService`, `DataNodeService` |
| RPC | `PascalCase`, verbo canónico + objeto | `GetBlockLocations`, `CommitFile` |
| Mensajes | Un par `<Rpc>Request` / `<Rpc>Response` **por cada RPC**, aunque hoy coincidan | `CommitFileRequest` |
| Mensajes de datos reutilizables | `PascalCase`, sustantivo | `BlockLocation`, `NodeInfo` |
| Campos | `snake_case`, con la unidad como sufijo | `size_bytes`, `block_index` |
| Enums | Tipo en `PascalCase`; valores en `UPPER_SNAKE` con el nombre del tipo como prefijo; `_UNSPECIFIED = 0` | `NodeState`: `NODE_STATE_UNSPECIFIED`, `NODE_STATE_ALIVE` |

### API REST (si el diseño la usa)
| Elemento | Convención | Ejemplo |
|---|---|---|
| Rutas | Versión al principio, recursos en plural y en `kebab-case` | `GET /v1/files/{path}`, `POST /v1/files/{path}/lock` |
| Campos JSON | `snake_case`, para que coincidan con Python y proto | `{"block_id": "...", "size_bytes": 1048576}` |

### Errores
- Se usan primero los **códigos de estado estándar de gRPC**: `NOT_FOUND`,
  `ALREADY_EXISTS`, `PERMISSION_DENIED`, `UNAUTHENTICATED`, `FAILED_PRECONDITION`, `UNAVAILABLE`,
  `DEADLINE_EXCEEDED`, `ABORTED`.
- Para dar más detalle se añade un **código de motivo** propio en `UPPER_SNAKE` con forma
  `<OBJETO>_<PROBLEMA>`: `LOCK_CONFLICT`, `LEASE_EXPIRED`, `BLOCK_CORRUPTED`, `QUORUM_NOT_REACHED`.
- El texto del error, en español, es para el usuario; el código es para programas y pruebas.

### Configuración y entorno
| Elemento | Convención | Ejemplo |
|---|---|---|
| Variables de entorno | `UPPER_SNAKE` con prefijo `DFSHA_` | `DFSHA_METADATA_ADDR`, `DFSHA_REPLICATION_FACTOR` |
| Claves en YAML/TOML | `snake_case`, iguales al campo Python que alimentan | `replication_factor: 3` |
| Direcciones | Siempre `host:puerto` en variables terminadas en `_addr` | `DFSHA_DATANODE_ADDR=datanode-1:50052` |
| Listas de direcciones | `host:puerto` separados por comas, en variables terminadas en `_addrs` (ADR 0021) | `DFSHA_METADATA_ADDRS=metadata-1:50051,metadata-2:50051,metadata-3:50051` |
| Entornos | `local` (Docker Compose en una máquina, solo para desarrollo) y `aws` (varias EC2, el producto y las evidencias). Mismas imágenes y configuración en los dos (ADR 0030) | `deploy/local/`, `deploy/aws/` |

## 3. Verbos canónicos

Se usa **un verbo por intención** en funciones, RPC y rutas. Los sinónimos de la columna
derecha no se usan.

| Intención | Verbo | No usar |
|---|---|---|
| Leer un recurso | `get` | `fetch`, `retrieve`, `obtain` |
| Enumerar recursos | `list` | `get_all`, `enumerate` |
| Crear un recurso | `create` | `make`, `new`, `add` |
| Modificar un recurso | `update` | `modify`, `change`, `set` (salvo setters triviales) |
| Eliminar un recurso | `delete` | `remove`, `erase`, `destroy` |
| Reservar recursos para una escritura | `allocate` | `reserve`, `assign` |
| Hacer visible y definitiva una escritura | `commit` | `publish`, `finalize`, `save` |
| Descartar una escritura en curso | `abort` | `cancel`, `rollback` |
| Dar de alta un nodo en el clúster | `register` | `join`, `enroll` |
| Comprobar algo sin modificarlo | `verify` | `check`, `validate` (salvo validar entradas de usuario: `validate`) |
| Avisar al servidor de metadatos de algo observado | `report` | `notify`, `signal`, `send` |

Excepción: los nombres de las **primitivas y comandos del enunciado** se conservan
tal cual: `ls`, `cd`, `mkdir`, `rmdir`, `rm`, `put`, `get`, `open`, `close`, `read`, `write`,
`lock`, `unlock`. También `mv`, que no está en el enunciado pero es un comando equivalente de RF1 (ADR 0025).

## 4. Nombres de host y recursos de red

### Hosts del clúster
- Patrón **`<rol>-<n>`**, en minúsculas.
- Roles, de una lista cerrada: `metadata`, `datanode`, `client`. Un rol nuevo exige un ADR.
- `n` empieza en **1** y va sin ceros a la izquierda: `datanode-1`, `datanode-2`, … `datanode-10`.
- Los nombres cumplen RFC 1123: solo `a-z`, `0-9` y `-`, como máximo 63 caracteres, **sin guion bajo**
  (`_` no es válido en un nombre de host).
- **El mismo nombre en todas partes**: servicio de Docker Compose, `hostname`, `container_name`,
  logs, diagramas y documentación. Si en el diagrama pone `datanode-2`, en el log también.
- Un nodo conserva su nombre al reiniciarse. Un nodo que sustituye a uno caído recibe el siguiente
  número libre; los números no se reutilizan dentro de un experimento.
- **El repositorio no contiene IP literales** en código ni en configuración versionada. Las direcciones
  se resuelven por nombre (RNF7). Cómo se resuelven los nombres en AWS es una decisión de diseño y va
  en su propio ADR. Las IP solo pueden aparecer en `evidencias/`, como parte de la salida registrada.
- Los puertos se definen **por rol y en un único sitio** de la configuración, nunca como literal en el código.

### Recursos de AWS
La cuenta del Learner Lab se comparte con otros laboratorios, así que todo lo del proyecto lleva el
prefijo `dfsha-`.

| Recurso | Patrón | Ejemplo |
|---|---|---|
| Etiqueta `Name` de una EC2 | `dfsha-<rol>-<n>` | `dfsha-datanode-2` |
| `hostname` dentro de la EC2 | `<rol>-<n>` (sin prefijo, igual que en Docker) | `datanode-2` |
| Security group | `dfsha-sg-<rol>` | `dfsha-sg-datanode` |
| Volumen EBS de datos | etiqueta `Name` = `dfsha-<rol>-<n>-data` | `dfsha-datanode-2-data` |
| Bucket S3, si se usa | `dfsha-<uso>-<sufijo-único>` (los nombres de S3 son globales) | `dfsha-evidencias-pjg09` |

Todos los recursos llevan además la etiqueta `project=dfsha`, para poder listarlos y borrarlos juntos.

### Docker
| Recurso | Patrón | Ejemplo |
|---|---|---|
| Servicio y contenedor | `<rol>-<n>` | `datanode-1` |
| Imagen | `dfsha-<rol>:<versión>` | `dfsha-datanode:0.3.0` |
| Red | `dfsha-net` | — |
| Volumen | `<rol>-<n>-data` | `datanode-1-data` |

## 5. Estructura del repositorio (orientativa)

Las carpetas se crean cuando hacen falta, no antes.

```
dfsha/
├── .claude/               # skills (/adr, /commit) y plugins de Claude Code
├── CLAUDE.md               # instrucciones para sesiones de Claude Code
├── CONTRIBUTING.md         # reglas de commits, autoría y release
├── docs/
│   ├── enunciado.md        # transcripción fiel del enunciado oficial
│   ├── consejos-diseno.md  # condicionantes de diseño C1–C30
│   ├── convenciones.md     # este documento
│   ├── glosario.md
│   ├── decisiones/         # ADR (registro de decisiones del enunciado §2)
│   ├── diagramas/          # fuentes y exportaciones de diagramas, comunes a todos los documentos
│   ├── fase-1/             # documento de diseño individual
│   └── fase-2/             # informe final
├── proto/dfsha/v1/         # contratos gRPC
├── dfsha/                  # paquete Python: common/, metadata/, datanode/, client/
├── tests/
├── bench/                  # experimentos de rendimiento y sus resultados
├── deploy/                 # local/ (Docker Compose) y aws/
├── scripts/
└── evidencias/             # salida de las pruebas mínimas (§5.2 del enunciado)
```

## 6. Git y versiones

Las reglas de commits, ramas, etiquetas, release automático, autoría y lo que no se versiona
están en [`CONTRIBUTING.md`](../CONTRIBUTING.md), que es la única fuente para esos temas.
Resumen:

- Commits en formato Conventional Commits: `<tipo>(<ámbito>): <descripción en español>`, con la
  cabecera de 72 caracteres como máximo.
- Autor y committer siempre `pedroj1229@gmail.com`. Sin `Co-Authored-By` ni marcas de Claude Code.
- semantic-release publica una versión en cada push a `main` (ADR 0005). La serie es `0.y.z` hasta la fase II.
