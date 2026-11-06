# 0041 · Modelo de metadatos en etcd y cliente de etcd

- **Estado:** Aceptada
- **Fecha:** 2026-11-06
- **Requisitos relacionados:** RF1, RF2, RNF2, RNF4; ADR 0009, 0010, 0011, 0013, 0020, 0025 y 0039; fase I §4.2, §6 y §8

## Contexto
El ADR 0039 eligió etcd y dejó para la etapa 4 dos cosas: cómo se guarda el modelo de la §4.2 en claves de
etcd y qué cliente de Python se usa. El modelo tiene que cumplir:
- **Una sola transacción por cambio** (§4.2): confirmar una versión, `mv` o `rm` se aplica entero o no se aplica.
- **`mv` atómico de un directorio con todo su contenido** (§6.5). etcd admite como máximo 128 operaciones por
  transacción y peticiones de 1,5 MiB (ADR 0039).
- **Lecturas linealizables** (G2) y **reintentos idempotentes** con `request_id` durante 10 min (ADR 0020).
- **Cercado del líder** en cada escritura (ADR 0039).

Sobre el cliente, el 2026-11-06 se encontró que `etcd-sdk-python` 0.0.7 (`pyetcd`) tiene un fallo en su capa de
alto nivel: los filtros `min_create_revision` y `max_create_revision` rellenan `min_mod_revision`. Sus *stubs*
gRPC están generados para protobuf 5.27; funcionan con la 7.36 que usamos, pero eso puede romperse en cualquier
actualización. `aetcd` es asíncrono, y el servidor de metadatos usa el servidor gRPC con hilos.

## Opciones consideradas
**Claves del espacio de nombres**
1. **Ruta completa como clave** (`/u/docs/a.txt`). `ls` es un rango por prefijo, pero mover un directorio
   reescribe todas las claves de su contenido: un directorio con más de unas 60 entradas no cabe en una
   transacción, y `mv` deja de ser atómico.
2. **Entradas colgadas del identificador de su directorio padre**, como los inodos de un sistema de archivos.
   Mover un directorio cambia una sola entrada, tenga lo que tenga dentro.

**Cliente de etcd**
1. La capa de alto nivel de `etcd-sdk-python`: tiene el fallo descrito.
2. Solo sus *stubs* gRPC: dependen de código generado para otra versión de protobuf.
3. `aetcd`: obliga a mezclar asyncio con el servidor de hilos.
4. **Un subconjunto de los `.proto` oficiales de etcd v3.7.3**, generado con nuestras herramientas
   (ADR 0038), y un envoltorio propio pequeño.

## Decisión
Opción 2 para las claves y opción 4 para el cliente.

**Claves**, todas bajo el prefijo `/dfsha/`. Los valores son mensajes protobuf internos del servidor de metadatos.

| Clave | Valor | Entidad de la Tabla 13 |
|---|---|---|
| `leader` | Dirección del líder; ligada a su arrendamiento de etcd. Su revisión de creación es la época del líder | — (ADR 0039) |
| `entries/<user_id>/<directory_id>/<nombre>` | Tipo (archivo o directorio), `file_id` o `directory_id`, fecha | Directorio, y el nombre de cada archivo |
| `files/<file_id>` | Propietario, `block_size_bytes`, versión actual y clave de datos envuelta (etapa 6) | Archivo |
| `versions/<file_id>/<versión con 20 cifras>` | `block_id`, hash y tamaño de cada bloque, `size_bytes`, fecha, sustituida y su caducidad | Versión de archivo y bloque |
| `replicas/<block_id>/<node_id>` | Hash, tamaño, estado y fecha del aviso | Réplica |
| `pending/<lease_id>/<request_id>` | Los bloques que reservó una llamada a `AllocateBlocks`: índice, `block_id` y nodos | Escritura en curso |
| `leases/<file_id>/<lease_id>` | Usuario, rango de bloques y caducidad | Arrendamiento |
| `lease-guards/<file_id>` | Contador que cambia con cada arrendamiento del archivo | — |
| `requests/<user_id>/<request_id>` | Respuesta guardada; ligada a un arrendamiento de etcd de 10 min | Registro de peticiones |
| `nodes/<node_id>` | Nombre de host, dirección y capacidad | Nodo de datos (sin el estado de vida, que sigue en la memoria del líder) |

