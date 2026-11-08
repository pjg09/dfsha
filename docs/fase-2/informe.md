# DFSha: sistema de archivos distribuido con alta disponibilidad

## Informe técnico final · Fase II

**Proyecto 1 · Arquitectura de Nube y Sistemas Distribuidos · Universidad Pontificia Bolivariana · 2026-2**

**Arquitectura asignada:** opción 1, cliente/servidor con servicio distribuido entre servidores (S2S), operado dentro de una red privada virtual.

| Campo | Valor |
|---|---|
| Autor | **[[COMPLETAR: nombre completo]]** |
| Código | **[[COMPLETAR: código de estudiante]]** |
| Profesor | **[[COMPLETAR: nombre del profesor]]** |
| Grupo | **[[COMPLETAR: grupo]]** |
| Fecha | **[[COMPLETAR: fecha de entrega]]** |
| Versión del documento | 1.0, informe técnico final (fase II) |
| Versión del sistema | `v0.13.2` |
| Repositorio | https://github.com/pjg09/dfsha |

> 🟨🟨 **[ INSERTAR AQUÍ LA TABLA DE CONTENIDO, LA LISTA DE FIGURAS Y LA LISTA DE TABLAS ]** 🟨🟨

## Resumen

Este informe describe DFSha tal como quedó implementado y desplegado en la fase II: un sistema de archivos distribuido escrito en Python 3.12 con gRPC, que corre en nueve instancias EC2 del AWS Academy Learner Lab. Cada archivo se reparte en bloques de 16 MiB con tres réplicas en nodos de datos distintos, y los metadatos viven en un clúster de etcd de tres miembros, uno junto a cada servidor de metadatos, que los replica con Raft. El cliente solo conoce los nombres de los servidores de metadatos, y transfiere los bloques directamente con los nodos de datos.

La implementación cumple el diseño de la fase I sin simplificar ningún requisito: `read()` y `write()` con los cuatro modos de escritura, consistencia de apertura-cierre con cuatro garantías comprobadas, arrendamientos por rango de bloques, confirmación con dos de tres réplicas, modo seguro tras cada elección, re-replicación automática, TLS mutuo en todas las conexiones y cifrado de sobre en el cliente. Donde la implementación se apartó del diseño, cada cambio pasó por un registro de decisión: trece decisiones nuevas, de la 0036 a la 0048.

Las siete pruebas mínimas pasan en AWS con la versión final, y cada una deja su evidencia en el repositorio. Los nueve experimentos se ejecutaron con cinco repeticiones por punto. Un cliente transfiere a unos 130 MB/s con cualquier número de nodos de datos, la caída de un nodo de datos se detecta en unos 31 s y se re-replica en unos 12 s, y la caída del líder de metadatos deja unos 7 s sin escrituras de metadatos. Las pruebas en AWS sacaron a la luz cuatro fallos de tolerancia a fallos que no aparecían en las pruebas automáticas; los cuatro se corrigieron y se volvieron a medir. El informe termina con las limitaciones que quedan, la principal de las cuales es que la escalabilidad con varios clientes no se pudo medir con las nueve instancias del laboratorio.

**Palabras clave:** sistema de archivos distribuido, replicación, etcd, Raft, consistencia de apertura-cierre, arrendamientos, gRPC, TLS mutuo, cifrado de sobre, AWS.

# 1. Introducción

## 1.1 Objetivo del informe

El enunciado del proyecto pide, para la fase II, un repositorio con el código y las instrucciones reproducibles, un informe técnico final, un vídeo y una defensa [1]. Este documento es el informe técnico final. Según el enunciado, debe explicar la arquitectura, los cambios frente a los diseños individuales, las APIs, los algoritmos, el despliegue, las pruebas, los resultados y las limitaciones, y las secciones 2 a 9 siguen ese orden.

El diseño completo está en el documento de la fase I [2], que este informe no repite: aquí se cuenta qué se construyó, cómo se comprobó y qué se midió, y se remite a la sección correspondiente de la fase I cuando el mecanismo no cambió.

## 1.2 Qué se entrega

**Tabla 1.** Entregables de la fase II y dónde están.

| Entregable | Dónde | Contenido |
|---|---|---|
| Código | `dfsha/` (5 249 líneas de Python sin el código generado) | Cliente (CLI y biblioteca), servidor de metadatos, nodo de datos y módulos comunes |
| Contratos | `proto/dfsha/v1/` y el código generado en `dfsha/v1/` | Los tres servicios gRPC y sus mensajes |
| Pruebas automáticas | `tests/` (3 132 líneas, 158 pruebas) | Se ejecutan en GitHub Actions en cada cambio de `main` |
| Despliegue | `deploy/aws/` y `deploy/local/` | Clúster de 9 instancias en AWS con una orden; el mismo clúster en una máquina con Docker Compose |
| Instrucciones | `README.md` | Instalación, pruebas, entorno local, despliegue en AWS y uso del cliente, comprobadas desde un clon limpio (§7.4) |
| Evidencias | `evidencias/` | Salida de las siete pruebas mínimas y de los fallos provocados, con un índice |
| Experimentos | `bench/` y `bench/resultados/` | Arnés de medición, CSV de cada experimento y su resumen |
| Decisiones | `docs/decisiones/` | 48 registros de decisión (ADR): 35 de la fase I y 13 de la fase II |
| Este informe | `docs/fase-2/informe.md` y sus figuras en `docs/diagramas/fase-2/` | — |

El proyecto es individual, con autorización del profesor, y por eso no hay matriz comparativa de propuestas: en su lugar, la sección 3 recoge qué decisiones de la fase I cambiaron y por qué [3].

## 1.3 Cómo se construyó

La fase II se dividió en quince etapas, de la 0 (comprobar los supuestos de AWS) a la 14 (defensa), cada una con una condición de terminación verificable. Tres reglas de trabajo condicionan lo que cuenta este informe:

- **Ningún cambio de diseño sin su registro de decisión** (ADR). Una decisión aceptada no se edita: si cambia, la sustituye otra [4]. De ahí sale la tabla de cambios de la sección 3.
- **Toda evidencia se registra cuando se produce**, en texto y en el repositorio, con la versión, los comandos y la salida completa (ADR 0036). Las evidencias en texto son válidas según el profesor [3], así que este informe muestra las imprescindibles y remite a `evidencias/` para el resto [5].
- **Versionado automático.** Cada cambio sigue Conventional Commits, y semantic-release calcula la versión a partir de los mensajes. La serie fue de la `v0.1.0` a la `v0.13.2` en 18 versiones y unos 190 commits desde la entrega de la fase I. Cada imagen Docker lleva la versión como etiqueta inmutable, así que una medición siempre se puede atribuir a un código concreto.

# 2. Arquitectura implementada

## 2.1 Visión general

La arquitectura es la de la fase I [2, §3]: un plano de control, los servidores de metadatos, que dice dónde está cada bloque, y un plano de datos, los nodos de datos, que guarda y transfiere los bloques. El cliente pide al líder de metadatos la ubicación de los bloques y después habla directamente con los nodos de datos, como en GFS y HDFS [6], [7]. La Figura 1 muestra los componentes tal como están en el código.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 1 ]** · archivo: `docs/diagramas/fase-2/01-arquitectura-implementada.png` 🟥🟥

**Figura 1.** Componentes implementados. Las flechas continuas son el plano de datos y las discontinuas el plano de control. Todas las conexiones usan TLS mutuo.

Hay dos diferencias visibles con la Figura 2 de la fase I:
- **La máquina de estados replicada es etcd.** Cada servidor de metadatos tiene a su lado un miembro de etcd v3.7.3 en su propio contenedor, con los datos en el volumen EBS del servidor [8]. El servidor de metadatos es un cliente de etcd: cada cambio de metadatos es una transacción de etcd, y etcd la replica con Raft entre los tres miembros [9]. La elección del líder de DFSha también se hace sobre etcd (§5.4).
- **TLS mutuo en todas las conexiones**, también las del cliente. La fase I preveía TLS de servidor más un token para el cliente, pero la biblioteca gRPC de Python no permite pedir el certificado del cliente sin exigirlo (§3).

## 2.2 Componentes

**Tabla 2.** Módulos del código y su responsabilidad. Las líneas no incluyen el código generado de los `.proto`.