- La raíz de cada usuario es el directorio `root`. Una ruta se resuelve entrada a entrada, con todas las
  lecturas en la misma revisión de etcd, así que se ve un estado coherente.
- `ls` es un rango sobre `entries/<user_id>/<directory_id>/`. `rmdir` comprueba con ese mismo rango que el
  directorio está vacío.
- `mv` es una transacción que borra la entrada de origen y crea la de destino, comprobando que ninguna entrada
  de las dos rutas ha cambiado. Rechaza mover un directorio dentro de sí mismo.
- **Cada escritura es una sola transacción** que compara: que la clave `leader` sigue siendo del líder (su
  época), que lo leído no ha cambiado (por su revisión de modificación) y que el `request_id` no existe.
  Después aplica el cambio y guarda la respuesta.
- `LockBlocks` lee los arrendamientos del archivo, comprueba que no se solapan con uno vigente y se aplica
  comparando la revisión de `lease-guards/<file_id>`: si otro escritor cambió algo entre medias, se vuelve a
  evaluar. La caducidad de los arrendamientos la lleva el líder con su reloj (§8.1), no un arrendamiento de etcd,
  porque el modo seguro tiene que poder detenerla (ADR 0031).

**Líder:** la clave `leader` va ligada a un arrendamiento de etcd con TTL de 5 s, que el líder renueva cada
segundo. Renuncia si no lo ha renovado en 3,5 s (renuncia anticipada del ADR 0039). Los seguidores leen la clave
para responder `NODE_NOT_LEADER` con la dirección del líder. Son valores de partida; los ajusta E7.

**Cliente:** `proto/dfsha/etcd/rpc.proto` contiene, sin cambios en paquetes ni en números de campo, los mensajes
y servicios de etcd v3.7.3 que hacen falta: `KV` (`Range`, `Put`, `DeleteRange`, `Txn`), `Lease`
(`LeaseGrant`, `LeaseRevoke`, `LeaseKeepAlive`) y `KeyValue`, sin las anotaciones de OpenAPI ni de gogoproto. Se
genera con `scripts/generate-proto.sh` y lleva la cabecera de la licencia Apache 2.0 de etcd y su origen. Un
envoltorio en `dfsha/metadata/` ofrece lo que usa el servidor: lecturas en una revisión, transacciones con
comparaciones y arrendamientos. Las pruebas automáticas lo ejercitan contra un etcd v3.7.3 real.

## Consecuencias
- **Se gana:**
  - `mv` de un directorio es una sola entrada del log, sea cual sea su tamaño.
  - Ninguna transacción depende del tamaño del espacio de nombres.
  - El cliente usa el mismo protobuf y el mismo grpcio que el resto, sin capas de terceros con fallos conocidos.
- **Se pierde:**
  - Resolver una ruta cuesta una lectura por nivel. Las rutas son cortas y las lecturas de un mismo nivel van
    juntas; E1 lo medirá.
  - Hay que mantener el subconjunto de los `.proto` de etcd si se cambia de versión.
- **Límites:**
  - Un archivo cuya versión supere 1,5 MiB de metadatos no se puede confirmar: con bloques de 16 MiB son unos
    18 000 bloques, o 280 GiB.
  - Ninguna operación usa un número de operaciones de etcd que crezca con el número de bloques:
    `AllocateBlocks` guarda todos los bloques de una llamada en una sola clave, y `CommitFile` borra
    `pending/<lease_id>/` con un solo borrado por rango. Así se respeta el límite de 128 operaciones por
    transacción con archivos de cualquier número de bloques.
- **Cambia el plan:** los arrendamientos (`LockBlocks`, `UpdateLease`, `UnlockBlocks`) pasan a la etapa 4,
  porque `put` los necesita (§6.1). La etapa 8 se queda con la semántica de RF3 en el cliente y las pruebas
  de concurrencia.
- **Hasta la etapa 6:** un único usuario implícito, sin clave de datos y con descriptores de archivo sin
  firmar. Las claves ya llevan el `user_id`, así que la etapa 6 no cambia el modelo.