| Componente | Módulos principales | Líneas | Responsabilidad |
|---|---|---|---|
| Servidor de metadatos | `metadata/service.py`, `store.py`, `keys.py`, `etcd_client.py` | 1 600 | Espacio de nombres, versiones, arrendamientos, reservas de bloques y confirmaciones, todo como transacciones de etcd |
| | `metadata/leader.py` | 160 | Elección del líder, época y renuncia anticipada |
| | `metadata/nodes.py`, `replication.py` | 360 | Registro de nodos y su estado de vida, ubicación de réplicas, re-replicación, borrado de réplicas de más |
| Nodo de datos | `datanode/service.py`, `block_store.py` | 590 | `WriteBlock` con reenvío a las secundarias y confirmación con W réplicas; `ReadBlock`; almacén con área temporal y renombrado atómico |
| | `datanode/metadata_client.py`, `server.py` | 420 | Alta, latidos, informes de bloques, avisos, órdenes del líder y verificador periódico |
| Cliente | `client/client.py`, `file_handle.py`, `connection.py` | 900 | Biblioteca: `put`, `get`, `open`, `read`, `write`, `lock`, `close`; reintentos, nodos excluidos y vigilante de inactividad |
| | `client/cli.py` | 320 | CLI `dfsha` y su modo interactivo |
| Comunes | `common/security.py`, `tls.py`, `pki.py` | 440 | Tokens HMAC, cifrado de sobre, scrypt, TLS mutuo y generación de la CA y los certificados |
| | `common/errors.py`, `config.py`, `log.py` | 240 | Modelo de errores, configuración por variables de entorno y registro |

## 2.3 Tecnologías

**Tabla 3.** Tecnologías y versiones usadas.

| Pieza | Versión | Uso |
|---|---|---|
| Python | 3.12 | Todos los componentes |
| uv | 0.12.5 | Entorno y dependencias, con `uv.lock` versionado [10] |
| grpcio y protobuf | 1.85.1 y 7.36.2 | Comunicación entre componentes; `grpcio-status` para el modelo de errores [11] |
| cryptography | 50.0.2 | AES-256-GCM, scrypt y la CA interna [12] |
| etcd | v3.7.3, imagen fijada por su digest | Máquina de estados replicada de los metadatos [8] |
| Docker y Docker Compose | 29.1.3 y 2.40.3 (Ubuntu 26.04) | Un contenedor por rol; reinicio automático |
| AWS | EC2, EBS gp3, ECR, S3 en `us-east-1` | Instancias, volúmenes, registro de imágenes y copias de seguridad |
| pytest y pyright | 9.2.0 y 1.1.414 | Pruebas automáticas y comprobación de tipos en modo `standard` |
| semantic-release | — | Versión y notas de cada release, calculadas en GitHub Actions |

El cliente de etcd es propio: un subconjunto de los `.proto` oficiales de etcd con su código generado. Las bibliotecas de Python disponibles se probaron y se descartaron: `etcd-sdk-python` filtra mal por revisión de creación, un fallo que habría roto la época del líder [13], `aetcd` obliga a mezclar asyncio con el servidor de hilos, y `etcd3` no tiene versiones desde 2020 (ADR 0041).

# 3. Cambios frente al diseño de la fase I

La Tabla 4 recoge cada decisión de la fase II que cambia o completa el diseño de la fase I, con el registro que la justifica [4]. Las decisiones solo de proceso (evidencias, imágenes, entorno de Python) están en el Anexo A.

**Tabla 4.** Cambios frente al diseño de la fase I.

| Decisión de la fase I | Qué cambió en la fase II | Por qué | ADR |
|---|---|---|---|
| Raft en los servidores de metadatos, con etcd o PySyncObj por decidir (§3.3, §14) | etcd v3.7.3, un miembro por servidor; el servidor de metadatos es su cliente. Líder elegido con una clave de etcd con TTL de 5 s; su época es la revisión de creación de esa clave | PySyncObj no escribía su log en disco antes de confirmar y admite dos líderes a la vez [14]. etcd escribe cada entrada en disco antes de confirmarla, y su consistencia está analizada de forma independiente [15] | 0039 |
| Modelo de metadatos de la §4.2, sin forma de almacenamiento | Un esquema de claves de etcd, con cada cambio en una transacción que comprueba la época del líder, lo leído y el `request_id` | Atomicidad de `CommitFile`, `mv` y `rm` en una sola entrada del log replicado | 0041 |
| Despliegue: una imagen por rol y un contenedor por instancia | Además, un contenedor de etcd junto a cada servidor de metadatos | Consecuencia de elegir etcd | 0040 (sustituye a 0027) |
| `RegisterDataNodeRequest` con el nombre de host | Lleva también la dirección `host:puerto` del nodo | El puerto quedaba definido en dos sitios | 0042 |
| TLS de servidor más token para el cliente; TLS mutuo entre nodos (§10.4) | TLS mutuo en todas las conexiones; el rol sale del SAN del certificado; límite de 5 intentos de contraseña fallidos | gRPC para Python no permite pedir un certificado de cliente sin exigirlo [16] | 0043 |
| Al repetir un bloque, el líder da «otros tres» nodos (§11.3) | `AllocateBlocks` admite los nodos que ya fallaron con ese bloque | El líder volvía a dar el nodo recién caído, que aún contaba como vivo | 0044 |
| `client-1` en una t3.micro (§3.6) | `client-1` en una t3.small | La memoria del cliente no bastaba para E4 y E5 | 0045 |
| E8 de extremo a extremo, con y sin seguridad | E8 mide cada pieza de la seguridad por separado | La seguridad no se puede desactivar en el código; añadir ese modo era un riesgo | 0046 (sustituye a 0028) |
| El cliente cambia de réplica si una no responde (§11.4) | Un vigilante de inactividad corta una transferencia que pasa 10 s sin ningún mensaje | Un nodo congelado aceptaba la conexión y retenía la lectura 120 s | 0047 |
| Re-replicación hacia nodos vivos (§9.3) | Solo entre nodos con un latido de 4,5 s o menos; una orden sin respuesta se repite a los 15 s, no a los 60 | Un bloque pasó 61 s con dos réplicas por una orden hacia un nodo recién caído | 0048 |

El resto del diseño de la fase I se implementó como estaba. Ningún requisito se simplificó.

# 4. APIs

## 4.1 Servicios

Los contratos están en `proto/dfsha/v1/`, que es la fuente desde la etapa 1 (ADR 0038): `common.proto` (bloques, tokens, ubicaciones), `metadata.proto` (servicio `MetadataService`), `datanode.proto` (servicio `DataNodeService`) y `records.proto` (mensajes internos que el servidor de metadatos guarda en etcd). La Tabla 5 resume los 23 RPC.

**Tabla 5.** Servicios y RPC implementados.

| Servicio | RPC | Quién llama | Para qué |
|---|---|---|---|
| `MetadataService` (puerto 50051) | `Authenticate`, `CreateUser` | Cliente | Token de acceso; alta de usuarios por un administrador |
| | `ListDirectory`, `GetFileInfo`, `CreateDirectory`, `DeleteDirectory`, `DeleteFile`, `MovePath` | Cliente | Espacio de nombres (RF1) |
| | `OpenFile`, `GetBlockLocations` | Cliente | Abre una versión de archivo y da la ubicación de sus bloques, con un token de bloque por bloque |
| | `LockBlocks`, `UpdateLease`, `UnlockBlocks` | Cliente | Arrendamientos por rango de bloques (RF3) |
| | `AllocateBlocks`, `CommitFile`, `AbortFile` | Cliente | Reserva de bloques nuevos, confirmación atómica de una versión y abandono de una escritura |
| | `RegisterDataNode`, `ReportHeartbeat`, `ReportBlocks`, `ReportBlockReceived`, `ReportCorruptReplica` | Nodo de datos | Alta, latidos (la respuesta trae las órdenes y la época), informes de bloques, aviso de bloque recibido y aviso de réplica corrupta |
| `DataNodeService` (puerto 50052) | `WriteBlock` | Cliente y nodo de datos | Flujo de mensajes de 1 MiB; la primaria reenvía a las secundarias y responde con W réplicas |
| | `ReadBlock` | Cliente | Flujo de mensajes de 1 MiB con el hash del bloque |

Cada llamada lleva un plazo, y las que cambian algo llevan un `request_id`: durante 10 min, un reintento devuelve la respuesta guardada en lugar de repetir el cambio [2, §8.6]. Los errores siguen el modelo de la §5.4 de la fase I: un código gRPC estándar más un `ErrorInfo` con la razón (`LOCK_CONFLICT`, `VERSION_CONFLICT`, `NODE_NOT_LEADER`, `SAFE_MODE_ACTIVE`, `QUORUM_NOT_REACHED`, …) y metadatos como la dirección del líder [11].

## 4.2 Cambios del contrato frente al Anexo A

Todos los cambios del contrato público son campos nuevos, compatibles con el Anexo A de la fase I: un cliente o un nodo que no los envía se comporta como antes.

**Tabla 6.** Cambios del contrato frente al Anexo A de la fase I.

| Mensaje | Campo nuevo | Para qué | ADR |
|---|---|---|---|
| `ReportHeartbeatResponse` y `ReportBlocksResponse` | `leader_epoch` | Ficha de cercado: el nodo de datos descarta órdenes de una época menor | 0039 |
| `RegisterDataNodeRequest` | `addr` | Dirección por la que los demás alcanzan al nodo | 0042 |
| `AllocateBlocksRequest` | `excluded_datanode_addrs` | Nodos que ya fallaron con esos bloques | 0044 |
| Error `QUORUM_NOT_REACHED` de `WriteBlock` | Metadato `failed_addrs` | Secundarias que no guardaron el bloque, para excluirlas al repetirlo | 0044 |

`records.proto` es nuevo, pero interno: lo escribe y lo lee solo el servidor de metadatos (ADR 0041 y 0043).

# 5. Algoritmos

Esta sección describe los algoritmos tal como están en el código. Los flujos básicos de carga, lectura, modificación y borrado son los de la sección 6 de la fase I, con sus diagramas de secuencia [2, §6]; aquí se cuenta lo que la implementación concretó o cambió.

## 5.1 Escritura

1. **Apertura.** `OpenFile` devuelve un descriptor de archivo firmado con la versión base y, en modo creación, una clave de datos nueva envuelta con la clave de envoltura (§5.8).
2. **Preparación local.** `write()` prepara en el cliente, en un archivo del área temporal, solo los bloques que cambian. Nada viaja hasta `close()`.
3. **Arrendamiento.** Antes de enviar, el cliente arrienda el rango de bloques afectado (`LockBlocks`, TTL de 30 s) y lo renueva mientras dura el envío.
4. **Reserva.** `AllocateBlocks` da a cada bloque nuevo un `block_id` y tres nodos de datos: los vivos con más espacio libre y sitio para el bloque, con desempate aleatorio, y la primaria rotando entre bloques consecutivos [2, §4.3]. Deja la reserva anotada como escritura en curso.
5. **Transferencia.** Cada bloque se cifra con AES-256-GCM y se envía a su primaria en mensajes de 1 MiB, con 4 bloques en paralelo. La primaria escribe en su área temporal, reenvía a las dos secundarias mientras recibe, comprueba el SHA-256 del bloque, lo renombra a su sitio definitivo y responde en cuanto lo tienen W = 2 réplicas, ella incluida. La tercera termina en segundo plano.
6. **Confirmación.** `CommitFile` comprueba en una sola transacción de etcd la época del líder, que el arrendamiento sigue vigente y que nadie confirmó otra versión de esos bloques desde la versión base. Si todo se cumple, la versión nueva queda visible de forma atómica con sus bloques; si no, el cliente recibe `VERSION_CONFLICT` o `LEASE_EXPIRED` y nada cambia.

Si un bloque falla, el cliente lo reserva de nuevo excluyendo los nodos que fallaron (Figura 2 y §5.3). Un bloque reservado que no llega a ninguna versión no pertenece a nada vivo, y la recolección de basura lo borra (§5.7).

## 5.2 Lectura

`get` y `read` abren la versión vigente, piden la ubicación de los bloques y los leen en paralelo de cualquiera de sus réplicas: no hace falta quórum de lectura, porque un bloque nunca cambia una vez escrito (copia en escritura). El nodo de datos comprueba el SHA-256 de la réplica mientras la envía, y el cliente lo vuelve a comprobar antes de descifrar. Si una réplica falla, no responde o está corrupta, el cliente pasa a la siguiente; dentro de un mismo `get`, las réplicas que ya fallaron se prueban las últimas. Una réplica corrupta se avisa al líder, que la marca y deja de entregarla [2, §8.5].

**Vigilante de inactividad (ADR 0047).** El plazo de 120 s de una transferencia limita su duración total, no su progreso. En E6 se vio que un nodo de datos congelado acepta la conexión y no responde, y que cada lectura de ese nodo esperaba los 120 s completos (§8.6). Desde la `v0.13.1`, cada lectura y cada escritura de bloque lleva un vigilante que se reinicia con cada mensaje y corta la llamada si pasan 10 s sin ninguno. Se descartó el keepalive de gRPC: solo vigila la conexión, exige configurar también los servidores y no se recomienda por debajo de un minuto [17].

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 2 ]** · archivo: `docs/diagramas/fase-2/02-repeticion-de-bloque.png` 🟥🟥

**Figura 2.** Repetición de un bloque cuya primaria falla: el cliente lo reserva de nuevo excluyendo el nodo que falló (ADR 0044). Si la primaria está congelada, el vigilante de inactividad corta la llamada a los 10 s (ADR 0047).

## 5.3 Fallos durante la escritura y nodos excluidos

Un nodo de datos que acaba de caer sigue contando como vivo para el líder hasta 9 s sin latido [2, §9.2]. En el escenario 3, en AWS, el líder volvió a dar como primaria un nodo recién caído en las cuatro reservas de un mismo bloque, y la carga falló. Desde el ADR 0044, el cliente informa en `AllocateBlocks` de los nodos que ya fallaron con ese bloque, y el líder no los elige para esa reserva (Figura 2):
- Si el cliente no pudo hablar con la primaria, o el vigilante cortó la llamada, excluye la primaria.
- Si la primaria respondió `QUORUM_NOT_REACHED`, excluye las secundarias que ella indica en `failed_addrs`. La primaria está sana entonces, y excluirla sería equivocado: un primer intento de corrección lo hacía y rompió una prueba.

Los nodos excluidos solo cuentan para esa reserva; el líder no los recuerda, así que un cliente no puede sacar del reparto a un nodo sano para los demás.

## 5.4 Elección del líder y cercado

El líder de los servidores de metadatos es el que tiene la clave `leader` de etcd, ligada a un arrendamiento de etcd con TTL de 5 s que renueva cada segundo. Si la clave no existe, cualquier servidor intenta crearla con una transacción condicional, y solo uno lo consigue. La revisión de etcd en la que se creó es la **época del líder**, que crece en cada elección. La Figura 3 muestra cómo se usa para que un líder depuesto no cause daño, con tres defensas (ADR 0039):

1. **Época en cada escritura.** Cada transacción del líder compara la revisión de creación de `leader` con su época. Un líder depuesto no puede escribir: su transacción falla aunque él siga creyéndose líder.
2. **Ficha de cercado en las órdenes.** Las respuestas a los latidos llevan la época. Cada nodo de datos recuerda la mayor que ha visto y descarta las órdenes de una época menor, así que un líder depuesto no puede ordenar borrados ni re-replicaciones.
3. **Renuncia anticipada.** Un líder que lleva 3,5 s sin renovar su arrendamiento, según su reloj monótono, deja de actuar como tal y responde `NODE_NOT_LEADER`, antes de que caduque la clave. No basta sola, porque una pausa del proceso puede saltarse la comprobación; por eso existen las dos anteriores.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 3 ]** · archivo: `docs/diagramas/fase-2/03-eleccion-y-cercado.png` 🟥🟥

**Figura 3.** Elección de un líder nuevo y cercado del anterior. Los números de época son de ejemplo.

Los cerrojos de etcd con arrendamiento no garantizan por sí solos la exclusión mutua: dos procesos pueden creer tener el mismo cerrojo [15]. Por eso la época viaja dentro de cada transacción y de cada orden, la misma técnica de cercado que usa HDFS con sus JournalNodes [18].

**Restaurar una copia de seguridad** haría retroceder las revisiones de etcd, y con ellas la época: los nodos de datos rechazarían al nuevo líder. `deploy.sh restore` restaura con `--bump-revision 1000000000` [19]. En la prueba de restauración, el nuevo líder tuvo la época 2 000 000 252, y los nodos de datos lo aceptaron.

## 5.5 Modo seguro

Tras cada elección, el estado de vida de los nodos de datos, que solo existe en la memoria del líder, empieza vacío. Un líder recién elegido que re-replicara en ese momento lo haría con todos los bloques. El modo seguro lo impide [2, §9.5]: el líder no confirma escrituras (`SAFE_MODE_ACTIVE`) ni da órdenes hasta que cada bloque vivo tiene una réplica sana en un nodo que ya envió un latido al líder nuevo, o hasta un tope de 60 s. Al salir, renueva los arrendamientos vigentes por su TTL completo, porque sus escritores no pudieron renovarlos durante el modo seguro. Medido en AWS, sale siempre por la condición, en 0,5–2,4 s (E7 y E9).

## 5.6 Detección de fallos y re-replicación

Cada nodo de datos envía un latido cada 3 s. Sin latido en 9 s pasa a sospechoso, y en 30 s a caído. Cada 3 s, una pasada de mantenimiento del líder compara las réplicas sanas de cada bloque vivo con R = 3:
- **Con menos de 3**, ordena re-replicarlo desde una réplica sana a otro nodo, empezando por los bloques con menos réplicas y con 4 re-replicaciones como máximo por nodo origen y pasada.
- **Con más de 3**, ordena borrar las de más, en los nodos con menos espacio libre.
- **Réplica corrupta:** se borra solo cuando el bloque ya tiene 3 réplicas sanas.

Las órdenes viajan en la respuesta al siguiente latido del nodo, y una orden que no termina con un aviso de bloque recibido en 15 s se vuelve a calcular.

**Nodos con latido reciente (ADR 0048).** En el escenario 2 repetido con la `v0.13.1`, el líder eligió como destino de una re-replicación un nodo parado 5 s antes, que aún contaba como vivo. La orden falló sin que el líder lo supiera, y el bloque pasó 61 s con dos réplicas, hasta que venció el plazo de entonces, 60 s. Desde la `v0.13.2`, el origen y el destino de una re-replicación tienen que haber enviado un latido en los últimos 4,5 s, y el plazo baja a 15 s, unas 8 veces la re-replicación más lenta medida (1,9 s desde la orden). Repetido en AWS con el nodo de más espacio libre recién parado, los cinco bloques con dos réplicas vuelven a tres en 3 s, y ninguna orden va hacia el nodo parado (§7.3).

## 5.7 Recolección de basura y verificación periódica

**Recolección de basura.** Cada nodo de datos envía cada 5 min un informe con todos sus bloques, y el líder ordena borrar los que no pertenecen a nada vivo: ni a una versión vigente, ni a una versión sustituida durante su periodo de gracia de 10 min (para los lectores que la abrieron), ni a una escritura en curso. En la prueba de AWS se borraron 60 réplicas y ninguna viva [5].

**Verificador periódico.** Cada nodo de datos recorre sus bloques una vez al día a 4 MB/s como máximo, y comprueba su SHA-256. Una réplica corrupta se avisa al líder igual que si la hubiera encontrado una lectura.

## 5.8 Seguridad

La implementación sigue la sección 10 de la fase I, con los cambios del ADR 0043 (Figura 1 y Tabla 4):
- **TLS mutuo en todas las conexiones**, con una CA interna (EC P-256) que genera `python -m dfsha.common.pki`. El rol del otro extremo sale del nombre `<rol>-<n>` del SAN de su certificado. Las RPC de usuario exigen un certificado de rol `client` y un token de acceso, y las de los nodos de datos, el certificado de ese mismo nodo. La negociación da TLS 1.3 [20].
- **Usuarios** con contraseñas guardadas con scrypt (n = 2^15, r = 8, p = 1, sal de 16 bytes) [21]. Tras 5 intentos fallidos seguidos, el usuario no puede entrar durante 30 s. El primer administrador lo crea el líder con la contraseña del secreto de despliegue.
- **Tokens** de acceso (1 h), descriptores de archivo y tokens de bloque (10 min), firmados con HMAC-SHA256 y un prefijo distinto por tipo, para que la firma de uno no valga para otro [22]. Se aceptan 30 s de desfase de reloj.
- **Cifrado de sobre** en el cliente: cada archivo tiene una clave de datos aleatoria, cada bloque se cifra con AES-256-GCM y un nonce de 12 bytes, y la clave de datos se guarda envuelta con la clave de envoltura de los servidores de metadatos, con el `file_id` como dato asociado [23]. Los nodos de datos solo ven bytes cifrados, y la re-replicación copia bytes cifrados sin descifrarlos.
- **Clave de envoltura** fuera del volumen de metadatos y de la copia de seguridad (ADR 0035): quien robe un volumen o una copia de S3 no puede descifrar nada.

# 6. Despliegue

## 6.1 Clúster en AWS

La Figura 4 muestra el despliegue en el AWS Academy Learner Lab: tres servidores de metadatos en t3.small, cinco nodos de datos en t3.micro y un cliente en t3.small, todos en una zona de disponibilidad de `us-east-1`. Cada servidor de metadatos tiene un volumen EBS de 4 GiB para etcd, y cada nodo de datos uno de 10 GiB para sus bloques, todos cifrados.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 4 ]** · archivo: `docs/diagramas/fase-2/04-despliegue-implementado.png` 🟥🟥

**Figura 4.** Despliegue implementado en AWS: instancias, contenedores, volúmenes, grupos de seguridad, registro de imágenes y bucket de copias de seguridad.

`deploy/aws/deploy.sh` usa el AWS CLI con las credenciales de la sesión del laboratorio:
- **`images`** construye las tres imágenes y las envía a ECR con etiquetas inmutables: una versión siempre corresponde a los mismos bytes [24].
- **`up`** crea los grupos de seguridad, las instancias con Ubuntu 26.04 [25] y los volúmenes.
- **`install`**, en cada instancia:
  - instala Docker y lo hace esperar al montaje del volumen de datos (`RequiresMountsFor`), para que etcd nunca arranque sobre un directorio vacío del disco raíz;
  - comprueba que chrony está sincronizado;
  - escribe `/etc/hosts` con los nombres `<rol>-<n>`, porque no hay DNS privado y ninguna IP queda en el repositorio;
  - instala los secretos y arranca los contenedores con reinicio automático [26].
- **`all`** hace los tres pasos.
- **`status`**, **`backup`**, **`restore`** y **`down`** completan el ciclo.

`deploy/aws/run.sh` ejecuta órdenes en una instancia o la CLI en `client-1`.

**Tiempos medidos.** Sin ningún recurso del proyecto en AWS, `deploy.sh all` levanta el clúster sin intervención en 6 min 19 s:
- 18 s para las imágenes;
- 4 min 38 s para los recursos: cada volumen tarda unos 24 s, y se crean uno tras otro;
- 1 min 23 s para la instalación de los 9 hosts en paralelo.

Tras una parada del laboratorio, el clúster vuelve solo en unos 31 s (E9, §8.9).

## 6.2 Entorno local

`deploy/local/compose.yaml` levanta el mismo clúster de 12 contenedores en una sola máquina, con las mismas imágenes, nombres de host y certificados. Sirve para desarrollar y para las pruebas de integración, pero no da evidencias: la red, el disco y la CPU de una máquina no se parecen a los de AWS. Por ejemplo, en local los cinco nodos comparten disco, y la ubicación por espacio libre los veía desiguales.

## 6.3 Copias de seguridad

Raft protege frente a la pérdida de un servidor de metadatos, pero no frente a la de los tres ni frente a un borrado por error, que se replica a todos. `deploy.sh backup` guarda una instantánea de etcd en un bucket privado y cifrado de S3. La restauración es manual, y se probó en AWS: se recupera lo anterior a la copia y se pierde lo posterior, como se diseñó [2, §4.2].

La copia es manual a propósito. Así ningún componente del clúster tiene credenciales de AWS, y la única que las tiene es la máquina de administración (C27). La consecuencia está en §9.

## 6.4 Integración continua y versiones

En cada cambio de `main`, GitHub Actions:
1. instala las dependencias exactas de `uv.lock`;
2. arranca un etcd v3.7.3;
3. comprueba que el código generado coincide con los `.proto`;
4. ejecuta pytest y pyright.

semantic-release calcula la versión a partir de los mensajes de commit, y el paquete de Python la toma de la etiqueta de Git con hatch-vcs [27]. Una versión `fix` o `feat` produce una etiqueta `vX.Y.Z`, y las imágenes de esa versión se construyen una sola vez.

# 7. Pruebas

## 7.1 Pruebas automáticas

158 pruebas en 17 módulos de prueba, que se ejecutan en unos 75 s, con un etcd real en Docker:
- **Unitarias:** almacén de bloques, configuración, errores, seguridad, TLS, registro de nodos, re-replicación con un reloj falso.
- **De integración:** un clúster local completo dentro del proceso de pruebas, con servidores de metadatos, nodos de datos y cliente reales sobre gRPC con TLS mutuo. Cubren:
  - los cuatro modos de escritura y las garantías G1–G4;
  - los conflictos entre escritores y la caducidad de los arrendamientos;
  - la elección y el cercado del líder, el modo seguro;
  - la caída de nodos durante una escritura y la re-replicación;
  - las réplicas corruptas, la recolección de basura y el reinicio de los nodos.

Cada corrección de un fallo encontrado en AWS lleva una prueba que lo reproduce, y se comprobó que esa prueba falla sin la corrección. pyright, en modo `standard`, no da ningún error.

## 7.2 Pruebas mínimas en AWS

El enunciado pide siete pruebas mínimas con su evidencia [1]. Todas se hicieron en AWS, primero cuando su funcionalidad estuvo lista y después con la versión final; las dos ejecuciones están en el repositorio (Tabla 7). La `v0.13.2` solo cambia la re-replicación del líder, así que las dos pruebas que pasan por ella se repitieron con esa versión, y las otras cinco con la `v0.13.1`.

**Tabla 7.** Pruebas mínimas con la versión final.

| Prueba | Qué se comprueba | Resultado | Evidencia |
|---|---|---|---|
| Carga y recuperación | Un archivo de 1 GiB se reparte en bloques con 3 réplicas en nodos distintos y se recupera idéntico | 64 bloques, 192 réplicas en los 5 nodos; el mismo SHA-256 y `cmp` idéntico; `put` a 137 MB/s y `get` a 124 MB/s | `2026-11-08-carga-y-recuperacion` |
| Acceso RF3 | `read()` y `write()` con la semántica de la §7 de la fase I | Creación, anexado, dos modificaciones parciales y dos reemplazos coinciden con un modelo local y solo crean los bloques afectados; G2, G3 y G4 se cumplen | `2026-11-08-acceso-rf3` |
| Concurrencia | Dos clientes sobre el mismo archivo y bloque | El segundo recibe `LOCK_CONFLICT` y, si reintenta desde su versión base, `VERSION_CONFLICT`; en bloques distintos, los dos confirman; si el primero muere, el segundo escribe a los 27 s; si reaparece, recibe `LEASE_EXPIRED` | `2026-11-08-concurrencia` |
| Replicación y fallos | Caída de un nodo de datos durante lecturas y escrituras | Durante la caída, `get` de 1 GiB con el mismo hash y `put` confirmado; a los 47 s todos los bloques tienen 3 réplicas sin el nodo caído; al volver, sus réplicas de más se borran | `2026-11-08-replicacion-y-fallos` |
| Consistencia (escenario 2) | Una réplica desconectada durante una escritura | La escritura se confirma con W = 2; la ubicación nunca muestra el nodo desconectado; la lectura ve la versión nueva (G2); la re-replicación completa los bloques en 3 s | `2026-11-08-escenario-2` |
| Seguridad | Acceso autorizado y denegado; TLS en el canal; bloques cifrados en disco | Las 7 llamadas indebidas se rechazan; TLS 1.3; un usuario no ve los archivos de otro; límite de intentos; una marca repetida 50 000 veces no aparece en ninguna de las 438 réplicas | `2026-11-08-seguridad` |
| Rendimiento | Latencia y tasa de transferencia en al menos dos condiciones | E1 con tres tamaños de archivo, con la versión final (Tabla 8) | `bench/resultados/2026-11-08-e1.md` |

## 7.3 Escenarios obligatorios

Los cuatro escenarios de la sección 11 de la fase I se provocaron en AWS.
- **Escenario 1, dos procesos escriben el mismo bloque:** es la prueba de concurrencia de la Tabla 7.
- **Escenario 2, una réplica desconectada durante una escritura:** es la prueba de consistencia de la Tabla 7. Con la `v0.13.1`, un bloque tardó 61 s en recuperar su tercera réplica; con la `v0.13.2`, 3 s (§5.6).
- **Escenario 3, un nodo falla a mitad de un bloque:** durante una carga de 1 GiB, seis bloques fallan en el nodo caído, una sola vez cada uno, y se repiten en otros nodos. La carga se confirma en 8,0 s con el mismo SHA-256. Un observador no ve el archivo hasta la confirmación. Al volver, el nodo borra de su área temporal los dos bloques a medias que dejó.
- **Escenario 4, el cliente desconoce la ubicación de los bloques:** la única dirección que conoce `client-1` es la lista de los tres servidores de metadatos. Un seguidor responde `NODE_NOT_LEADER` con la dirección del líder, el cliente lo sigue, y las ubicaciones llegan como nombres (`datanode-2:50052`) que resuelve `/etc/hosts`. Ninguna IP está en el repositorio fuera de las evidencias (RNF7).

## 7.4 Otras comprobaciones en AWS

- **Recolección de basura:** se borran las réplicas de escrituras abortadas y de versiones sustituidas tras su periodo de gracia, y ninguna viva: de 270 réplicas quedan 213, exactamente las de las versiones vigentes.
- **Restauración de metadatos:** se pierde el estado de etcd en los tres servidores y se restaura la copia de S3. Vuelven los archivos anteriores a la copia, con el mismo hash, y el líder nuevo tiene una época mayor.
- **Arranque en frío real:** al empezar una sesión nueva del laboratorio, el clúster vuelve solo, elige líder, y los nodos de datos se dan de alta e informan de sus bloques, en unos 18–20 s desde que arrancan las instancias.
- **Despliegue desde cero y README desde cero:** desde un clon limpio de GitHub, cada orden del `README.md` se ejecutó tal como está escrita: instalación, pruebas, entorno local, `deploy.sh down` y `all` en AWS y cliente. Salieron dos fallos del README, un archivo de ejemplo que ningún paso creaba y la semántica de `unlock` sin explicar, y uno de `deploy.sh status`. Los tres se corrigieron.

# 8. Resultados de los experimentos

## 8.1 Método

Los nueve experimentos se definieron en la fase I [2, §12] y se ajustaron en el ADR 0046. Se ejecutaron en el clúster de la Figura 4 con este método:
- **Repeticiones:** 5 por punto. Se informa la mediana y el p95 de rango más cercano, que con 5 repeticiones coincide con el máximo.
- **Unidades:** tiempos medidos en el cliente, en MB/s (10^6 bytes por segundo).
- **Datos:** archivos de contenido aleatorio, con el SHA-256 comparado fuera del tiempo medido.
- **Instancias:** las t3 en modo de créditos `unlimited`, para que el agotamiento de créditos no limite la CPU [28].
- **Registro:** cada fila del CSV lleva la versión, el tipo de instancia del cliente y el modo de créditos. Cada experimento tiene en `bench/resultados/` su CSV, su registro y un resumen con la condición exacta.

Los experimentos se hicieron con versiones entre la `v0.12.0` y la `v0.13.1`, según cuándo estuvo lista cada funcionalidad. Cada resumen indica la suya. La configuración fue la de producción salvo donde el experimento la varía, con una excepción: durante E2 a E9, el periodo de gracia bajó a 60 s y el informe de bloques a cada 60 s, para que los archivos borrados entre repeticiones no llenaran los volúmenes de 10 GiB.

## 8.2 E1 · Tamaño del archivo

**Tabla 8.** E1 con la `v0.13.1`, en la misma sesión que las pruebas mínimas con la versión final: `put` y `get` con 5 nodos de datos, R = 3, W = 2, bloques de 16 MiB, cifrado y TLS mutuo.

| Operación | Tamaño | Latencia mediana | Latencia p95 | Tasa mediana |
|---|---|---|---|---|
| `put` | 16 MiB | 327 ms | 351 ms | 51,3 MB/s |
| `put` | 256 MiB | 1 866 ms | 2 022 ms | 143,9 MB/s |
| `put` | 1 GiB | 8 378 ms | 8 386 ms | 128,2 MB/s |
| `get` | 16 MiB | 198 ms | 200 ms | 84,9 MB/s |
| `get` | 256 MiB | 2 120 ms | 2 258 ms | 126,6 MB/s |
| `get` | 1 GiB | 8 112 ms | 9 097 ms | 132,4 MB/s |

Con un solo bloque (16 MiB) domina el coste fijo de abrir, arrendar, reservar y confirmar: un `put` de 16 MiB tarda 327 ms, cuando el bloque solo necesitaría unos 130 ms a 130 MB/s. A partir de 256 MiB la tasa se estabiliza en torno a 130 MB/s. La medición con la `v0.12.0` daba lo mismo a 1 GiB (128 y 136 MB/s), así que las correcciones posteriores no empeoraron la tasa [5].

## 8.3 E2 y E4 · Número de nodos y de clientes

La Figura 5 reúne los dos experimentos que debían mostrar la escalabilidad.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 5 ]** · archivo: `docs/diagramas/fase-2/05-tasa-de-transferencia.png` 🟥🟥

**Figura 5.** Tasa de transferencia mediana con un cliente y 3, 4 o 5 nodos de datos (E2), y tasa agregada con 1 a 8 clientes en `client-1` (E4).

- **E2:** con 3, 4 y 5 nodos de datos, un cliente transfiere 1 GiB a la misma tasa: 127–128 MB/s en `put` y 136–137 MB/s en `get`. El límite lo pone el cliente, no los nodos.
- **E4, archivos distintos:** con varios procesos cliente en `client-1`, la tasa agregada sube hasta unos 130 MB/s con 4 clientes y no pasa de ahí con 8. Es el mismo techo que un solo cliente con archivos grandes: el límite es la máquina cliente.
- **E4, mismo bloque:** los conflictos crecen más deprisa que los clientes: 18, 102 y 498 con 2, 4 y 8 clientes en 5 repeticiones. El cliente reintenta enseguida tras un `LOCK_CONFLICT`, así que cada escritor que espera vuelve a chocar. Ninguna escritura se pierde ni se mezcla.

Ninguna de las dos mediciones muestra que la tasa agregada crezca con más clientes en máquinas distintas, que es lo que demostraría la escalabilidad horizontal (RNF1). Lo que sí muestran es que, por debajo de unos 130 MB/s, el clúster no es el cuello de botella. La limitación se analiza en §9.

## 8.4 E3 · Quórum de escritura

Con W = 3, la escritura de un bloque de 16 MiB tarda unos 15 ms más que con W = 2 (194 frente a 209 ms de mediana en la ejecución registrada), un 8 %. La cola también se alarga: p95 de 241 frente a 264 ms. Una ejecución anterior, interrumpida, dio la misma diferencia [5]. W = 2 confirma con la mayoría de las réplicas y tolera una réplica lenta o caída sin esperar; W = 3 solo añadiría que el bloque está en tres sitios al confirmar, algo que la re-replicación ya garantiza en segundos.

## 8.5 E5 · Tamaño de bloque

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 6 ]** · archivo: `docs/diagramas/fase-2/06-tamano-de-bloque.png` 🟥🟥

**Figura 6.** Tasa de transferencia con archivos de 1 GiB y latencia de una modificación parcial de 4 KiB, según el tamaño de bloque (E5).

Con bloques de 4 y 16 MiB la tasa es la misma; con 64 MiB baja un 12 % (Figura 6). La modificación parcial de 4 KiB sí cambia mucho: 204, 513 y 1 828 ms, porque la copia en escritura reescribe el bloque entero. Bloques de 4 MiB harían más baratas las modificaciones parciales, a cambio de cuatro veces más bloques en los metadatos, un coste que no se midió. Se mantienen los 16 MiB del diseño, pensados para archivos de 100 MiB a 1 GiB [2, §4.1].

## 8.6 E6 · Caída de un nodo de datos

Se tiró un nodo de datos mientras un cliente leía en bucle un archivo de 256 MiB. Hubo dos variantes, 5 repeticiones cada una:
- **parado** (`docker stop`): el nodo rechaza las conexiones;
- **congelado** (`docker pause`): el nodo acepta las conexiones y no responde, como una instancia colgada.

**Detección y re-replicación.** En las dos variantes, el líder declara caído el nodo a los 30,6 s de mediana (32,4 como máximo), con el umbral de 30 s. La re-replicación termina 12,1 s después, con un máximo de 15,1. Ninguna lectura falló.

**Nodo congelado.** Con la `v0.13.0`, la mediana de las lecturas era de 2,05 s, pero tres tardaron 120, 240 y 360 s: cada bloque leído del nodo congelado esperaba el plazo completo de 120 s, y un mismo `get` lo volvía a probar con otros bloques. La §11.4 de la fase I pide pasar a otra réplica cuando una no responde. Con el vigilante de inactividad de la `v0.13.1` (§5.2), la lectura más lenta bajó a 12,1 s: los 10 s del vigilante más la lectura desde otra réplica, una sola vez por `get` (Figura 7).

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 7 ]** · archivo: `docs/diagramas/fase-2/07-lecturas-con-nodo-congelado.png` 🟥🟥

**Figura 7.** Duración de cada lectura de 256 MiB con un nodo de datos congelado, antes y después del vigilante de inactividad (E6, 5 repeticiones de cada versión).

## 8.7 E7 · Caída del líder de metadatos

Una sonda en `client-1` hace un `mkdir` cada 0,1 s, con 1 s de plazo y sin reintentos, mientras cae el líder de metadatos junto con su miembro de etcd. También aquí hubo dos variantes, que resultaron ser escenarios muy distintos (Tabla 9):
- **congelado:** el líder deja de renovar su clave sin renunciar, como un fallo de verdad;
- **parado:** el líder recibe SIGTERM y renuncia antes de morir, que es un relevo ordenado.

**Tabla 9.** E7: tiempo sin escrituras de metadatos tras la caída del líder (medianas de 5 repeticiones).

| Variante | Sin servicio para el cliente | Elección | Modo seguro | `mkdir` fuera de la caída |
|---|---|---|---|---|
| Líder congelado (fallo) | 7,09 s (6,1–10,0) | 5,33 s | 1,58 s | 12,0 ms |
| Líder parado (relevo ordenado) | 0,81 s (0,5–1,8) | 0,13 s | 0,76 s | 12,1 ms |

Con un fallo de verdad, la elección dura unos 5 s, lo que tarda en caducar la clave del líder (TTL de 5 s), y el modo seguro añade 1–2 s. En dos repeticiones la elección tardó 7,7 y 8,5 s. La hipótesis, sin comprobar, es que el miembro de etcd congelado era también el líder de Raft de etcd, y hubo que elegir otro antes de que caducara la clave. Fuera de las caídas, un `mkdir`, que es una transacción de etcd con escritura en disco en los tres miembros, tarda unos 12 ms.

Bajar el TTL acortaría la interrupción, pero también acercaría al umbral de la renuncia anticipada cualquier pausa normal del proceso, y se cambiaría de líder sin motivo. No se probó con otros valores.

## 8.8 E8 · Coste de la seguridad

La seguridad no se puede desactivar en el código, así que E8 midió cada pieza por separado en `client-1` (ADR 0046). La Figura 8 las compara con el techo de un cliente.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 8 ]** · archivo: `docs/diagramas/fase-2/08-coste-de-la-seguridad.png` 🟥🟥

**Figura 8.** Tasa de cada pieza de la seguridad medida por separado, frente al techo de unos 130 MB/s de un cliente en E1 (E8).

- **Cifrado de sobre:** AES-256-GCM cifra y descifra a unos 1,5 GB/s, gracias a las instrucciones AES del procesador.
- **SHA-256:** a 397 MB/s, casi cuatro veces más lento que el cifrado, y se calcula al escribir y al leer.
- **TLS mutuo:** un canal gRPC con TLS mutuo pierde entre un 25 y un 32 % de su tasa: 460 frente a 618 MB/s al enviar, y 418 frente a 615 al recibir.

Ninguna pieza explica por sí sola el techo de unos 130 MB/s: todas son entre 3 y 12 veces más rápidas. Sumadas, el cifrado y el hash del cliente cuestan unos 3,3 ms de CPU por MiB, entre el 20 y el 40 % del tiempo de un `put` según cuánto se repartan entre los dos vCPU. Es una estimación a partir de las piezas, no una medición. El resto del tiempo se va en el código Python y gRPC del cliente, que no se perfiló.

## 8.9 E9 · Arranque en frío

Se pararon y arrancaron las nueve instancias cinco veces con la API de EC2, y además se observó un arranque al empezar una sesión nueva del laboratorio. El clúster volvió solo en todos los arranques:
- el líder elegido a los 28,5 s de mediana desde la orden de arranque, con un rango de 21–31 s;
- el modo seguro terminado 0,9 s después, siempre por la condición, nunca por el tope de 60 s.

El líder no ordenó ninguna re-replicación ni ningún borrado en los seis arranques, y los datos se leyeron con el mismo hash. Es lo que el modo seguro debía garantizar [2, §9.6].

La Figura 9 resume los tiempos de recuperación de E6, E7 y E9.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 9 ]** · archivo: `docs/diagramas/fase-2/09-tiempos-de-recuperacion.png` 🟥🟥

**Figura 9.** Tiempos de recuperación ante fallos: mediana de cada tramo en E9, E6 y E7.

## 8.10 Revisión de los parámetros de diseño

La fase I fijó unos valores iniciales y los experimentos que debían ajustarlos [2, §13.2]. La Tabla 10 recoge qué dijeron. Ningún valor por defecto cambia.

**Tabla 10.** Parámetros de diseño frente a lo medido.

| Parámetro | Valor | Experimento | Conclusión |
|---|---|---|---|
| Tamaño de bloque | 16 MiB | E5 | La misma tasa que 4 MiB y un 12 % más que 64 MiB. Se mantiene; 4 MiB es la alternativa si las modificaciones parciales pesan más |
| Quórum de escritura W | 2 | E3 | W = 3 añade un 8 % por bloque y alarga la cola. Se mantiene |
| Latido, sospechoso y caído | 3, 9 y 30 s | E6 | Detección a los 31 s y re-replicación en 12 s, como se diseñó. Se mantienen |
| Tope del modo seguro | 60 s | E7 y E9 | El modo seguro sale siempre por la condición en menos de 2,5 s. Se mantiene |
| Ritmo de la verificación periódica | 4 MB/s | E8 | SHA-256 va a 397 MB/s: 4 MB/s es en torno al 1 % de un núcleo. Se mantiene |
| Tamaño de mensaje | 1 MiB | E1 (no se varió) | Un canal gRPC con mensajes de 1 MiB va a 450–615 MB/s (E8), de 3,5 a 5 veces el techo del cliente: el mensaje no limita |
| TTL del arrendamiento | 30 s | E4 (no se varió) | En la prueba de concurrencia, un escritor que muere libera el rango en 27 s; los conflictos de E4 vienen del reintento inmediato del cliente, no del TTL |
| Inactividad de una transferencia (nuevo) | 10 s | E6 | Una lectura con un nodo congelado pasa de 360 a 12 s como máximo (ADR 0047) |
| Plazo de una orden de re-replicación (nuevo) | 15 s | Escenario 2 | Unas 8 veces la re-replicación más lenta medida (ADR 0048) |

El tamaño de mensaje y el TTL del arrendamiento no se variaron: E1 midió tamaños de archivo y E4 número de clientes. Los datos indirectos de la tabla muestran que no eran cuellos de botella, así que medirlos no habría cambiado la decisión.

# 9. Limitaciones

Las limitaciones declaradas en la fase I siguen vigentes [2, §1.4]:
- **No tolera** la caída de la zona de disponibilidad, ni la de dos servidores de metadatos a la vez.
- **La clave de envoltura** es un punto crítico.
- **Leer un byte** transfiere un bloque entero.

La Tabla 11 añade las que aparecieron al implementar y medir.

**Tabla 11.** Limitaciones descubiertas en la fase II.

| Limitación | Impacto | Origen |
|---|---|---|
| **La escalabilidad con varios clientes no está medida.** Un cliente llega a unos 130 MB/s con cualquier número de nodos, y varios clientes en la misma instancia comparten ese techo | No hay una medición que muestre que la tasa agregada crezca con más clientes en máquinas distintas (RNF1). Las nueve instancias del laboratorio están ocupadas por el clúster. Queda el argumento de diseño: el plano de control está separado del de datos, y los bloques se reparten entre todos los nodos | E2 y E4 |
| **El techo de un cliente no está explicado del todo.** Ninguna pieza de la seguridad lo explica sola, y el código Python del cliente no se perfiló | La tasa por cliente depende de la CPU de la máquina cliente | E8 |
| **Una caída del líder deja unos 7 s sin escrituras de metadatos** | Las lecturas de bloques siguen; las operaciones de metadatos esperan y el cliente las reintenta solo | E7 |
| **La copia de seguridad es manual** y depende de que la sesión del laboratorio termine en orden. Las copias solo sirven con la clave de envoltura con que se hicieron | El 2026-11-07, la sesión caducó sin aviso y unas horas de trabajo quedaron sin copia. Desde entonces se hace una copia tras cada cambio importante. Al recrear el clúster con secretos nuevos, las copias anteriores necesitan los secretos antiguos, que se guardan aparte | ADR 0035 |
| **El límite de intentos de contraseña vive en la memoria del líder** | Un cambio de líder reinicia el contador | ADR 0043 |
| **Un certificado por máquina cliente** | Todas las conexiones usan TLS mutuo, así que cada máquina cliente necesita un certificado de la CA interna | ADR 0043 |
| **Un modo de escritura por apertura**, y las escrituras deben caber en el rango arrendado | Mezclar un reemplazo con un anexado exige dos aperturas; `close()` tarda lo que tarda enviar todos los bloques cambiados | Etapa 8 |
| **La recolección de basura recorre todos los metadatos** en cada informe de bloques | Barato con pocos archivos; con muchos haría falta un índice de bloques vivos | Etapa 8 |
| **Los nodos excluidos y el vigilante dependen de la primaria.** Con dos fallos a la vez (una secundaria caída y la otra congelada), el cliente culpa a la primaria, que está sana | La escritura sigue, en otros nodos; solo se excluye un nodo sano para esa reserva | ADR 0047 |
| **Los 4,5 s de latido reciente suponen el intervalo de latido de 3 s** | Si cambia el intervalo, hay que cambiar también esta constante | ADR 0048 |
| **El cliente no reintenta tras `VERSION_CONFLICT`** | Con varios escritores sobre el mismo bloque, el que pierde tiene que volver a abrir y repetir su cambio; es la semántica declarada, pero no es transparente | Fase I, §7.4 |

# 10. Problemas encontrados

La Tabla 12 recoge los fallos que aparecieron al implementar, desplegar y medir, y que las pruebas automáticas no habían encontrado. Todos se corrigieron. Los del código llevan una prueba que los reproduce, y todos se volvieron a comprobar en AWS.

**Tabla 12.** Fallos encontrados durante la fase II y cómo se resolvieron.

| Fallo | Cómo se vio | Corrección |
|---|---|---|
| Un `get` con un nodo de datos caído agotaba la memoria del cliente | El kernel mató el `get` de 1 GiB por falta de memoria en la t3.micro, sin mensaje | La traza de la excepción de gRPC formaba un ciclo de referencias que retenía cada bloque leído después; ahora se borra al capturar el error (`v0.11.1`) |
| Al repetir un bloque, el líder devolvía el nodo recién caído | Escenario 3: la carga falló tras cuatro reservas con la misma primaria caída | Nodos excluidos en `AllocateBlocks` (ADR 0044) |
| El líder elegía nodos sin espacio y el nodo lleno respondía `UNKNOWN` | La primera ejecución de E2 llenó un volumen de 10 GiB | Ubicación solo en nodos con sitio y `RESOURCE_EXHAUSTED` en el nodo (`v0.12.1`) |
| El hilo de latidos del nodo de datos moría con un error del líder | Tras una restauración, ningún nodo de datos contaba como vivo para el nuevo líder | El bucle de latidos registra cualquier error y reintenta (`v0.9.1`) |
| Una confirmación parcial podía truncar lo anexado por otro escritor | Al diseñar la biblioteca, antes de que ningún cliente usara esos modos | La versión nueva toma el mayor de los dos tamaños |
| Un nodo congelado retenía cada lectura 120 s | E6, variante congelada | Vigilante de inactividad (ADR 0047, `v0.13.1`) |
| Una orden de re-replicación hacia un nodo recién caído tardaba 60 s en repetirse | Escenario 2 repetido con la `v0.13.1` | Nodos con latido reciente y plazo de 15 s (ADR 0048, `v0.13.2`) |
| Restaurar una copia de seguridad hacía retroceder la época del líder | Al diseñar la restauración | `--bump-revision` al restaurar |

Además, la memoria de los nodos de datos se midió desde la etapa 3, porque una t3.micro sin swap deja unos 440 MiB libres. Con 8 escrituras simultáneas, la primaria llegaba a 257 MiB por las arenas de memoria que glibc crea en cada hilo, y con `MALLOC_ARENA_MAX=2` bajó a 167 MiB sin perder tasa [29]. En AWS, durante una carga de 1 GiB, cada nodo de datos se queda entre 98 y 132 MiB.

# 11. Conclusiones

DFSha cumple en AWS lo que la fase I prometió:
- **RF1–RF3** con la semántica declarada: espacio de nombres por usuario, carga y recuperación, y `read()` y `write()` con los cuatro modos.
- **Consistencia** de apertura-cierre, con sus garantías comprobadas.
- **Concurrencia** coordinada por arrendamientos.
- **Tolerancia** a la caída de un nodo de datos y del líder de metadatos.
- **Seguridad** de extremo a extremo.

Las siete pruebas mínimas y los cuatro escenarios tienen su evidencia en el repositorio, y el clúster se levanta desde cero con una orden siguiendo el README.

Tres decisiones de la fase I demostraron su valor al implementarlas:
1. **Bloques inmutables con copia en escritura.** Ningún fallo encontrado dejó una réplica divergente ni una versión a medias.
2. **El modo seguro.** En los seis arranques en frío de E9, el líder nuevo no lanzó ninguna re-replicación ni ningún borrado, y salió del modo seguro por la condición en menos de 2,5 s.
3. **Separar el control de los datos.** El líder de metadatos nunca fue el cuello de botella: un `mkdir` tarda 12 ms, y la tasa la limita el cliente.

Lo que más aportó la fase II fue medir con fallos reales, no con los de las pruebas automáticas. Un nodo congelado, distinto de uno parado, y un nodo que cae justo después de su último latido destaparon cuatro fallos que el diseño y las pruebas no habían previsto: la memoria del cliente con un nodo caído, la ubicación al repetir un bloque, la espera ante un nodo que no responde y la re-replicación hacia un nodo recién caído. Cada uno tiene una prueba que lo reproduce y se volvió a medir en AWS, y los tres que cambiaban el diseño pasaron además por su registro de decisión (0044, 0047 y 0048). La limitación principal que queda, demostrar la escalabilidad con varias máquinas cliente, no se pudo medir con los recursos del laboratorio; el informe la deja declarada en lugar de suplirla con el argumento de diseño.

# Referencias

[1] Universidad Pontificia Bolivariana, «Proyecto 1 · DFSha: diseño e implementación de un sistema de archivos distribuido con alta disponibilidad, rendimiento y seguridad», enunciado del proyecto, Sistemas Distribuidos 2026-2, 2026.

[2] DFSha, «DFSha: sistema de archivos distribuido con alta disponibilidad. Documento de diseño · Fase I», repositorio del proyecto, docs/fase-1.md, 2026. [En línea]. Disponible en: https://github.com/pjg09/dfsha/blob/main/docs/fase-1.md

[3] A. Ospina Sanjuan, aclaraciones sobre el enunciado del Proyecto 1 (A1–A10), comunicación personal, oct.–nov. 2026.

[4] DFSha, «Registro de decisiones de arquitectura (ADR 0001–0048)», repositorio del proyecto, docs/decisiones, 2026. [En línea]. Disponible en: https://github.com/pjg09/dfsha/tree/main/docs/decisiones

[5] DFSha, «Evidencias de las pruebas y resultados de los experimentos», repositorio del proyecto, directorios evidencias y bench/resultados, nov. 2026. [En línea]. Disponible en: https://github.com/pjg09/dfsha/tree/main/evidencias

[6] S. Ghemawat, H. Gobioff y S.-T. Leung, «The Google file system», en *Proc. 19th ACM Symp. Operating Systems Principles (SOSP)*, Bolton Landing, NY, EE. UU., 2003, pp. 29–43. doi: 10.1145/945445.945450.

[7] D. Borthakur, «HDFS architecture guide», Apache Hadoop 1.2.1 Documentation, The Apache Software Foundation, 2013. [En línea]. Disponible en: https://hadoop.apache.org/docs/r1.2.1/hdfs_design.html (consultado: 23 oct. 2026).

[8] etcd Authors, «etcd v3.7.3», versión publicada en GitHub, 22 oct. 2026. [En línea]. Disponible en: https://github.com/etcd-io/etcd/releases/tag/v3.7.3 (consultado: 6 nov. 2026).

[9] D. Ongaro y J. Ousterhout, «In search of an understandable consensus algorithm», en *Proc. USENIX Annual Technical Conf. (ATC)*, Philadelphia, PA, EE. UU., 2014, pp. 305–319. Versión extendida disponible en: https://raft.github.io/raft.pdf (consultado: 23 oct. 2026).

[10] Astral, «uv: An extremely fast Python package and project manager», documentación. [En línea]. Disponible en: https://docs.astral.sh/uv/ (consultado: 6 nov. 2026).

[11] The gRPC Authors, «grpcio-status 1.85.1», Python Package Index. [En línea]. Disponible en: https://pypi.org/project/grpcio-status/ (consultado: 6 nov. 2026).

[12] The Python Cryptographic Authority, «cryptography 50.0.2 documentation: AEAD (AESGCM) y Scrypt». [En línea]. Disponible en: https://cryptography.io/en/latest/ (consultado: 7 nov. 2026).

[13] «etcd-sdk-python 0.0.7», Python Package Index, 4 ago. 2025. [En línea]. Disponible en: https://pypi.org/project/etcd-sdk-python/ (consultado: 6 nov. 2026).

[14] bakwc, «pysyncobj 0.3.17», Python Package Index, 30 ago. 2026. [En línea]. Disponible en: https://pypi.org/project/pysyncobj/0.3.17/ (consultado: 6 nov. 2026).

[15] K. Kingsbury, «Jepsen: etcd 3.4.3», Jepsen, 30 ene. 2020. [En línea]. Disponible en: https://jepsen.io/analyses/etcd-3.4.3 (consultado: 6 nov. 2026).

[16] The gRPC Authors, «grpc.ssl_server_credentials», gRPC Python API reference. [En línea]. Disponible en: https://grpc.github.io/grpc/python/grpc.html#grpc.ssl_server_credentials (consultado: 7 nov. 2026).

[17] gRPC Authors, «Keepalive User Guide for gRPC Core» y «Keepalive», gRPC. [En línea]. Disponible en: https://github.com/grpc/grpc/blob/master/doc/keepalive.md y https://grpc.io/docs/guides/keepalive/ (consultado: 8 nov. 2026).

[18] The Apache Software Foundation, «HDFS high availability using the Quorum Journal Manager», Apache Hadoop 3.3.5 Documentation, 2023. [En línea]. Disponible en: https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HDFSHighAvailabilityWithQJM.html (consultado: 6 nov. 2026).

[19] etcd Authors, «etcdutl snapshot restore», ayuda de la orden en etcd v3.7.3. [En línea]. Disponible en: https://etcd.io/docs/v3.6/op-guide/recovery/ (consultado: 7 nov. 2026).

[20] E. Rescorla, «The Transport Layer Security (TLS) protocol version 1.3», RFC 8446, IETF, ago. 2018. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc8446 (consultado: 23 oct. 2026).

[21] C. Percival y S. Josefsson, «The scrypt password-based key derivation function», RFC 7914, IETF, ago. 2016. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc7914 (consultado: 23 oct. 2026).

[22] H. Krawczyk, M. Bellare y R. Canetti, «HMAC: Keyed-hashing for message authentication», RFC 2104, IETF, feb. 1997. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc2104 (consultado: 23 oct. 2026).

[23] M. Dworkin, «Recommendation for block cipher modes of operation: Galois/Counter Mode (GCM) and GMAC», NIST, Gaithersburg, MD, EE. UU., SP 800-38D, nov. 2007. doi: 10.6028/NIST.SP.800-38D.

[24] Amazon Web Services, «Preventing image tags from being overwritten in Amazon ECR», Amazon ECR User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html (consultado: 6 nov. 2026).

[25] Canonical, «Find Ubuntu images on AWS», Ubuntu on public clouds. [En línea]. Disponible en: https://documentation.ubuntu.com/aws/aws-how-to/instances/find-ubuntu-images/ (consultado: 7 nov. 2026).

[26] Docker Inc., «Start containers automatically», Docker Docs. [En línea]. Disponible en: https://docs.docker.com/engine/containers/start-containers-automatically/ (consultado: 23 oct. 2026).

[27] «hatch-vcs 0.5.0», Python Package Index. [En línea]. Disponible en: https://pypi.org/project/hatch-vcs/ (consultado: 6 nov. 2026).

[28] Amazon Web Services, «Burstable performance instances», Amazon EC2 User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances.html (consultado: 23 oct. 2026).

[29] Free Software Foundation, «Memory allocation tunables», en *The GNU C Library Reference Manual*. [En línea]. Disponible en: https://www.gnu.org/software/libc/manual/html_node/Memory-Allocation-Tunables.html (consultado: 6 nov. 2026).

# Anexo A. Registro de decisiones de la fase II

Los registros de la fase I (0001–0035) están en el Anexo B del documento de la fase I [2]. La Tabla 13 lista los de la fase II, que están completos en `docs/decisiones/` [4].

**Tabla 13.** Registros de decisión de la fase II.

| N.º | Decisión | Estado |
|---|---|---|
| 0036 | Evidencias y material del informe durante la fase II | Aceptada |
| 0037 | Imágenes Docker en ECR, construidas una vez por versión | Aceptada |
| 0038 | Entorno de Python con uv, código generado versionado y versión desde Git | Aceptada |
| 0039 | Raft con etcd en los servidores de metadatos | Aceptada |
| 0040 | Despliegue en AWS: una imagen por rol, con etcd junto a cada servidor de metadatos | Aceptada; sustituye a 0027 |
| 0041 | Modelo de metadatos en etcd y cliente de etcd | Aceptada |
| 0042 | El nodo de datos envía su dirección al darse de alta | Aceptada |
| 0043 | Implementación de la seguridad: TLS mutuo en todas las conexiones, formatos y secretos | Aceptada |
| 0044 | Nodos excluidos al repetir un bloque | Aceptada |
| 0045 | El cliente pasa a una t3.small para los experimentos | Aceptada |
| 0046 | Métricas y experimentos, con E8 medido por componentes | Aceptada; sustituye a 0028 |
| 0047 | Vigilante de inactividad en las transferencias del cliente | Aceptada |
| 0048 | Nodos con latido reciente en la re-replicación y plazo de 15 s por copia | Aceptada |

# Anexo B. Índice de evidencias

Cada evidencia es un directorio de `evidencias/` con un `README.md` (fecha, versión, comandos, resultado esperado y obtenido) y la salida completa de cada orden [5]. Las mediciones están en `bench/resultados/`, con un CSV, un registro y un resumen por experimento. La Tabla 14 las lista.

**Tabla 14.** Evidencias registradas en AWS.

| Evidencia | Directorio |
|---|---|
| Carga y recuperación | `2026-11-07-carga-y-recuperacion` y, con la versión final, `2026-11-08-carga-y-recuperacion` |
| Acceso RF3 | `2026-11-07-acceso-rf3` y `2026-11-08-acceso-rf3` |
| Concurrencia (escenario 1) | `2026-11-07-concurrencia` y `2026-11-08-concurrencia` |
| Replicación y fallos | `2026-11-07-replicacion-y-fallos` y `2026-11-08-replicacion-y-fallos` |
| Consistencia (escenario 2) | `2026-11-07-escenario-2` y `2026-11-08-escenario-2` |
| Escenario 3: un nodo falla a mitad de un bloque | `2026-11-07-escenario-3` |
| Escenario 4: ubicación desconocida para el cliente | `2026-11-07-escenario-4` |
| Seguridad | `2026-11-07-seguridad` y `2026-11-08-seguridad` |
| Recolección de basura | `2026-11-07-recoleccion-de-basura` |
| Restauración de metadatos | `2026-11-07-restauracion-de-metadatos` |
| Arranque en frío real | `2026-11-07-arranque-en-frio` |
| Despliegue desde cero | `2026-11-07-despliegue-desde-cero` |
| README desde cero | `2026-11-08-readme-desde-cero` |
| Experimentos E1–E9 | `bench/resultados/2026-11-07-e1.md` a `2026-11-07-e9.md`, y E1 repetido con la `v0.13.1` en `2026-11-08-e1.md` |
