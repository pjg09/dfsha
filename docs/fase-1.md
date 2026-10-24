# DFSha: sistema de archivos distribuido con alta disponibilidad

## Documento de diseño · Fase I

**Proyecto 1 · Arquitectura de Nube y Sistemas Distribuidos · Universidad Pontificia Bolivariana · 2026-2**

**Arquitectura asignada:** opción 1, cliente/servidor con servicio distribuido entre servidores (S2S), operado dentro de una red privada virtual.

| Campo | Valor |
|---|---|
| Autor | **[[COMPLETAR: nombre completo]]** |
| Código | **[[COMPLETAR: código de estudiante]]** |
| Profesor | **[[COMPLETAR: nombre del profesor]]** |
| Grupo | **[[COMPLETAR: grupo]]** |
| Fecha | **[[COMPLETAR: fecha de entrega]]** |
| Versión del documento | 1.0, diseño individual (fase I) |

> 🟨🟨 **[ INSERTAR AQUÍ LA TABLA DE CONTENIDO, LA LISTA DE FIGURAS Y LA LISTA DE TABLAS QUE GENERA WORD ]** 🟨🟨

## Resumen

DFSha es un sistema de archivos distribuido que reparte cada archivo en bloques de 16 MiB, guarda tres réplicas de cada bloque en nodos de datos distintos y mantiene los metadatos en tres servidores replicados con Raft, de modo que ningún componente es un punto único de fallo. El cliente solo conoce los nombres de los servidores de metadatos: les pide dónde están los bloques y después los transfiere directamente con los nodos de datos, con lo que el plano de control y el plano de datos quedan separados.

El diseño no simplifica ningún requisito. `write()` admite creación, reemplazo, anexado y modificación parcial sobre bloques inmutables con copia en escritura. Cada escritura confirmada produce una versión de archivo nueva de forma atómica, y la consistencia es de apertura-cierre, con cuatro garantías comprobables. La exclusión mutua usa arrendamientos por rango de bloques, que permiten escribir a la vez en zonas distintas de un mismo archivo. Un bloque se confirma cuando lo tienen dos de sus tres réplicas.

Los fallos se detectan en 30 s, la re-replicación es automática y un modo seguro evita falsos positivos tras cada elección de líder. Toda comunicación va por gRPC con TLS, y entre nodos con TLS mutuo. Los bloques se cifran en el cliente con AES-256-GCM mediante cifrado de sobre. El sistema se despliega en nueve instancias EC2 del AWS Academy Learner Lab. El documento especifica las APIs completas, analiza los cuatro escenarios obligatorios y define nueve experimentos para validar en la fase II los parámetros que aquí se eligen.

**Palabras clave:** sistema de archivos distribuido, replicación, Raft, consistencia de apertura-cierre, arrendamientos, gRPC, cifrado de sobre, AWS.

# 1. Introducción

## 1.1 Objetivo y alcance

Este documento es la propuesta técnica individual de la fase I del Proyecto 1 [1]. Describe un sistema de archivos distribuido (DFS) llamado DFSha, que cumple los requisitos funcionales RF1–RF3 y los no funcionales RNF1–RNF7 con la arquitectura asignada: cliente/servidor con servicio distribuido entre servidores (S2S). Para cada decisión, el documento sigue el mismo esquema: qué se exige o se observa, qué concepto lo explica, qué se gana y qué queda sin cubrir. Una decisión cuyo límite no se declara no se ha entendido del todo.

El alcance cubre los nueve puntos de §4.1 del enunciado y los cuatro escenarios de su §4.2:
- definición del servicio, casos de uso y operaciones;
- arquitectura, despliegue y distribución de los datos;
- protocolos y APIs, con mensajes de ejemplo y errores;
- semántica de `read()` y `write()`, consistencia, concurrencia y recuperación de escrituras interrumpidas;
- tolerancia a fallos y seguridad;
- métricas y experimentos para validar el diseño en la fase II.

No hay implementación en esta fase. Los parámetros numéricos (tamaño de bloque, umbrales de detección, plazos) son valores iniciales justificados que la fase II mide y ajusta.

## 1.2 Enfoque de la arquitectura asignada

En la opción 1, los clientes no cooperan entre sí: hablan con un servicio que forman varios servidores. En DFSha ese servicio tiene dos clases de servidores, que también cooperan entre ellos:
- **Servidores de metadatos.** Tres servidores que mantienen el espacio de nombres y las ubicaciones de los bloques. Se replican con el algoritmo de consenso Raft [2].
- **Nodos de datos.** Cinco nodos que guardan los bloques. Se reenvían los bloques al escribir y se re-replican entre ellos cuando cae uno.

Es el patrón de GFS y HDFS [3], [4]: un plano de control que sabe *dónde* están los datos y un plano de datos por el que circulan. La diferencia es que en DFSha el plano de control también está replicado.

## 1.3 Supuestos

Los supuestos de la Tabla 1 delimitan el entorno para el que vale el diseño. Si alguno deja de cumplirse, la sección indicada dice qué garantía se ve afectada.

**Tabla 1.** Supuestos del diseño.

| Id. | Supuesto | Justificación | Si no se cumple |
|---|---|---|---|
| S1 | Los nodos fallan por parada (*fail-stop*): dejan de responder, pero no envían mensajes falsos | El enunciado no exige tolerar nodos maliciosos dentro del clúster | Un nodo malicioso podría anunciar bloques que no tiene; lo limitan los hashes y el TLS mutuo (§10) |
| S2 | Un disco puede corromper datos sin avisar | Discos y memorias pueden alterar bits sin aviso; HDFS verifica sumas de comprobación por lo mismo [4] | Cubierto: verificación por hash al leer y verificación periódica (§8.5) |
| S3 | La red es privada (una VPC de AWS), pero puede perder, retrasar o duplicar mensajes | Falacias de la computación distribuida [5], [6, cap. 1] | Cubierto: plazos, reintentos idempotentes y TLS (§5, §8.6) |
| S4 | Los relojes están sincronizados con un desfase acotado | chrony con el servicio de hora de Amazon [7] | Con margen de 30 s; más allá, tokens rechazados o aceptados fuera de plazo (§10.6) |
| S5 | Los clientes están autenticados, pero no son de confianza: pueden mentir sobre lo que han hecho | Un cliente es código del usuario | El servidor de metadatos no se fía del cliente para contar réplicas ni para marcar réplicas corruptas (§4.4, §8.5) |
| S6 | Los usuarios los da de alta un administrador | RF1 no pide autorregistro | — |
| S7 | Archivos de prueba de 100 MiB a 1 GiB; volúmenes de 10 GiB por nodo de datos | Instancias pequeñas del Learner Lab | Con archivos mucho mayores conviene un bloque mayor (§4.1) |
| S8 | Como máximo 9 instancias en marcha a la vez | Límite del Learner Lab [8] | Determina la topología (§3.6) |

## 1.4 Limitaciones declaradas

Ninguna de estas limitaciones es una simplificación de RF3 ni de las garantías no funcionales, que se mantienen todas [9]. Son los límites del diseño y se declaran para que se puedan evaluar (Tabla 2).

**Tabla 2.** Limitaciones declaradas del diseño.

| Id. | Limitación | Motivo | Sección |
|---|---|---|---|
| L1 | No se tolera la caída de la zona de disponibilidad completa | Una sola zona en el Learner Lab; el presupuesto no cubre otra | §3.6 |
| L2 | No hay tolerancia a fallos bizantinos | Supuesto S1 | §9.1 |
| L3 | Con dos de los tres servidores de metadatos caídos no hay operaciones de metadatos | Raft necesita mayoría | §9.4 |
| L4 | Lo ya escrito no se rebalancea al añadir nodos de datos | Igual que HDFS 1.2.1 [4] | §4.3 |
| L5 | Leer un byte de un bloque transfiere el bloque entero | El cifrado autenticado verifica el bloque completo | §7.1 |
| L6 | Un lector que mantiene una versión abierta más de 10 min puede fallar | Periodo de gracia de las versiones sustituidas | §7.3 |
| L7 | Quien comprometa un servidor de metadatos puede descifrar todos los archivos | Allí está la clave de envoltura | §10.5 |
| L8 | Los metadatos (nombres y tamaños) van en claro | Lo permite el profesor [9] | §10.5 |
| L9 | No se comparten archivos entre usuarios, ni hay cuotas ni papelera | RF1 no lo exige | §2.3 |
| L10 | La implementación concreta de Raft (etcd o PySyncObj) se elige en la fase II | Hay que probarlas antes | §3.3 |
| L11 | Los metadatos no se pueden recuperar a un momento anterior a la última copia de seguridad, y un borrado por error se replica a los tres servidores | Raft replica también los errores | §4.2 |

## 1.5 Convenciones del documento

- **Términos.** El documento usa un glosario fijo: *bloque* (no *chunk*), *cerrojo* (no *bloqueo*, para no confundirlo con *bloque*), *réplica primaria* (no *maestro*), *carga* y *recuperación* para `put` y `get`.
- **Código.** Los identificadores del código, los RPC y los códigos de error van en inglés (`CommitFile`, `LOCK_CONFLICT`). La documentación y los mensajes al usuario, en español.
- **Unidades.** MiB y GiB son potencias de 2 (1 MiB = 1 048 576 bytes). Las tasas de transferencia se dan en MB/s, megabytes por segundo, para no confundir bytes con bits.
- **Nombres de host.** Siguen el patrón `<rol>-<n>`: `metadata-1`, `datanode-3`, `client-1`. Ningún documento ni configuración usa direcciones IP de nodos (RNF7).
- **Decisiones.** Cada decisión tiene un registro (ADR) en el repositorio del proyecto [10]. El Anexo B relaciona cada ADR con su sección; la tabla de cambios de la fase II partirá de ellos.

# 2. Definición del servicio y casos de uso

## 2.1 El servicio

DFSha ofrece a cada usuario autenticado un **espacio de nombres** propio: un árbol de directorios y archivos con raíz `/` que nadie más puede ver ni modificar (RF1). Sobre ese árbol, el usuario puede:
- **gestionar el espacio de nombres:** listar, cambiar de directorio, crear y borrar directorios, borrar y mover archivos (RF1);
- **transferir archivos completos:** carga (`put`) y recuperación (`get`) (RF2);
- **acceder a un archivo por partes:** `open()`, `read()`, `write()`, `lock()`, `unlock()` y `close()` (RF3).

El servicio se usa desde una **biblioteca de cliente** en Python, que implementa las primitivas de RF3, y desde un **CLI** construido sobre ella, que ofrece los comandos de RF1 y RF2. La biblioteca oculta la distribución: el usuario trabaja con rutas lógicas (`/informes/2026.pdf`) y nunca ve bloques, réplicas ni nombres de nodos (RNF7).

## 2.2 Actores

**Tabla 3.** Actores del sistema.

| Actor | Tipo | Qué hace | Cómo se autentica |
|---|---|---|---|
| Usuario | Humano | Usa el CLI para gestionar y transferir sus archivos | Usuario y contraseña, que se cambian por un token de acceso |
| Aplicación cliente | Programa | Usa la biblioteca para leer y escribir partes de un archivo | Token de acceso del usuario por el que actúa |
| Administrador | Humano | Da de alta usuarios, despliega el clúster y guarda las copias de seguridad de los metadatos | Token de acceso de un usuario administrador; credenciales del Learner Lab para desplegar |
| Servidor de metadatos | Sistema | Mantiene el espacio de nombres, las versiones, las ubicaciones y los arrendamientos; dirige la re-replicación | Certificado de su rol (TLS mutuo) |
| Nodo de datos | Sistema | Guarda, sirve, reenvía y verifica bloques | Certificado de su rol (TLS mutuo) |

## 2.3 Operaciones

La Tabla 4 resume las operaciones que ofrece el servicio, con la semántica que el documento desarrolla en las secciones 6 a 8. Los errores completos están en la §5.4.

**Tabla 4.** Operaciones de RF1, RF2 y RF3.

| Operación | RF | Qué hace | Semántica principal | Errores típicos |
|---|---|---|---|---|
| `ls [ruta]` | RF1 | Lista un directorio | Ve la última versión confirmada de cada entrada | `NOT_FOUND` |
| `cd ruta` | RF1 | Cambia el directorio actual | Lo guarda el cliente; al servidor solo llegan rutas absolutas | `NOT_FOUND` |
| `mkdir ruta` | RF1 | Crea un directorio | Un solo nivel; el padre debe existir | `NOT_FOUND`, `ALREADY_EXISTS` |
| `rmdir ruta` | RF1 | Borra un directorio | Solo si está vacío | `FAILED_PRECONDITION` + `DIRECTORY_NOT_EMPTY` |
| `rm ruta` | RF1 | Borra un archivo | Deja de ser visible al confirmarse; sus bloques se borran tras 10 min | `ABORTED` + `LOCK_CONFLICT` si alguien escribe |
| `mv origen destino` | RF1 | Mueve o renombra un archivo o directorio | Atómico, dentro del espacio del usuario | `NOT_FOUND`, `ALREADY_EXISTS` |
| `put local remoto` | RF2 | Carga un archivo completo | Creación o reemplazo; visible entero o nada | `ABORTED` + `LOCK_CONFLICT` |
| `get remoto local` | RF2 | Recupera un archivo completo | Lee una versión confirmada completa; verifica el hash | `DATA_LOSS` si se perdieron todas las réplicas de un bloque |
| `open(ruta, modo)` | RF3 | Abre para leer o escribir | Fija la versión que se va a leer | `NOT_FOUND` |
| `read(h, offset, n)` | RF3 | Lee `n` bytes desde `offset` | Siempre de la versión abierta; no toma cerrojo | `FAILED_PRECONDITION` + `FILE_VERSION_EXPIRED` |
| `write(h, offset, datos, modo)` | RF3 | Escribe | Creación, reemplazo, anexado o modificación parcial; visible al confirmar en `close()` | `ABORTED` + `LOCK_CONFLICT` |
| `lock(h, rango)` | RF3 | Pide un arrendamiento exclusivo de escritura | Sobre un rango de bloques, con TTL de 30 s renovable | `ABORTED` + `LOCK_CONFLICT` |
| `unlock(h)` | RF3 | Libera el arrendamiento | — | — |
| `close(h)` | RF3 | Cierra y confirma lo escrito | La escritura está confirmada cuando `close()` devuelve OK | `ABORTED` + `LEASE_EXPIRED` o `VERSION_CONFLICT` |

**Fuera de alcance**, porque RF1 no lo pide: compartir archivos entre usuarios, enlaces, cuotas de espacio y papelera.

## 2.4 Casos de uso

La Figura 1 muestra los casos de uso y la Tabla 5 los detalla. Las secuencias de carga, lectura, escritura y borrado que pide §4.1 del enunciado están en la sección 6, porque usan los RPC que define la sección 5.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 1 ]** · archivo: `docs/diagramas/01-casos-de-uso.png` 🟥🟥

**Figura 1.** Diagrama de casos de uso de DFSha.

**Tabla 5.** Casos de uso.

| Id. | Caso de uso | Actor | Precondición | Flujo principal | Resultado | Sección |
|---|---|---|---|---|---|---|
| CU1 | Autenticarse | Usuario, aplicación | El usuario existe | Envía usuario y contraseña; recibe un token de acceso de 1 h | Token válido | §10.2 |
| CU2 | Gestionar el espacio de nombres | Usuario | Autenticado | `ls`, `cd`, `mkdir`, `rmdir`, `rm`, `mv` | Árbol modificado de forma atómica | §6.5 |
| CU3 | Cargar un archivo | Usuario | Autenticado | `put`: abrir, reservar bloques, enviarlos a los nodos de datos y confirmar | Versión nueva, completa y visible | §6.1 |
| CU4 | Recuperar un archivo | Usuario | El archivo existe | `get`: abrir, pedir ubicaciones, leer los bloques en paralelo y verificar | Archivo idéntico al cargado (mismo hash) | §6.2 |
| CU5 | Leer parte de un archivo | Aplicación | El archivo existe | `open`, `read` en cualquier `offset`, `close` | Bytes de la versión abierta | §6.2, §7 |
| CU6 | Escribir parte de un archivo | Aplicación | Autenticado | `open`, `lock`, `write` (cualquiera de los cuatro modos), `close` | Versión nueva o error de conflicto | §6.3, §7 |
| CU7 | Borrar un archivo | Usuario | Sin escritor activo | `rm` | Archivo invisible; espacio liberado tras 10 min | §6.4 |
| CU8 | Dar de alta un usuario | Administrador | Token de administrador | `CreateUser` | Usuario con espacio vacío | §10.2 |
| CU9 | Desplegar el clúster y guardar las copias de seguridad | Administrador | Sesión del Learner Lab activa | Script de despliegue repetible; al final de cada sesión, copia la última instantánea de los metadatos a S3 | 9 instancias con sus contenedores; copia de los metadatos en S3 | §3.6, §4.2 |
| CU10 | Mantener las réplicas | Servidor de metadatos, nodos de datos | Clúster en marcha | Latidos, informes de bloques, re-replicación, verificación periódica | R réplicas sanas por bloque | §9 |

## 2.5 Trazabilidad de los requisitos

La Tabla 6 indica qué mecanismo cubre cada requisito y dónde se explica. Sirve como índice para la evaluación.

**Tabla 6.** Requisitos y mecanismos que los cubren.

| Requisito | Mecanismo de DFSha | Sección |
|---|---|---|
| RF1 · Sistema de archivos jerárquico por usuario | Espacio de nombres por usuario en el servidor de metadatos; `cd` en el cliente; `mv` atómico | §2.3, §6.5 |
| RF2 · Archivos completos | `put` y `get` sobre las primitivas de RF3, con transferencia paralela de bloques | §6.1, §6.2 |
| RF3 · `open`, `read`, `write`, `lock`… | Cuatro modos de escritura sobre bloques inmutables; arrendamientos por rango de bloques | §7, §8.1 |
| RNF1 · Escalabilidad | Plano de datos directo entre cliente y nodos de datos; ubicaciones de todos los bloques en una sola llamada; nodos de datos añadibles | §3.1, §4.3 |
| RNF2 · Alta disponibilidad | R = 3 réplicas por bloque; tres servidores de metadatos con Raft; detección en 30 s y re-replicación | §4.4, §9 |
| RNF3 · Consistencia y réplicas | Apertura-cierre (G1–G4); confirmación atómica; réplicas idénticas o inexistentes | §7.3, §8.4 |
| RNF4 · Particionamiento | Bloques de 16 MiB repartidos por espacio libre entre nodos de datos distintos | §4.1, §4.3 |
| RNF5 · Rendimiento y concurrencia | Lecturas sin cerrojo; escrituras concurrentes en rangos distintos; confirmación con W = 2 | §7.4, §4.4 |
| RNF6 · Seguridad | TLS y TLS mutuo; tokens de acceso y de bloque; cifrado de sobre con AES-256-GCM | §10 |
| RNF7 · Transparencia | El cliente solo conoce los nombres de los servidores de metadatos; descubre los bloques en tiempo de ejecución | §11.4 |

# 3. Arquitectura

## 3.1 Visión general: plano de control y plano de datos

La decisión central de la arquitectura es **separar el control de los datos**. El profesor lo explicó con el sobre y el contenido de una carta, y con el directorio telefónico y los negocios: primero se pregunta *dónde* y después se va directamente *allí* [11], [12]. En DFSha:
- **El plano de control** son los servidores de metadatos. Responden dónde está cada bloque, deciden quién puede escribir y cuándo una escritura es visible, y dirigen la re-replicación. Por ellos no pasa ni un byte del contenido de los archivos.
- **El plano de datos** son los nodos de datos. El cliente les envía y les pide los bloques directamente, y ellos se reenvían los bloques entre sí.

Si los bloques pasaran por el servidor de metadatos, ese servidor sería a la vez el punto único de fallo y el cuello de botella de ancho de banda: añadir nodos de datos no aumentaría la tasa de transferencia (RNF1, RNF5). Aun así, el servidor de metadatos sigue siendo la parte secuencial del sistema, y la ley de Amdahl dice que esa parte limita la mejora al escalar [13]. Por eso el diseño reduce las consultas al plano de control: el cliente pide las ubicaciones de todos los bloques en una sola llamada al abrir el archivo.

La Figura 2 muestra los componentes y sus interfaces.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 2 ]** · archivo: `docs/diagramas/02-componentes.png` 🟥🟥

**Figura 2.** Diagrama de componentes. Las flechas continuas son el plano de datos y las discontinuas el plano de control.

## 3.2 Roles y responsabilidades

**Tabla 7.** Roles, responsabilidades y estado que guarda cada uno.

| Rol | Hosts | Responsabilidades | Estado que guarda | Cómo se replica |
|---|---|---|---|---|
| Servidor de metadatos | `metadata-1` a `metadata-3` | Autenticación; espacio de nombres; versiones de archivo; ubicaciones de bloques; arrendamientos; registro de `request_id`; estado de los nodos; ubicación de réplicas nuevas; re-replicación y recolección de basura; modo seguro | Máquina de estados replicada con Raft; el log y las instantáneas, en su volumen EBS (§4.2) | Log replicado en los tres servidores; se confirma con 2 de 3 |
| Nodo de datos | `datanode-1` a `datanode-5` | Guardar y servir bloques; verificar su hash; reenviarlos a las réplicas secundarias; re-replicarlos cuando se le ordena; enviar latidos, avisos e informes de bloques; verificación periódica | Bloques cifrados en su volumen EBS, uno por archivo local; área temporal | Cada bloque tiene R = 3 réplicas en nodos distintos |
| Cliente | `client-1` | CLI y biblioteca; directorio actual; cifrado y descifrado de los bloques; transferencia en paralelo; reintentos | Nada persistente; caché de ubicaciones y de la clave de datos mientras el archivo está abierto | No aplica |

## 3.3 Servidor de metadatos replicado

Los metadatos son lo más delicado del sistema. Si el servidor de metadatos cae, los bloques siguen existiendo, pero nadie sabe dónde están: es la diferencia entre la disponibilidad de los datos y la de su localización [12]. Un DFS con un solo servidor de metadatos tiene un punto único de fallo, y optimizar código no lo arregla: lo fija la arquitectura [14]. La propia guía de HDFS 1.2.1 reconoce que su NameNode lo es y que reiniciarlo exige intervención manual [4]. La Tabla 8 compara las alternativas.

**Tabla 8.** Alternativas para el servidor de metadatos.

| Alternativa | Ventaja | Inconveniente |
|---|---|---|
| Un solo servidor con log persistente y reinicio | Simple y barato | Es un punto único de fallo; mientras se reinicia no hay servicio. Equivale a simplificar RNF2 |
| Primario y respaldo con copia del log, sin consenso | Conmutación rápida | Una partición de red puede dejar dos primarios aceptando escrituras a la vez (cerebro dividido) |
| **Tres servidores con Raft** (elegida) | Tolera la caída de uno sin perder escrituras confirmadas y sin cerebro dividido | Cada cambio necesita un viaje de ida y vuelta hasta la mayoría; hacen falta tres instancias |

**Decisión.** Tres servidores de metadatos con Raft [2]:
- Cada cambio de metadatos es una entrada del log replicado y se aplica cuando la confirma la mayoría (2 de 3). Con N = 3, el quórum de mayoría es ⌊3/2⌋ + 1 = 2 y tolera un fallo [15], [6, cap. 8].
- El líder atiende las escrituras y también las lecturas, que así son linealizables [2]. La garantía G2 de la §7.3 lo necesita.
- Un seguidor que recibe una petición responde con el nombre del líder, y el cliente repite la petición allí.
- Se toman instantáneas periódicas para acotar el tamaño del log.
- El log y las instantáneas se guardan en un volumen EBS propio de cada servidor, y cada entrada se escribe en disco antes de contar para la mayoría (§4.2).

**Raft no se implementa a mano.** En la fase II se elegirá entre etcd [16], como almacén externo replicado en los mismos tres hosts, y PySyncObj [17], como biblioteca dentro del proceso del servidor. El diseño solo supone una máquina de estados replicada con lecturas linealizables, que ofrecen las dos.

**Límite.** Con dos servidores de metadatos caídos no hay líder, y por tanto no hay operaciones de metadatos, ni siquiera `open()`. Las lecturas ya abiertas siguen mientras no caduquen sus tokens de bloque (10 min), porque tienen las ubicaciones en caché (§9.4).

## 3.4 Nodo de datos

Cada nodo de datos tiene cuatro componentes:
- **Servicio `DataNodeService`.** Recibe bloques en flujo (`WriteBlock`) y los sirve (`ReadBlock`).
- **Almacén de bloques.** Un archivo local por bloque, con el `block_id` como nombre, en un volumen EBS propio. Al lado está el **área temporal**, en el mismo sistema de archivos, para que el renombrado al almacén sea atómico (§8.4).
- **Agente de latidos.** Envía un latido cada 3 s con su espacio libre, recibe las órdenes en la respuesta y envía un informe de bloques al darse de alta y cada 5 min.
- **Verificador de bloques.** Recalcula el hash de todos sus bloques una vez al día, con un ritmo de lectura limitado (§8.5).

El nodo de datos **nunca ve el contenido en claro**: los bloques llegan cifrados desde el cliente (§10.5). Al arrancar, comprueba que su directorio de datos es un punto de montaje y que contiene una marca con su `node_id`. Si no, no arranca, para no escribir en el disco raíz sin avisar.

## 3.5 Cliente

La biblioteca de cliente concentra la lógica que no debe estar en el servidor:
- **Directorio actual.** `cd` cambia una variable del cliente, que envía siempre rutas absolutas. Así el servidor no guarda estado de sesión.
- **Cifrado.** Cifra y descifra cada bloque con la clave de datos del archivo (§10.5).
- **Transferencia en paralelo.** Lee y escribe varios bloques a la vez, cada uno con un nodo de datos distinto. El grado de paralelismo es configurable y se ajusta con los experimentos (§12).
- **Reintentos.** Reintenta con espera exponencial y con un `request_id` estable las operaciones que lo permiten (§8.6).
- **Descubrimiento.** Solo se configura con `DFSHA_METADATA_ADDRS`, la lista de nombres de los servidores de metadatos (§11.4).

## 3.6 Despliegue en AWS

El producto se despliega en el AWS Academy Learner Lab, en `us-east-1`, dentro de una VPC y en una sola zona de disponibilidad. La Tabla 9 muestra la topología y la Figura 3 el despliegue.

**Tabla 9.** Topología del clúster.

| Rol | Hosts | Instancia | Almacenamiento | Contenedor |
|---|---|---|---|---|
| Servidor de metadatos | `metadata-1`, `metadata-2`, `metadata-3` | t3.small (2 vCPU, 2 GiB) | Disco raíz de 8 GiB + volumen EBS gp3 de 4 GiB, cifrado | `dfsha-metadata` |
| Nodo de datos | `datanode-1` a `datanode-5` | t3.micro (2 vCPU, 1 GiB) | Disco raíz de 8 GiB + volumen EBS gp3 de 10 GiB, cifrado | `dfsha-datanode` |
| Cliente | `client-1` | t3.micro | Disco raíz de 8 GiB | `dfsha-client` |

**Por qué 3 + 5 + 1.**
- **Tres servidores de metadatos:** es el mínimo para que Raft tolere un fallo.
- **Cinco nodos de datos:** con R = 3, hacen falta más nodos de datos que réplicas para demostrar la re-replicación. Con tantos nodos como réplicas, al caer uno no hay dónde crear la réplica que falta [18]. Cinco nodos permiten re-replicar tras dos caídas seguidas y medir la escalabilidad con 3, 4 y 5 nodos.
- **Cada rol en su instancia:** juntar servidor de metadatos y nodo de datos ahorraría instancias, pero una caída tumbaría dos roles a la vez (fallos correlacionados).
- **El total es exactamente el tope del Learner Lab: 9 instancias en marcha a la vez** [8]. Las que pasan de 9 se terminan, así que el script de despliegue cuenta las instancias en marcha antes de lanzar ninguna. Las pruebas de concurrencia lanzan varios procesos cliente desde `client-1`.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 3 ]** · archivo: `docs/diagramas/03-despliegue.png` 🟥🟥

**Figura 3.** Diagrama de despliegue en AWS: instancias, contenedores, volúmenes, grupos de seguridad y bucket de copias de seguridad.

**Red.** Cada rol tiene su grupo de seguridad, y los puertos del clúster solo se abren entre los grupos del proyecto (Tabla 10). Ningún puerto del clúster queda abierto a Internet.

**Tabla 10.** Puertos y grupos de seguridad.

| Grupo de seguridad | Puerto | Origen permitido | Uso |
|---|---|---|---|
| `dfsha-sg-metadata` | 50051/tcp | `dfsha-sg-client`, `dfsha-sg-datanode` | `MetadataService` |
| `dfsha-sg-metadata` | Puerto de Raft (lo fija la implementación) | `dfsha-sg-metadata` | Consenso entre servidores de metadatos |
| `dfsha-sg-datanode` | 50052/tcp | `dfsha-sg-client`, `dfsha-sg-datanode` | `DataNodeService` |
| Los tres | 22/tcp | Solo la IP de quien administra | SSH para administrar |

**Fuera del clúster: S3.** El único recurso de AWS que no es una instancia ni un volumen es un bucket privado y cifrado de S3, `dfsha-copias-<sufijo>`, que guarda las copias de seguridad de los metadatos (§4.2). Solo lo usa el script de despliegue, con las credenciales de la sesión del lab. Ninguna instancia accede a él, así que no hace falta abrir ningún puerto ni dar permisos a `LabInstanceProfile`, y ningún componente usa credenciales de AWS mientras funciona. El Readme del Learner Lab incluye S3 entre los servicios disponibles [8]; crear el bucket no se ha probado todavía.

**Contenedores.** Hay una imagen Docker por rol, con la versión como etiqueta, y un solo contenedor por instancia, lanzado con Docker Compose. Usa la red del host, monta los certificados y los secretos desde fuera del repositorio (y su volumen EBS, en los servidores de metadatos y en los nodos de datos), y tiene la política de reinicio `always` [19].

**Script de despliegue.** Es repetible, porque las credenciales del lab caducan con cada sesión:
1. crea o arranca las instancias, con sus etiquetas, grupos de seguridad y volúmenes EBS;
2. instala Docker y lo deja activado al arrancar el sistema;
3. configura chrony con el servicio de hora de Amazon y comprueba que el reloj sincroniza (§10.6);
4. genera `/etc/hosts` con los nombres `<rol>-<n>` y las IP privadas, la CA interna y los certificados;
5. monta por UUID con `nofail` el volumen EBS de cada servidor de metadatos y de cada nodo de datos, y arranca los contenedores;
6. al final de cada sesión de trabajo, guarda en S3 la última instantánea de los metadatos (§4.2).

**Resolución de nombres.** Se hace por `/etc/hosts`, regenerado en cada despliegue. La IP pública cambia en cada sesión del lab, pero la privada se conserva al parar y arrancar la instancia [20]. Por eso `/etc/hosts` solo cambia si se sustituye una instancia. Una zona privada de Route 53 también funcionaría, pero añade una pieza propia de AWS sin beneficio a esta escala.

**Coste.** Con precios de lista, unos 0,125 USD/h de cómputo, más unos 11 USD/mes de volúmenes EBS, que se cobran aunque las instancias estén paradas, y unos céntimos de S3 por las copias de seguridad. El presupuesto del lab (50 USD, ampliables) lo cubre.

## 3.7 Entorno local de desarrollo

Para desarrollar y ensayar los escenarios de fallo sin gastar crédito, el mismo clúster de 9 nodos se levanta en una sola máquina con Docker Compose. Usa las mismas imágenes, nombres de host, variables y certificados, y cada cambio se aplica a la vez a los dos entornos. **Solo sirve para desarrollar**: no reproduce la latencia ni el ancho de banda de la red real, ni los créditos de CPU de las instancias t3. Las evidencias y los experimentos se obtienen siempre en AWS, porque el enunciado no admite una simulación local como producto [1]. Las copias de seguridad en S3 (§4.2) solo se hacen en el entorno `aws`; en el local, las instantáneas se quedan en los volúmenes Docker.

## 3.8 Tecnologías y su justificación

§7 del enunciado sugiere Linux, Docker, FastAPI/Flask, gRPC y, cuando proceda, RabbitMQ/Kafka, y pide justificar la elección [1]. La Tabla 11 recoge qué se usa, qué no y por qué.

**Tabla 11.** Tecnologías elegidas y descartadas.

| Tecnología | ¿Se usa? | Motivo | Límite o alternativa descartada |
|---|---|---|---|
| Linux (Ubuntu LTS) en EC2 | Sí | Sistema de las instancias del Learner Lab y de los laboratorios del curso | — |
| Python 3.12 | Sí, en todos los roles | Lenguaje de los laboratorios del curso; `grpcio` y `cryptography` (AES-GCM, scrypt) son maduras; un solo lenguaje para cliente y servidores | Es el más lento en CPU. Go rendiría más, pero no se vio en el curso; Java es pesado para 1 GiB de RAM. El coste se mide con E8 |
| gRPC y Protocol Buffers | Sí, en todas las interfaces | Flujos binarios, contrato tipado, plazos, códigos de estado y TLS (§5.1) | — |
| Docker y Docker Compose | Sí, un contenedor por instancia | La misma imagen en todas las instancias; el despliegue se rehace desde cero en cada sesión del lab | Un orquestador (Kubernetes, ECS) es excesivo para instancias t3 |
| Raft (etcd o PySyncObj) | Sí, en los servidores de metadatos | Consenso probado; implementarlo a mano sería arriesgado (§3.3) | La elección entre las dos, en la fase II |
| Amazon S3 | Sí, solo para las copias de seguridad de los metadatos | Almacén duradero fuera del clúster, disponible en el Learner Lab; lo usa el script de despliegue, no los componentes (§3.6, §4.2) | No guarda bloques: usar S3 como almacén de datos dejaría de ser un DFS propio |
| Base de datos (PostgreSQL, RDS) | No | El log y las instantáneas de Raft ya son la base de datos de los metadatos (§4.2) | Una base de datos externa sería otro punto único de fallo o necesitaría su propia replicación |
| FastAPI / Flask | No | No hay API REST: los bloques binarios y el flujo encajan mejor en gRPC (§5.1) | Se revisaría si hiciera falta acceso desde un navegador |
| RabbitMQ / Kafka | No | Las órdenes van a un nodo concreto y salen del estado de los metadatos; un broker sería otro punto único de fallo (§5.1) | Se revisaría si aparecieran eventos que difundir a varios consumidores |

# 4. Distribución de archivos, metadatos y réplicas

## 4.1 Partición en bloques

Cada archivo se divide en **bloques** de tamaño fijo, numerados desde 0. El bloque es la unidad de reparto, de replicación y de transferencia (RNF4). El último bloque puede ser más pequeño.

El tamaño de bloque es una decisión de **granularidad**. Con bloques pequeños la carga se reparte mejor, pero hay más metadatos y más peticiones; con bloques grandes ocurre lo contrario. Distribuir solo compensa si el tiempo de procesar cada parte es mucho mayor que el de coordinarla [12]. HDFS usa 64 MB en la versión 1.2.1 [4] porque está pensado para archivos de GB o TB. DFSha trabaja con archivos de 100 MiB a 1 GiB, instancias de 1 GiB de RAM y copia en escritura, que reescribe un bloque entero por cada modificación parcial (§7.2). La Tabla 12 compara tres tamaños.

**Tabla 12.** Tamaños de bloque considerados, para un archivo de 1 GiB.

| Tamaño | Bloques por GiB | Reparto entre 5 nodos de datos | Coste de cambiar un byte | Valoración |
|---|---|---|---|---|
| 4 MiB | 256 | Muy fino | Reescribir 4 MiB | Demasiados RPC y metadatos |
| **16 MiB** (elegido) | 64 | Bueno incluso con archivos de 100 MiB (7 bloques) | Reescribir 16 MiB | Equilibrio |
| 64 MiB | 16 | Malo con archivos pequeños: uno de 100 MiB solo tiene 2 bloques | Reescribir 64 MiB | Amplifica demasiado la modificación parcial |

**Decisión.** `block_size_bytes` = 16 MiB (16 777 216 bytes) por defecto, configurable en el clúster.
- Cada archivo guarda el tamaño de bloque con el que se creó, así que cambiar la configuración no afecta a los archivos existentes.
- Los bloques viajan en mensajes de 1 MiB (§5.2), así que nunca hay un bloque entero en memoria en un solo mensaje.

**Ejemplo.** Un archivo de 1 GiB tiene 64 bloques y 192 réplicas, unas 38 por nodo de datos (≈ 614 MiB por nodo). Un archivo de 40 MiB tiene 3 bloques, de 16, 16 y 8 MiB (Figura 4).

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 4 ]** · archivo: `docs/diagramas/04-particion.png` 🟥🟥

**Figura 4.** Partición de un archivo de 40 MiB en tres bloques y ubicación de sus réplicas. La réplica primaria, en gris oscuro, rota entre bloques consecutivos.

**Límite.** Hay más peticiones por GiB que con 64 MiB. El experimento E5 compara 4, 16 y 64 MiB (§12.2).

## 4.2 Metadatos

El servidor de metadatos guarda todo lo necesario para encontrar y reconstruir un archivo, pero nunca su contenido. La Figura 5 muestra el modelo y la Tabla 13 describe cada entidad.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 5, parte 1 de 2: usuarios, espacio de nombres y versiones ]** · archivo: `docs/diagramas/05-modelo-metadatos-parte-1.png` 🟥🟥

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 5, parte 2 de 2: escrituras, bloques, réplicas y nodos ]** · archivo: `docs/diagramas/05-modelo-metadatos-parte-2.png` 🟥🟥

**Figura 5.** Modelo de los metadatos.

**Tabla 13.** Entidades de los metadatos.

| Entidad | Campos principales | Notas |
|---|---|---|
| Usuario | `user_id`, nombre, hash scrypt de la contraseña y su sal, `is_admin` | Cada usuario es dueño de un espacio de nombres |
| Directorio | Ruta, propietario, entradas hijas | La raíz `/` de cada usuario se crea con él |
| Archivo | `file_id`, ruta, propietario, `block_size_bytes`, versión actual, clave de datos envuelta | La ruta puede cambiar con `mv`; el `file_id` no |
| Versión de archivo | Número de versión, lista ordenada de `block_id`, `size_bytes`, fecha de confirmación, estado (vigente o sustituida, con su fecha de caducidad) | Inmutable una vez confirmada |
| Bloque | `block_id` (UUID [21]), `block_sha256`, `size_bytes` | Inmutable; puede pertenecer a varias versiones |
| Réplica | `block_id`, `node_id`, estado (confirmada, corrupta) | Solo existe si el nodo de datos avisó de que la tiene |
| Escritura en curso | `file_id`, arrendamiento, versión base, bloques reservados | Se descarta si el arrendamiento caduca |
| Arrendamiento | `lease_id`, `file_id`, rango de bloques, usuario, caducidad | TTL de 30 s, renovable |
| Nodo de datos | `node_id`, nombre de host, capacidad, espacio libre, último latido, estado | El estado de vida solo vive en la memoria del líder (§9.5) |
| Registro de peticiones | `request_id`, respuesta guardada, caducidad | TTL de 10 min (§8.6) |

**Persistencia.** No hace falta una base de datos aparte: el log replicado y las instantáneas de Raft son la base de datos de los metadatos. Todo el estado anterior, salvo el último latido de cada nodo, es la máquina de estados de Raft: vive en memoria y se reconstruye a partir de la última instantánea y del log. HDFS hace lo mismo: el NameNode mantiene el espacio de nombres en memoria y guarda en su disco local un log de transacciones (EditLog) y una imagen periódica (FsImage) [4]. Una base de datos externa, como PostgreSQL, sería otro punto único de fallo o necesitaría su propia replicación, que es justo lo que ya resuelve Raft.
- **Dónde.** Cada servidor de metadatos guarda el log y las instantáneas en un volumen EBS gp3 de 4 GiB propio, cifrado y con la etiqueta `dfsha-metadata-<n>-data`. Se monta por UUID, y el servidor comprueba al arrancar que está montado. Si la instancia se rompe, el volumen se conecta a otra con el mismo nombre de host, sin cambiar la composición del clúster de Raft.
- **Durabilidad.** Cada entrada se escribe en disco con `fsync` antes de contar para la mayoría, como exige Raft [2]. Si no fuera así, una caída de dos servidores podría perder escrituras ya confirmadas, y G1 dejaría de cumplirse (§7.3). Es un requisito para elegir la implementación en la fase II.
- **Atomicidad.** Confirmar una versión, un `mv` o un `rm` es **una sola** entrada del log (§8.4): o se aplica entera o no se aplica, así que nada queda confirmado a medias. En etcd sería una transacción con varias escrituras.
- **Copias de seguridad.** Raft protege frente a la pérdida de un servidor, pero no frente a la de los tres ni frente a un borrado por error, que se replica a todos. Al final de cada sesión de trabajo, el script de despliegue guarda la última instantánea del líder en un bucket privado y cifrado de S3. No hay recuperación a un momento anterior a esa copia (L11).

**Tamaño.** Un archivo de 1 GiB ocupa unos pocos KiB de metadatos (64 `block_id` con sus hashes y 192 réplicas). Los metadatos de todo el clúster caben con holgura en los 2 GiB de RAM de una t3.small.

## 4.3 Ubicación de réplicas

Cuando se reserva un bloque nuevo, el servidor de metadatos elige sus R nodos de datos así:
- solo entre nodos **vivos** que hayan enviado un latido desde la última elección de líder (§9.5);
- los que tienen **más espacio libre** según su último latido, con desempate aleatorio;
- **nunca dos réplicas del mismo bloque en el mismo nodo**;
- la **réplica primaria rota** entre bloques consecutivos, para que la carga de reenvío se reparta.

Al leer, el cliente pide todas las ubicaciones al abrir el archivo y lee cada bloque de una réplica elegida al azar, varios bloques en paralelo. La carga de escritura y de lectura se reparte entre todos los nodos de datos.

**Alternativas descartadas.** La ubicación aleatoria uniforme puede quedar desequilibrada con pocos bloques. El hash consistente, como en Chord, elimina el estado de ubicación, pero mueve datos cada vez que entra o sale un nodo. DFSha ya guarda las ubicaciones en los metadatos, así que no aporta nada.

**Límite.** No hay conciencia de rack ni de zona, porque solo hay una zona (L1). Lo ya escrito no se rebalancea: un nodo nuevo solo recibe bloques nuevos (L4).

## 4.4 Replicación

Hay que decidir cuántas réplicas tiene cada bloque, cuándo se considera escrito y cómo llega a cada réplica. Añadir réplicas no acelera el sistema: las réplicas conservan estado y los trabajadores procesan [15]. El factor de replicación se justifica por tolerancia a fallos, no por rendimiento. Que el cliente lea cada bloque de una réplica distinta reparte la carga de lectura, pero es un efecto secundario, no el motivo de tener tres réplicas. La Tabla 14 compara las opciones.

**Tabla 14.** Alternativas de replicación.

| Alternativa | Ventaja | Inconveniente |
|---|---|---|
| R = 3, W = 3 | Máxima durabilidad al confirmar | La réplica más lenta marca la latencia; con un nodo caído no se puede escribir hasta detectarlo |
| **R = 3, W = 2** (elegida) | Latencia de las dos réplicas más rápidas; se sigue escribiendo con un nodo caído | Durante un rato el bloque tiene dos réplicas |
| R = 2 | Menos disco | Tolera un solo fallo, sin margen |
| Propagación en cadena (HDFS) | El cliente envía el bloque una vez | La latencia suma los saltos [4] |
| Propagación desde el cliente a las tres | Sin dependencia de la primaria | El cliente envía el bloque tres veces |
| **Reenvío en paralelo desde la réplica primaria** (elegida) | El cliente envía una vez; latencia de la réplica más rápida | La primaria envía el doble de tráfico de salida |

**Decisión.** `replication_factor` = 3 y `write_quorum` = 2, es decir, una mayoría de 3. La escritura de un bloque sigue estos pasos:
1. El servidor de metadatos asigna tres nodos de datos; el primero es la réplica primaria.
2. La primaria recibe el bloque del cliente, lo guarda y lo reenvía **en paralelo** a las dos secundarias.
3. Responde OK al cliente cuando al menos **dos réplicas**, ella incluida, lo tienen en disco con el hash verificado.
4. La tercera termina en segundo plano. Si falla, el bloque queda con menos réplicas de las debidas y la re-replicación lo corrige (§9.3).

Confirmar con una mayoría no es esperar a todas. En el ejemplo de clase, con respuestas a los 12, 20 y 55 ms, la mayoría confirma a los 20 ms en lugar de a los 55 ms. A cambio, la tercera réplica queda atrasada un tiempo [15]. Es el compromiso entre latencia y consistencia que el experimento E3 mide (§12.2).

**Quién cuenta las réplicas.** El servidor de metadatos no se fía del cliente (S5). Cada nodo de datos le avisa directamente de cada bloque que guarda con el hash verificado (aviso de bloque recibido), y solo esos avisos cuentan para confirmar una escritura (§8.4).

**Lectura.** Basta una réplica: el bloque es inmutable y su hash se verifica, así que dos réplicas de un bloque son idénticas o una de ellas está corrupta y se detecta. No hay quórum de lectura.

**Por debajo del quórum.** Si no hay al menos W = 2 nodos de datos vivos con espacio, el sistema **rechaza las escrituras nuevas** con `UNAVAILABLE` + `QUORUM_NOT_REACHED`, y **sigue sirviendo las lecturas** de cualquier réplica viva. Tener una sola réplica viva no significa que se hayan perdido datos [15].

## 4.5 Reconstrucción del archivo

Para leer un archivo, el cliente:
1. abre el archivo, lo que fija una versión: la lista ordenada de `block_id` y el tamaño total;
2. pide las ubicaciones y los tokens de lectura de todos sus bloques en una sola llamada;
3. lee los bloques en paralelo, cada uno de una réplica distinta elegida al azar;
4. verifica el `block_sha256` de cada bloque con el que dio el servidor de metadatos (no con el del nodo de datos) y lo descifra con AES-256-GCM, que comprueba además la etiqueta de autenticación;
5. si una réplica no responde o falla la verificación, pasa a otra;
6. concatena los bloques en el orden de la versión y recorta el último según `size_bytes`.

Como la versión fija exactamente qué bloques forman el archivo, el resultado es siempre una versión confirmada completa: nunca una mezcla de dos versiones (G4, §7.3). La prueba de carga y recuperación (§5.2 del enunciado) lo comprueba comparando el hash del archivo original con el del recuperado.

# 5. Protocolos y APIs

## 5.1 Elección de protocolos

El enunciado pide elegir el protocolo de cada interfaz «según corresponda» entre REST, gRPC, TCP o MOM (§4.1), y justificar la elección (§7) [1]. Antes de elegir hay que mirar qué naturaleza tiene cada interacción (Tabla 15).

**Tabla 15.** Interacciones de DFSha y su naturaleza.

| Interacción | Naturaleza | Protocolo |
|---|---|---|
| Cliente → servidor de metadatos (`open`, `lock`, `commit`, `ls`…) | Petición-respuesta: el cliente necesita la respuesta para seguir | gRPC unario |
| Cliente ↔ nodo de datos | Transferencia de bloques de 16 MiB en flujo | gRPC con *streaming* |
| Réplica primaria → secundarias; nodo → nodo al re-replicar | Transferencia en flujo | gRPC con *streaming* |
| Nodo de datos → servidor de metadatos (latido, informes, avisos) | Periódica; la respuesta lleva órdenes para el nodo | gRPC unario |
| Entre servidores de metadatos | Consenso | El protocolo de la implementación de Raft |
| Trabajo en segundo plano (re-replicar, borrar, verificar) | Órdenes a un nodo concreto, derivadas del estado de los metadatos | En la respuesta al latido |

La Tabla 16 compara las opciones.

**Tabla 16.** Alternativas de protocolo.

| Alternativa | Ventaja | Inconveniente para DFSha |
|---|---|---|
| REST/JSON (FastAPI) | Legible; se prueba con `curl` | Los bloques binarios van en base64 (un 33 % más de datos) o en multipart; no hay contrato tipado ni flujo bidireccional estándar; los plazos se programan a mano |
| **gRPC** (elegida) | Protobuf binario y flujos sobre HTTP/2; contrato `.proto` con código generado; plazos, códigos de estado y TLS incluidos [22], [23] | No se usa desde un navegador; para inspeccionar hace falta `grpcurl` |
| MOM (RabbitMQ) para el trabajo en segundo plano | Desacoplamiento temporal: la orden espera en la cola si el nodo está caído [24] | Añade un broker, que es otro punto único de fallo salvo que se monte un clúster de tres. Las órdenes van a un nodo concreto, así que no hay consumidores que compitan, y la cola sería una segunda fuente de verdad además de los metadatos |
| TCP propio | Máximo control | Obliga a reinventar el enmarcado de mensajes, los errores y TLS |

**Decisión.** gRPC en todas las interfaces, sin MOM ni API REST:
- **El trabajo en segundo plano viaja en la respuesta al latido**, como en HDFS, donde el NameNode nunca inicia una llamada [4]. Si una orden se pierde, no queda guardada en una cola. Pero tampoco hace falta: el servidor de metadatos la vuelve a calcular a partir de su estado en el siguiente latido (reconciliación). Es la ventaja de que haya una sola fuente de verdad.
- **Cuándo se revisaría:** si aparecieran consumidores de eventos que necesitaran difusión, como una auditoría o notificaciones a varios destinatarios, un MOM con tópicos tendría sentido [24].

## 5.2 Servicios y RPC

Hay dos servicios en el paquete `dfsha.v1`, uno por rol de servidor. Los nombres siguen la forma *verbo + objeto* (`GetBlockLocations`, `CommitFile`). La Tabla 17 y la Tabla 18 los resumen, y el Anexo A los especifica completos.

**Tabla 17.** RPC de `MetadataService`.

| RPC | Quién llama | Para qué | Operación de usuario | Idempotencia |
|---|---|---|---|---|
| `Authenticate` | Cliente | Cambia usuario y contraseña por un token de acceso | — | Sin efectos |
| `CreateUser` | Administrador | Da de alta un usuario | — | `request_id` |
| `ListDirectory` | Cliente | Lista un directorio | `ls` | Sin efectos |
| `GetFileInfo` | Cliente | Tamaño, versión y tamaño de bloque de un archivo | `ls`, `get` | Sin efectos |
| `CreateDirectory` | Cliente | Crea un directorio | `mkdir` | `request_id` |
| `DeleteDirectory` | Cliente | Borra un directorio vacío | `rmdir` | `request_id` |
| `DeleteFile` | Cliente | Borra un archivo | `rm` | `request_id` |
| `MovePath` | Cliente | Mueve o renombra, de forma atómica | `mv` | `request_id` |
| `OpenFile` | Cliente | Abre un archivo: descriptor, versión y clave de datos | `open` | Sin efectos |
| `GetBlockLocations` | Cliente | Ubicaciones, hashes y tokens de lectura de un rango de bloques | `open`, `read` | Sin efectos |
| `LockBlocks` | Cliente | Concede un arrendamiento sobre un rango de bloques | `lock`, `write` | `request_id` |
| `UpdateLease` | Cliente | Renueva un arrendamiento | — | `request_id` |
| `UnlockBlocks` | Cliente | Libera un arrendamiento | `unlock`, `close` | `request_id` |
| `AllocateBlocks` | Cliente | Reserva bloques nuevos: `block_id`, nodos y tokens de escritura | `write` | `request_id` |
| `CommitFile` | Cliente | Confirma una versión nueva de forma atómica | `close` | `request_id` |
| `AbortFile` | Cliente | Descarta una escritura en curso | `close` tras un error | `request_id` |
| `RegisterDataNode` | Nodo de datos | Se da de alta en el clúster | — | Por `node_id` |
| `ReportHeartbeat` | Nodo de datos | Latido con espacio libre; la respuesta trae órdenes | — | Sin efectos acumulativos |
| `ReportBlocks` | Nodo de datos | Informe de bloques completo | — | Por contenido |
| `ReportBlockReceived` | Nodo de datos | Aviso de que guardó un bloque con el hash verificado | — | Por `block_id` y `node_id` |
| `ReportCorruptReplica` | Nodo de datos o cliente | Avisa de una réplica corrupta | `read` | Por `block_id` y `node_id` |

**Tabla 18.** RPC de `DataNodeService`.

| RPC | Tipo | Quién llama | Para qué |
|---|---|---|---|
| `WriteBlock` | Flujo del cliente al servidor | Cliente (a la primaria); primaria (a las secundarias); nodo origen (al destino, al re-replicar) | Envía un bloque en mensajes de 1 MiB. La primera petición es una cabecera con el `block_id`, el token de bloque, el hash y la lista de secundarias |
| `ReadBlock` | Flujo del servidor al cliente | Cliente | Recibe un bloque en mensajes de 1 MiB, tras una cabecera con su tamaño y su hash |

**Órdenes en la respuesta al latido.** `ReportHeartbeat` y `ReportBlocks` devuelven una lista de órdenes para el nodo de datos (Tabla 19).

**Tabla 19.** Órdenes que el servidor de metadatos envía en la respuesta al latido.

| Orden | Efecto en el nodo de datos | Cuándo la emite el servidor |
|---|---|---|
| `REPLICATE` | Copia un bloque a otro nodo con `WriteBlock`, usando el token que trae la orden | Un bloque tiene menos de R réplicas (§9.3) |
| `DELETE` | Borra un bloque de su almacén | Bloque huérfano, réplica de más o réplica corrupta ya sustituida |
| `VERIFY` | Recalcula el hash de un bloque y avisa si no coincide | Un cliente avisó de una réplica corrupta (§8.5) |
| `SEND_BLOCK_REPORT` | Envía un informe de bloques completo | El servidor no conoce al nodo, por ejemplo tras una elección |

## 5.3 Autenticación en las llamadas y plazos

- **Token de acceso.** Cada llamada del cliente lleva su token de acceso en los metadatos de gRPC (`authorization: Bearer <token>`). Las llamadas internas se autentican con el certificado del nodo, por TLS mutuo (§10.4).
- **Token de bloque.** `WriteBlock` y `ReadBlock` llevan además un token de bloque firmado por el servidor de metadatos, que el nodo de datos verifica sin consultarlo (§10.3).
- **Plazos.** Toda llamada gRPC lleva un plazo (*deadline*). Sin plazo, un cliente puede esperar indefinidamente [25], que es justo lo que ocurre en el laboratorio de gRPC del curso [26]. El cliente siempre recibe una respuesta en un tiempo razonable: el resultado o un error explícito.

## 5.4 Errores

Los errores usan primero los códigos de estado estándar de gRPC [27], con su significado: `UNAVAILABLE` es transitorio y se reintenta con espera; `ABORTED` indica un conflicto de concurrencia y obliga a repetir la secuencia completa; `FAILED_PRECONDITION` no se reintenta hasta que cambie el estado. Para dar más detalle, cada error lleva un **código de motivo** propio en un mensaje `ErrorInfo` del modelo de error enriquecido de gRPC [28], con dominio `dfsha.v1` y datos adicionales cuando hace falta (por ejemplo, la dirección del líder). El texto del error está en español y es para el usuario; el código es para los programas y las pruebas (Tabla 20).

**Tabla 20.** Códigos de error.

| Estado gRPC | Código de motivo | Dónde aparece | Qué hace el cliente |
|---|---|---|---|
| `UNAUTHENTICATED` | `ACCESS_TOKEN_EXPIRED` | Cualquier RPC del cliente | Vuelve a autenticarse |
| `PERMISSION_DENIED` | `BLOCK_TOKEN_INVALID` | `WriteBlock`, `ReadBlock` | Pide tokens nuevos (`GetBlockLocations` o `AllocateBlocks`) |
| `NOT_FOUND` | `PATH_NOT_FOUND` | `ls`, `open`, `rm`, `mv`, `mkdir` (padre) | Informa al usuario |
| `ALREADY_EXISTS` | `PATH_ALREADY_EXISTS` | `mkdir`, `mv`, `open` en modo creación | Informa al usuario |
| `INVALID_ARGUMENT` | `PATH_INVALID`, `BLOCK_RANGE_INVALID` | Cualquier RPC con ruta o rango | Corrige la petición |
| `FAILED_PRECONDITION` | `DIRECTORY_NOT_EMPTY` | `rmdir` | Informa al usuario |
| `FAILED_PRECONDITION` | `FILE_VERSION_EXPIRED` | `read` de una versión sustituida hace más de 10 min | Vuelve a abrir el archivo |
| `ABORTED` | `LOCK_CONFLICT` | `LockBlocks`, `rm` | Reintenta con espera |
| `ABORTED` | `LEASE_EXPIRED` | `CommitFile`, `AllocateBlocks`, `UpdateLease` | Repite la escritura completa |
| `ABORTED` | `VERSION_CONFLICT` | `CommitFile` | Vuelve a abrir, lee la versión nueva y repite |
| `ABORTED` | `BLOCK_CORRUPTED` | `WriteBlock` (el hash recibido no coincide) | Vuelve a enviar el bloque |
| `DATA_LOSS` | `BLOCK_CORRUPTED` | `ReadBlock` (la réplica guardada no coincide con su hash) | Lee de otra réplica |
| `DATA_LOSS` | `BLOCK_LOST` | `get`/`read` cuando todas las réplicas de un bloque están perdidas o corruptas | Informa al usuario |
| `UNAVAILABLE` | `NODE_NOT_LEADER` | Cualquier RPC de `MetadataService` en un seguidor; trae `leader_addr` | Repite en el líder |
| `UNAVAILABLE` | `SAFE_MODE_ACTIVE` | Operaciones que cambian metadatos durante el modo seguro (§9.5) | Reintenta con espera |
| `UNAVAILABLE` | `QUORUM_NOT_REACHED` | `WriteBlock` con menos de W réplicas; `AllocateBlocks` con menos de W nodos vivos; `CommitFile` con bloques sin W avisos | Reintenta; si persiste, vuelve a reservar el bloque |
| `DEADLINE_EXCEEDED` | — | Cualquier RPC | Reintenta con el mismo `request_id`; la operación pudo haberse ejecutado |

## 5.5 Ejemplos de mensajes

Los ejemplos usan el formato de texto de Protocol Buffers. Las rutas, los nombres y los identificadores son ilustrativos.

**Carga: reservar bloques.** El cliente ya tiene un arrendamiento sobre el archivo entero y reserva sus 3 bloques.

```text
# AllocateBlocksRequest
request_id: "6f9c1e2a-0d4b-4c7e-9a51-3b2f8e7d1c40"
file_handle: "<opaco, firmado por el servidor>"
lease_id: "lease-7731"
block_indices: [0, 1, 2]

# AllocateBlocksResponse
blocks {
  block_index: 0
  block_id: "b-0c41f2d8-7e1a-4b8f-a3d2-9f6e1c5b7a20"
  datanode_addrs: ["datanode-2:50052", "datanode-4:50052", "datanode-5:50052"]   # la primera es la primaria
  block_token { block_id: "b-0c41f2d8-…" operation: BLOCK_OPERATION_WRITE
                expires_at { seconds: 1793030400 } signature: "<HMAC-SHA256>" }
}
blocks { block_index: 1  block_id: "b-91d3…"  datanode_addrs: ["datanode-4:50052", "datanode-1:50052", "datanode-3:50052"]  … }
blocks { block_index: 2  block_id: "b-e27a…"  datanode_addrs: ["datanode-1:50052", "datanode-3:50052", "datanode-2:50052"]  … }
```

**Carga: enviar un bloque a la primaria.** La primera petición del flujo es la cabecera; las siguientes llevan 1 MiB cada una.

```text
# WriteBlockRequest 1 (cabecera)
header {
  block_id: "b-0c41f2d8-…"
  block_token { … }
  block_sha256: "<32 bytes: SHA-256 del bloque cifrado>"
  size_bytes: 16777244          # 16 MiB de datos + 12 bytes de nonce + 16 bytes de etiqueta GCM
  secondary_addrs: ["datanode-4:50052", "datanode-5:50052"]
}
# WriteBlockRequest 2..18 (16 mensajes de 1 MiB y uno de 28 bytes)
data: "<1 MiB>"

# WriteBlockResponse
stored_on: ["datanode-2:50052", "datanode-4:50052"]   # W = 2 alcanzado; datanode-5 termina en segundo plano
```

**Carga: confirmar.**

```text
# CommitFileRequest
request_id: "1b7e…"
file_handle: "<…>"
lease_id: "lease-7731"
write_mode: WRITE_MODE_REPLACE
blocks { block_index: 0  block_id: "b-0c41…"  block_sha256: "<…>"  size_bytes: 16777244 }
blocks { block_index: 1  block_id: "b-91d3…"  block_sha256: "<…>"  size_bytes: 16777244 }
blocks { block_index: 2  block_id: "b-e27a…"  block_sha256: "<…>"  size_bytes: 8388636 }
size_bytes: 41943040            # 40 MiB en claro

# CommitFileResponse
version: 4
```

**Recuperación: pedir las ubicaciones.**

```text
# GetBlockLocationsRequest
file_handle: "<versión 4 de /informes/2026.pdf>"
block_range { first_block_index: 0  block_count: 0 }   # 0 = todos los bloques

# GetBlockLocationsResponse
locations { block_index: 0  block_id: "b-0c41…"  block_sha256: "<…>"  size_bytes: 16777244
            datanode_addrs: ["datanode-2:50052", "datanode-4:50052", "datanode-5:50052"]
            block_token { operation: BLOCK_OPERATION_READ … } }
locations { block_index: 1 … }
locations { block_index: 2 … }
```

**Modificación parcial: arrendamiento sobre un rango.** El cliente quiere cambiar bytes que caen en los bloques 1 y 2.

```text
# LockBlocksRequest
request_id: "a40d…"
file_handle: "<versión 4>"
block_range { first_block_index: 1  block_count: 2 }

# LockBlocksResponse
lease_id: "lease-7790"
expires_at { seconds: 1793030430 }     # TTL de 30 s
current_version: 4                     # coincide con la versión abierta: no hay conflicto previsible
```

**Conflicto de cerrojo.** Otro proceso pide un rango que se solapa con `lease-7790`.

```text
# Respuesta de LockBlocks
status: ABORTED
message: "El bloque 2 de /informes/2026.pdf está arrendado por otro escritor"
details: ErrorInfo { reason: "LOCK_CONFLICT"  domain: "dfsha.v1"
                     metadata { key: "retry_after_ms"  value: "500" } }
```

**Caída de una réplica durante la escritura.** `datanode-5` no responde; la primaria confirma igualmente con dos réplicas.

```text
# WriteBlockResponse de la primaria
stored_on: ["datanode-2:50052", "datanode-4:50052"]
# Si también falla datanode-4:
status: UNAVAILABLE
details: ErrorInfo { reason: "QUORUM_NOT_REACHED"  domain: "dfsha.v1"
                     metadata { key: "stored_replicas"  value: "1" } }
```

**Redirección al líder.** El cliente preguntó a un seguidor.

```text
status: UNAVAILABLE
message: "metadata-3 no es el líder"
details: ErrorInfo { reason: "NODE_NOT_LEADER"  domain: "dfsha.v1"
                     metadata { key: "leader_addr"  value: "metadata-1:50051" } }
```

**Escritura rechazada en modo seguro.**

```text
status: UNAVAILABLE
message: "El servidor de metadatos acaba de ser elegido líder y está en modo seguro"
details: ErrorInfo { reason: "SAFE_MODE_ACTIVE"  domain: "dfsha.v1"
                     metadata { key: "retry_after_ms"  value: "3000" } }
```

**Réplica corrupta.** El nodo de datos detecta, al terminar de enviar el bloque, que su hash no coincide.

```text
# Fin del flujo de ReadBlock
status: DATA_LOSS
details: ErrorInfo { reason: "BLOCK_CORRUPTED"  domain: "dfsha.v1"
                     metadata { key: "block_id"  value: "b-91d3…" } }

# ReportCorruptReplicaRequest (lo envía el propio nodo de datos)
block_id: "b-91d3…"
node_id: "datanode-1"
```

# 6. Flujos de operación

Esta sección describe las secuencias de carga, lectura, escritura y borrado que pide §4.1 del enunciado, con los RPC de la sección 5. Todas suponen que el cliente ya tiene un token de acceso válido y que habla con el líder de los servidores de metadatos. Si habla con un seguidor, recibe `NODE_NOT_LEADER` y repite la llamada en el líder (§11.4).

## 6.1 Carga de un archivo (`put`)

`put` es una escritura en modo reemplazo, o creación si el archivo no existe, sobre el archivo entero. La Figura 6 muestra la secuencia para un bloque; los demás bloques siguen el mismo camino en paralelo.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 6 ]** · archivo: `docs/diagramas/06-secuencia-carga.png` 🟥🟥

**Figura 6.** Secuencia de carga de un archivo (`put`).

1. **Abrir.** `OpenFile(ruta, CREATE o WRITE)` devuelve un descriptor de archivo, la versión actual y la clave de datos. Si el archivo es nuevo, el servidor genera la clave de datos y la guarda envuelta.
2. **Arrendar.** `LockBlocks` sobre el archivo entero. Si otro escritor tiene un arrendamiento sobre cualquier bloque del archivo, la respuesta inmediata es `LOCK_CONFLICT`.
3. **Reservar.** `AllocateBlocks` con los índices de todos los bloques. El servidor registra una escritura en curso y devuelve, para cada bloque, un `block_id` nuevo, tres nodos de datos y un token de escritura.
4. **Cifrar y enviar.** Para cada bloque, el cliente cifra con AES-256-GCM, calcula el `block_sha256` del resultado y lo envía con `WriteBlock` a la réplica primaria. Varios bloques viajan a la vez, cada uno a una primaria distinta.
5. **Replicar.** La primaria escribe el bloque en su área temporal, lo reenvía en paralelo a las dos secundarias y responde cuando dos réplicas lo tienen verificado (§4.4). Cada nodo de datos que lo guarda envía `ReportBlockReceived` al servidor de metadatos.
6. **Renovar.** Si la carga dura más de unos 10 s, el cliente renueva el arrendamiento con `UpdateLease` antes de que caduque a los 30 s.
7. **Confirmar.** `CommitFile` con la lista de bloques. El servidor comprueba el arrendamiento, la versión y que cada bloque tiene al menos dos avisos de bloque recibido. Después confirma la versión nueva con una sola entrada del log replicado. La carga está confirmada cuando `CommitFile` devuelve OK.
8. **Liberar.** `UnlockBlocks`. La versión anterior, si la había, queda sustituida y sus bloques se borran pasado el periodo de gracia.

Si algo falla antes del paso 7, el archivo sigue en su versión anterior y los bloques ya enviados quedan huérfanos hasta que los borra la recolección de basura (§8.4).

## 6.2 Lectura y recuperación de un archivo (`get`, `read`)

`get` es una lectura completa. `read(h, offset, n)` lee solo los bloques que cubren el rango pedido. La Figura 7 muestra la secuencia.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 7 ]** · archivo: `docs/diagramas/07-secuencia-lectura.png` 🟥🟥

**Figura 7.** Secuencia de lectura de un archivo (`get` y `read`).

1. **Abrir.** `OpenFile(ruta, READ)` fija la versión que se va a leer y entrega la clave de datos.
2. **Ubicar.** `GetBlockLocations` con el rango completo devuelve, en una sola llamada, los `block_id`, sus hashes, las ubicaciones y los tokens de lectura de todos los bloques.
3. **Leer.** El cliente pide cada bloque con `ReadBlock` a una réplica elegida al azar, varios en paralelo.
4. **Verificar y descifrar.** Comprueba el `block_sha256` con el que dio el servidor de metadatos y descifra con AES-256-GCM, que verifica la etiqueta de autenticación.
5. **Fallar a otra réplica.** Si la réplica no responde dentro del plazo, devuelve `DATA_LOSS` o falla la verificación, el cliente pasa a otra réplica del mismo bloque y, si la corrupción no la avisó el nodo, la avisa él (§8.5).
6. **Entregar.** `get` escribe los bloques en orden en el archivo local; `read` devuelve los bytes pedidos.

Si una lectura dura más de 10 min, los tokens caducan y el cliente pide otros con `GetBlockLocations`, sobre el mismo descriptor y, por tanto, sobre la misma versión.

## 6.3 Modificación parcial y anexado (`write`)

La Figura 8 muestra una modificación parcial, el caso más completo.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 8 ]** · archivo: `docs/diagramas/08-secuencia-escritura.png` 🟥🟥

**Figura 8.** Secuencia de una modificación parcial con copia en escritura.

1. **Abrir** en modo escritura, lo que fija la versión base *v*.
2. **Arrendar** el rango de bloques que cubre el cambio: `lock(h, rango)`, o de forma implícita en el primer `write()`. La respuesta trae la versión actual. Si ya no es *v*, otro escritor confirmó algo entre medias; si tocó este rango, la confirmación fallará, así que el cliente vuelve a abrir el archivo antes de escribir, no después.
3. **Leer los bloques afectados** de la versión *v*, aplicar el cambio en memoria y **reservar bloques nuevos** solo para esos índices.
4. **Enviar** los bloques nuevos como en la carga.
5. **Confirmar** en `close()`. La versión *v + 1* reutiliza **por referencia** los `block_id` de los bloques no afectados y sustituye los del rango. El servidor rechaza la confirmación con `VERSION_CONFLICT` si algún índice del rango ya no tiene el `block_id` de *v* (§8.2).

**Anexado.** El arrendamiento cubre la cola del archivo, desde el último bloque. Si el último bloque no está lleno, se reescribe como un bloque nuevo con los datos añadidos; después se reservan los bloques que hagan falta.

## 6.4 Borrado de un archivo (`rm`)

La Figura 9 muestra el borrado y la recolección de basura posterior.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 9 ]** · archivo: `docs/diagramas/09-secuencia-borrado.png` 🟥🟥

**Figura 9.** Secuencia de borrado de un archivo y recolección de basura.

1. `DeleteFile(ruta)`. Si hay un arrendamiento de escritura activo sobre el archivo, la respuesta es `ABORTED` + `LOCK_CONFLICT`: no se borra un archivo mientras alguien lo escribe.
2. El servidor marca la versión vigente como sustituida, con una caducidad de 10 min, y quita la entrada del espacio de nombres. Todo ello es una sola entrada del log. Desde ese momento el archivo no aparece en `ls` ni se puede abrir.
3. Los lectores que ya lo tenían abierto siguen leyendo su versión durante el periodo de gracia.
4. Pasados los 10 min, los bloques que ya no pertenecen a ninguna versión viva se marcan como huérfanos. En la respuesta al siguiente latido de cada nodo que los guarda va una orden `DELETE`.
5. El nodo de datos borra los bloques. Si el nodo estaba caído, la orden se vuelve a calcular cuando su informe de bloques muestre que aún los tiene.

## 6.5 Operaciones del espacio de nombres

`ls`, `mkdir`, `rmdir` y `mv` solo tocan metadatos: no intervienen los nodos de datos.
- `mkdir` crea un solo nivel, y el directorio padre tiene que existir.
- `rmdir` solo borra directorios vacíos.
- `mv` cambia la ruta de un archivo o de un directorio con todo su contenido, en una sola entrada del log, así que es atómico.
- Los descriptores abiertos apuntan al `file_id`, no a la ruta, así que un `mv` no afecta a quien tiene el archivo abierto.
- Todas las operaciones que modifican el espacio de nombres llevan un `request_id`, de modo que un reintento tras un plazo vencido no duplica el efecto: un `mkdir` repetido devuelve la misma respuesta, no `ALREADY_EXISTS` (§8.6).

# 7. Semántica de `read()` y `write()`

RF3 obliga a declarar qué admite `write()`, y §7 del enunciado exige garantías de consistencia que se puedan comprobar: cuándo se confirma una escritura y qué pueden leer los demás clientes [1]. Todo lo que el enunciado deja abierto se declara aquí, porque lo que no se declara se evalúa como no resuelto.

## 7.1 Granularidad

- **En la interfaz**, la granularidad es el **byte**. `read(h, offset, n)` y `write(h, offset, datos, modo)` aceptan cualquier `offset` y cualquier tamaño.
- **Por dentro**, la granularidad es el **bloque**. Una lectura transfiere los bloques completos que cubren el rango pedido, y una escritura crea bloques nuevos completos.

**Límite (L5).** Leer un solo byte transfiere un bloque de 16 MiB, porque AES-GCM solo puede verificar la etiqueta de autenticación con el bloque completo. El cliente guarda en caché los bloques leídos mientras el archivo está abierto, así que las lecturas siguientes dentro del mismo bloque no vuelven a la red.

## 7.2 Modos de escritura

Hay dos formas de admitir escrituras parciales (Tabla 21).

**Tabla 21.** Alternativas para la semántica de escritura.

| Alternativa | Ventaja | Inconveniente |
|---|---|---|
| Solo creación y reemplazo (*write-once-read-many*, como HDFS 1.x [4]) | Muy simple: las réplicas nunca cambian | Es una simplificación de RF3 que habría que aprobar, y el objetivo es no simplificar [9] |
| Bloques mutables, modificados en el sitio | La escritura parcial es barata | Las réplicas de un bloque pueden quedar con contenidos distintos. Hace falta una réplica que ordene las escrituras, versiones por bloque y lecturas con quórum |
| **Bloques inmutables con copia en escritura** (elegida) | Las réplicas de un bloque son idénticas o no existen; los cuatro modos se reducen a lo mismo: crear bloques nuevos y confirmar una versión nueva | Amplificación de escritura: cambiar un byte reescribe un bloque entero |

**Decisión.** Un bloque escrito no cambia nunca. Cada escritura confirmada produce una **versión de archivo** nueva, que es la lista ordenada de los `block_id` del archivo. `write()` admite los cuatro modos que pide RF3 (Tabla 22).

**Tabla 22.** Modos de escritura de `write()`.

| Modo (`WriteMode`) | Arrendamiento que pide | Bloques nuevos | Bloques que reutiliza |
|---|---|---|---|
| Creación (`WRITE_MODE_CREATE`) | El archivo entero; el archivo no debe existir | Todos | Ninguno |
| Reemplazo (`WRITE_MODE_REPLACE`) | El archivo entero | Todos | Ninguno |
| Anexado (`WRITE_MODE_APPEND`) | La cola, desde el último bloque | El último, si no estaba lleno, y los añadidos | Todos menos el último |
| Modificación parcial (`WRITE_MODE_PARTIAL`) | Los bloques que cubre el rango escrito | Los del rango | Todos los demás, por referencia |

Una modificación parcial que se extiende más allá del final del archivo lo alarga, igual que un anexado.

## 7.3 Visibilidad y garantías de consistencia

DFSha usa **consistencia de apertura-cierre** (*close-to-open*), la de AFS y NFS [29]. `open()` fija la versión que se va a leer, y una escritura se vuelve visible cuando se confirma al cerrar. Una garantía de consistencia se define por lo que pueden observar las operaciones, no porque todas las copias sean iguales en cada instante [15], [6, cap. 7]. Por eso las garantías de la Tabla 23 están formuladas en términos de lo que ve cada cliente, y cada una tiene una prueba que la comprueba.

**Tabla 23.** Garantías de consistencia y cómo se comprueban.

| Garantía | Enunciado | Cómo se comprueba en la fase II |
|---|---|---|
| **G1. Cuándo se confirma** | Una escritura está confirmada cuando `close()` devuelve OK. En ese momento la versión nueva está en el log replicado de la mayoría de los servidores de metadatos y cada bloque nuevo tiene al menos W = 2 réplicas verificadas | Tras el OK, se tumba el líder de metadatos y una réplica de cada bloque: la versión sigue legible e idéntica (hash) |
| **G2. Qué ve un `open()` posterior** | Todo `open()` que empieza después de la confirmación lee esa versión o una más reciente | Un cliente confirma y avisa a otro, que abre y compara el hash |
| **G3. Qué ve un lector que ya tenía el archivo abierto** | Sigue viendo la misma versión, completa, aunque otro cliente confirme otra mientras tanto | Un lector abre, otro escribe y confirma, el primero termina de leer: su hash es el de la versión antigua |
| **G4. Qué no se ve nunca** | Una versión no confirmada, o una mezcla de bloques de dos versiones | Lectores en bucle mientras un escritor reemplaza el archivo: cada lectura coincide con el hash de alguna versión confirmada |

**Requisitos que impone.** G2 exige que las lecturas de metadatos sean linealizables, y por eso las atiende siempre el líder de Raft (§3.3). G3 exige conservar las versiones sustituidas mientras haya lectores, lo que se resuelve con el periodo de gracia.

**Límite (L6).** Un lector que mantiene una versión abierta más de 10 min después de que la sustituyan puede encontrar sus bloques borrados. Entonces `read()` falla con `FAILED_PRECONDITION` + `FILE_VERSION_EXPIRED`, y el cliente tiene que volver a abrir el archivo. El fallo es explícito: nunca se devuelven datos de otra versión.

## 7.4 Comportamiento de los accesos concurrentes

**Tabla 24.** Qué ocurre con cada combinación de accesos concurrentes al mismo archivo.

| Situación | Qué ocurre | Por qué |
|---|---|---|
| Varios lectores | Leen a la vez sin coordinarse | Las lecturas no toman cerrojo |
| Lector y escritor | El lector ve su versión hasta el final (G3); el escritor confirma la suya | La versión del lector es inmutable |
| Dos escritores en rangos de bloques **distintos** | Escriben a la vez y los dos confirman: la segunda confirmación se aplica sobre la primera | Los arrendamientos no se solapan y la comprobación de versión solo mira el rango propio (§8.2) |
| Dos escritores en rangos **solapados** | El segundo recibe `LOCK_CONFLICT` al pedir el arrendamiento | Arrendamiento exclusivo (§8.1) |
| Dos anexados | Se serializan | Los dos piden la cola del archivo |
| Escritor que muere | Su arrendamiento caduca en 30 s como máximo y otro puede escribir | La caducidad la decide solo el servidor |
| `rm` mientras alguien escribe | `rm` recibe `LOCK_CONFLICT` | No se borra un archivo con un escritor activo |
| `rm` o `mv` mientras alguien lee | El lector sigue leyendo su versión | El descriptor apunta al `file_id` y la versión se conserva 10 min |

## 7.5 Por qué apertura-cierre

**Tabla 25.** Alternativas de modelo de consistencia.

| Modelo | Ventaja | Inconveniente |
|---|---|---|
| Linealizable a nivel de byte | Cada `read()` ve la última escritura de cualquier cliente | Obliga a consultar al servidor de metadatos en cada lectura, que pasa a ser el cuello de botella, y a invalidar cachés |
| Eventual | Lecturas siempre locales y rápidas | Los lectores pueden ver versiones antiguas sin límite de tiempo; es difícil de comprobar y no responde a §7 |
| **Apertura-cierre** (elegida) | Las cuatro garantías se pueden comprobar; las lecturas no consultan los metadatos en cada `read()` | Un cliente no ve lo que escribe otro hasta que este cierra y él vuelve a abrir |

El inconveniente es aceptable para un sistema de archivos: es el mismo contrato que ofrecen AFS y NFS [29], y las aplicaciones que necesitan ver los cambios de otro proceso tienen que coordinarse con él igualmente, con `lock()`.

# 8. Concurrencia, integridad y recuperación de escrituras interrumpidas

## 8.1 Exclusión mutua: arrendamientos por rango de bloques

§7 del enunciado permite que `lock()` sea una primitiva explícita o un mecanismo equivalente, siempre que se documente su semántica. Además avisa de que la integridad (hashes, validaciones, escrituras atómicas) no sustituye la coordinación de escrituras concurrentes [1]. HDFS 1.2.1 admite un solo escritor por archivo [4], pero RNF5 pide concurrencia también dentro de un archivo. La Tabla 26 compara las opciones.

**Tabla 26.** Alternativas de exclusión mutua.

| Alternativa | Ventaja | Inconveniente |
|---|---|---|
| Sin cerrojos, solo control optimista al confirmar | Sin estado de cerrojos | El proceso que pierde se entera al final, después de enviar todos sus bloques |
| Cerrojo exclusivo por archivo | Simple | Serializa a escritores que tocan bloques distintos (RNF5) |
| Cerrojo sin caducidad | — | Si el cliente muere, el cerrojo queda huérfano para siempre |
| **Arrendamiento exclusivo por rango de bloques, más comprobación de versión al confirmar** (elegida) | Concurrencia entre rangos distintos; ningún cerrojo queda huérfano | Hay que renovarlo; los anexados se serializan |

**Decisión.** Un **arrendamiento** es un cerrojo con caducidad automática [30]:
- `lock(h, rango)` concede un arrendamiento **exclusivo de escritura** sobre un rango de bloques, con un TTL de 30 s renovable con `UpdateLease`.
- Lo gestiona el servidor de metadatos y su estado se replica con Raft. **La caducidad la decide solo el servidor**, así que los relojes de los clientes no influyen.
- El rango se pide **en una sola petición** y se concede entero o nada. Nadie espera teniendo ya una parte, así que **no puede haber interbloqueos**.
- Si el rango choca con otro arrendamiento, la respuesta es inmediata: `ABORTED` + `LOCK_CONFLICT`. El cliente decide si reintenta con espera.
- `write()` sin arrendamiento previo lo pide de forma implícita. El `lock()` explícito sirve para agrupar varias escrituras. `unlock()` y `close()` lo liberan.
- **Las lecturas no toman cerrojo.** No hay cerrojos compartidos, porque la consistencia de apertura-cierre ya protege a los lectores (§7.3).

**Límite.** Un escritor lento tiene que renovar el arrendamiento cada pocos segundos, y cada renovación es una entrada del log replicado. El TTL de 30 s se ajusta con el experimento E4.

## 8.2 Comprobación de versión al confirmar

El arrendamiento coordina a los escritores **mientras** escriben. La comprobación al confirmar cubre lo que el arrendamiento no puede cubrir. `CommitFile` solo se acepta si se cumplen dos condiciones:
1. **El arrendamiento sigue vigente.** Si caducó, la confirmación se rechaza con `LEASE_EXPIRED`, aunque el cliente reaparezca con todos sus bloques escritos. Así un escritor que estuvo parado más de 30 s no pisa al que vino después.
2. **El rango no ha cambiado desde la versión base.** Cada índice del rango conserva el `block_id` que tenía en la versión de la que partió el escritor. Si otro escritor confirmó un cambio en esos índices entre el `open()` y el arrendamiento, la confirmación se rechaza con `VERSION_CONFLICT`.

Si las dos se cumplen, los bloques del rango se aplican **sobre la versión vigente**, no sobre la base. Así, dos escritores de rangos distintos que confirman uno detrás de otro conservan los dos cambios.

## 8.3 Integridad

La integridad se comprueba en cuatro puntos con SHA-256 [31] y con la etiqueta de AES-GCM [32]:
- **Al escribir:** cada réplica verifica el `block_sha256` que envió el cliente antes de confirmar el bloque (§8.4).
- **Al leer, en el nodo de datos:** el nodo recalcula el hash mientras envía el bloque y cierra la llamada con `DATA_LOSS` si no coincide.
- **Al leer, en el cliente:** el cliente compara el hash con el que guarda el servidor de metadatos y descifra con AES-GCM, que falla si un solo bit del bloque ha cambiado.
- **En segundo plano:** el verificador de bloques recorre todos los bloques una vez al día (§8.5).

Un hash prueba la integridad, no la autoría: dice que el contenido no cambió, pero no quién lo creó [12]. La autoría la aportan la autenticación y el TLS mutuo (§10). Tampoco coordina las escrituras: eso lo hacen los arrendamientos.

## 8.4 Confirmación atómica y escrituras interrumpidas

Una escritura puede interrumpirse en cualquier punto: el cliente muere, un nodo de datos cae a mitad de un bloque, la red se corta. Ningún lector debe ver nunca un archivo a medias (G4). La Tabla 27 compara las opciones.

**Tabla 27.** Alternativas para confirmar escrituras.

| Alternativa | Ventaja | Inconveniente |
|---|---|---|
| Hacer visible cada bloque al escribirlo | Simple | El archivo es visible mientras se escribe: un lector puede ver un archivo a medias |
| Área temporal en el cliente hasta tener el archivo entero (HDFS 1.2.1) | El servidor solo ve archivos completos | La guía de HDFS advierte que el archivo se pierde si algo cae antes de cerrarlo, y ocupa disco en el cliente [4] |
| **Dos fases: bloques en el área temporal de los nodos de datos y confirmación atómica en los metadatos** (elegida) | Un único punto de visibilidad | Los bloques de escrituras abortadas ocupan disco hasta la recolección de basura |

**Decisión.** La escritura tiene dos fases, separadas por un único punto de visibilidad, al estilo de una confirmación distribuida en la que el coordinador es el log replicado [6, cap. 8]:

**Fase 1, bloques.**
1. `AllocateBlocks` registra una **escritura en curso** bajo el arrendamiento y devuelve los `block_id`, las ubicaciones y los tokens.
2. Cada nodo de datos, sea la primaria o una secundaria, escribe el bloque en su **área temporal**, hace `fsync`, verifica el `block_sha256` y lo **renombra de forma atómica** al almacén de bloques. Si el hash no coincide, descarta el bloque y responde `ABORTED` + `BLOCK_CORRUPTED`.
3. Cada nodo envía `ReportBlockReceived` al servidor de metadatos, que así cuenta las réplicas sin fiarse del cliente.

**Fase 2, confirmación.**
4. `CommitFile` se acepta solo si el arrendamiento sigue vigente, el rango no ha cambiado (§8.2) y **todos** los bloques nuevos tienen al menos W = 2 avisos de bloque recibido con el hash correcto.
5. La versión nueva se confirma con **una sola entrada del log replicado**: o se aplica entera o no se aplica.

**Abortar.** Si el arrendamiento caduca o el cliente llama a `AbortFile`, la escritura en curso se descarta. Sus bloques quedan **huérfanos**: no pertenecen a ninguna versión viva, y la recolección de basura los borra (§9.3). La Figura 10 muestra los estados de una escritura.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 10 ]** · archivo: `docs/diagramas/10-estados-escritura.png` 🟥🟥

**Figura 10.** Estados de una escritura en curso.

**Un bloque a medias nunca cuenta.** Si un nodo cae mientras recibe un bloque, lo que llegó se queda en el área temporal: nunca se renombra, no genera aviso de bloque recibido y no cuenta como réplica. El cliente repite ese bloque en otros nodos (escenario 3, §11.3).

## 8.5 Réplicas corruptas y verificación periódica

Un disco puede corromper un bloque sin avisar (S2). Una réplica corrupta que nadie corrige cuenta como una de las tres sin servir para nada. Además, un bloque que nadie lee puede corromperse sin que nadie lo note, hasta que fallen también las otras réplicas. HDFS verifica sumas de comprobación en el cliente y lee de otra réplica si fallan [4]; DFSha añade la corrección y la verificación periódica.

**Al leer.**
- El nodo de datos calcula el hash mientras envía el bloque. Si no coincide, cierra con `DATA_LOSS` + `BLOCK_CORRUPTED` y avisa al servidor de metadatos con `ReportCorruptReplica`.
- El cliente, ante ese error o si falla la etiqueta GCM, descarta lo recibido y lee de otra réplica. Si falló la etiqueta y el nodo no avisó de nada, avisa él.

**Quién puede marcar una réplica como corrupta.**
- Si el aviso viene del **nodo de datos** que la guarda, la réplica queda marcada.
- Si viene de un **cliente**, no se marca nada todavía. El servidor de metadatos ordena a ese nodo que la verifique (orden `VERIFY`) y solo la marca si el nodo lo confirma. **Un cliente malicioso no puede provocar el borrado de réplicas sanas** (S5).

**Corrección**, que la Figura 11 muestra completa:
1. La réplica marcada deja de entregarse en las ubicaciones.
2. Se re-replica desde una réplica sana, con la misma prioridad que un bloque con una sola réplica.
3. Cuando la réplica nueva está confirmada con su aviso de bloque recibido, se ordena borrar la corrupta.
4. **Nunca se borra la última réplica de un bloque**, aunque esté corrupta. Si todas lo están, el bloque se da por perdido: las lecturas devuelven `DATA_LOSS` + `BLOCK_LOST` y queda registrado.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 11 ]** · archivo: `docs/diagramas/11-replica-corrupta.png` 🟥🟥

**Figura 11.** Detección y corrección de una réplica corrupta.

**Verificación periódica.** El verificador de bloques de cada nodo de datos recalcula el hash de todos sus bloques una vez al día, leyendo a 4 MB/s como máximo para no competir con el tráfico normal. A ese ritmo, un volumen lleno de 10 GiB se recorre en unos 45 min. Una discrepancia se trata igual que si el nodo la detectara al leer.

**Límite.** Entre dos pasadas puede pasar hasta un día sin detectar un bloque corrupto que nadie lee. Con R = 3, el bloque solo se pierde si las tres réplicas se corrompen antes de corregirse. El coste del hash en cada lectura (decenas de milisegundos por bloque de 16 MiB en una t3, estimación sin medir) se mide con el experimento E8.

## 8.6 Reintentos e idempotencia

Que venza un plazo no dice si la operación se ejecutó: pudo perderse la petición, retrasarse el servidor o perderse la respuesta [33]. Reintentar algo que tiene efectos puede duplicarlo, y un identificador solo evita duplicados si el servidor recuerda los que ya procesó [12]. *Exactamente una vez* no es alcanzable en general; la solución práctica es *al menos una vez* con operaciones idempotentes [6, cap. 8], [15].

**Decisión.** Semántica *al menos una vez* con operaciones idempotentes (Tabla 28).

**Tabla 28.** Semántica de reintento de cada tipo de operación.

| Tipo de operación | Cómo se hace idempotente | Qué devuelve un duplicado |
|---|---|---|
| Escritura de un bloque (`WriteBlock`) | Por `block_id`: el mismo `block_id` con el mismo hash no se vuelve a escribir; con otro hash se rechaza | OK |
| Mutaciones de metadatos (`mkdir`, `rm`, `mv`, `LockBlocks`, `AllocateBlocks`, `CommitFile`…) | Llevan un `request_id`, un UUID que genera el cliente [21]. El servidor guarda el `request_id` y su respuesta en el estado replicado durante 10 min | La respuesta guardada |
| Lecturas (`OpenFile`, `GetBlockLocations`, `ReadBlock`, `ls`) | Son idempotentes por naturaleza | El mismo resultado |
| Avisos de los nodos de datos | Por `block_id` y `node_id`: el estado final es el mismo | OK |

- **La respuesta se envía después de aplicar el efecto**, cuando la mayoría lo ha confirmado. Si el cliente recibe OK, el efecto es definitivo.
- **Reintentos** con espera exponencial, un número máximo de intentos y un plazo en cada llamada. Los valores van en la configuración.
- **Límite.** Un duplicado que llegue después de los 10 min no se detecta. Por eso el cliente no reintenta más allá de ese tiempo. El registro de `request_id` ocupa memoria acotada por el TTL.

# 9. Tolerancia a fallos y disponibilidad

## 9.1 Modelo de fallos

Los fallos de un sistema distribuido son **parciales**: unos componentes fallan mientras otros siguen funcionando [5]. Por eso cada fallo se analiza por separado: qué falla, qué sigue funcionando y qué observa el cliente. DFSha supone fallos por parada de los nodos (S1), corrupción silenciosa de discos (S2) y pérdidas, retrasos y duplicados en la red (S3). No tolera fallos bizantinos (L2). La Tabla 29 resume qué ocurre con cada fallo.

**Tabla 29.** Efecto de cada fallo y cómo se recupera el sistema.

| Fallo | Lecturas | Escrituras | Recuperación | Tiempo |
|---|---|---|---|---|
| Un nodo de datos | Siguen: el cliente lee de otra réplica | Siguen: W = 2 de 3 | Re-replicación de sus bloques a otros nodos | Detección en 30 s; la re-replicación depende del volumen de datos (E6) |
| Dos nodos de datos a la vez | Siguen si queda una réplica de cada bloque | Siguen con los 3 nodos restantes | Re-replicación; primero los bloques con una sola réplica | Ídem |
| La réplica primaria a mitad de un bloque | — | El bloque se repite con otra asignación | El área temporal a medias se descarta | Plazo de la llamada |
| El líder de metadatos | Las ya abiertas siguen; los `open()` esperan a la elección | Esperan a la elección y al modo seguro | Raft elige otro líder entre los dos restantes | Elección (segundos, E7) + modo seguro (3–6 s si todos los nodos de datos están vivos) |
| Dos servidores de metadatos | Solo las ya abiertas, mientras no caduquen sus tokens (10 min) | No hay | Volver a tener mayoría | Lo que tarde en volver un servidor |
| El volumen EBS de un servidor de metadatos | Siguen: quedan dos servidores | Siguen | Volumen nuevo, al que el líder envía una instantánea | Lo que tarde en copiarse la instantánea |
| Los tres servidores de metadatos con sus volúmenes | No hay | No hay | Restaurar la última copia de seguridad de S3 | Manual; se pierde lo posterior a la copia (L11) |
| El cliente a mitad de una escritura | — | La escritura en curso no se confirma | El arrendamiento caduca a los 30 s; los bloques quedan huérfanos | 30 s |
| Una réplica corrupta | El cliente lee de otra réplica | No afecta | Re-replicación desde una sana y borrado de la corrupta | Al detectarla (lectura o verificación diaria) |
| Partición de red que aísla a un servidor de metadatos | Sin cambios en el lado mayoritario | Sin cambios en el lado mayoritario | El aislado deja de ser líder y no acepta escrituras: sin cerebro dividido | Elección |
| Todo el clúster (fin de sesión del lab) | No hay hasta el rearranque | No hay hasta el rearranque | Arranque en frío con modo seguro (§9.6) | Arranque de las instancias + modo seguro (≤ 60 s) |

## 9.2 Detección de fallos

Cada nodo de datos envía un **latido** al líder de metadatos cada 3 s, con su espacio libre. La Figura 12 muestra los estados por los que pasa un nodo:
- **Vivo:** ha enviado un latido en los últimos 9 s.
- **Sospechoso**, tras 9 s sin latido: deja de recibir escrituras nuevas, pero sus réplicas siguen en las ubicaciones.
- **Caído**, a los 30 s: se quita de las ubicaciones y se re-replican sus bloques.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 12 ]** · archivo: `docs/diagramas/12-estados-nodo.png` 🟥🟥

**Figura 12.** Estados de un nodo de datos según sus latidos.

**Por qué estos umbrales.** Con los valores por defecto, HDFS tarda unos 10,5 min en dar por muerto un DataNode (2 × 5 min de comprobación + 10 × 3 s de latido) y durante ese tiempo lo sigue mostrando como vivo [18]. Eso es demasiado para un sistema de alta disponibilidad, y también para un vídeo de 10–15 minutos. Unos umbrales muy agresivos, como un latido cada segundo y caído a los 5 s, dan falsos positivos cuando la red va lenta. Los valores intermedios detectan en 30 s, y un falso positivo es inofensivo: crea réplicas de más, que se borran después, porque los bloques son inmutables. El experimento E6 los ajusta.

**Órdenes en la respuesta.** El servidor de metadatos nunca llama a un nodo de datos: le envía las órdenes en la respuesta a su latido, como en HDFS [4]. Si una orden se pierde, se vuelve a calcular en el siguiente latido.

## 9.3 Re-replicación, resincronización y recolección de basura

- **Re-replicación.** Cuando un bloque tiene menos de R réplicas, el servidor elige una réplica viva como origen y un destino según la política de ubicación (§4.3). En la respuesta al latido del origen le envía una orden `REPLICATE` con un token de escritura para el destino. El origen copia el bloque al destino por TLS mutuo, y el destino envía su aviso de bloque recibido. Primero se re-replican los bloques que solo tienen una réplica.
- **Resincronización.** Un nodo que vuelve se da de alta otra vez y envía su informe de bloques. Sus bloques son inmutables, así que siguen siendo válidos si su hash coincide. Si el bloque ya tiene R réplicas en otros nodos, la réplica de más se borra.
- **Recolección de basura.** El informe de bloques de cada nodo, al darse de alta y cada 5 min, se compara con los metadatos. Los bloques que no pertenecen a ninguna versión viva ni a una escritura en curso, incluidos los de versiones sustituidas hace más de 10 min, se borran con una orden `DELETE` en la respuesta al latido.

## 9.4 Fallo de los servidores de metadatos

Con Raft, los tres servidores de metadatos tienen el mismo log. Si cae el líder, los otros dos dejan de recibir sus mensajes y, pasado un tiempo de elección aleatorio, uno de ellos se presenta como candidato y gana con la mayoría (2 de 3) [2]. Ninguna escritura confirmada se pierde, porque solo se confirmó lo que ya estaba en el log de la mayoría.

Mientras no hay líder no hay servicio de metadatos. El cliente recibe `UNAVAILABLE`, reintenta con espera y, cuando hay líder nuevo, el seguidor al que pregunte le indica cuál es. Los lectores que ya tenían el archivo abierto no lo notan: tienen las ubicaciones y los tokens.

**Límite (L3).** Con dos servidores de metadatos caídos no hay mayoría, así que no hay líder ni operaciones de metadatos. Es el precio de no tener cerebro dividido: el servidor que queda no puede saber si los otros dos siguen funcionando aislados.

## 9.5 Modo seguro tras cada elección de líder

El estado de vida de cada nodo de datos depende de cuándo llegó su último latido, y ese dato solo lo tiene el líder en memoria: no está en el log replicado. Un líder recién elegido todavía no ha recibido ningún latido. Si aplicara los umbrales de la §9.2 sin más, a los 30 s declararía caídos a los nodos que aún no le han hablado, quitaría sus ubicaciones y lanzaría una re-replicación masiva sin motivo. Pasa tras cada caída del líder y, sobre todo, en el arranque en frío (§9.6). HDFS tiene el mismo problema y lo resuelve con su *Safemode*: no re-replica hasta que una fracción de los bloques está informada [4]. DFSha hace lo mismo con dos diferencias (Figura 13):
- La condición de salida usa **los latidos**, no los informes de bloques, porque las ubicaciones ya están en el log replicado.
- Hay un **tope de tiempo**, para que el sistema no quede en solo lectura para siempre si se perdió algún bloque.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 13 ]** · archivo: `docs/diagramas/13-modo-seguro.png` 🟥🟥

**Figura 13.** Modo seguro del líder de metadatos.

**Entrada.** Cada vez que un servidor de metadatos pasa a ser líder.

**Mientras dura:**
- Los plazos de sospechoso y caído cuentan desde la elección, así que no se declara caído a ningún nodo.
- No hay re-replicación, ni recolección de basura, ni borrado de réplicas de más: un líder que todavía no sabe qué nodos están vivos no borra nada.
- Las **lecturas** se atienden.
- Las **operaciones del cliente que cambian metadatos** se rechazan con `UNAVAILABLE` + `SAFE_MODE_ACTIVE`, y el cliente las reintenta: `AllocateBlocks`, `CommitFile`, `mkdir`, `mv`, `rm` y también conceder o renovar arrendamientos.
- Los **mensajes de los nodos de datos** se atienden, porque son los que permiten salir.
- Los **arrendamientos no caducan.** Al salir, cada arrendamiento vigente vuelve a tener su TTL completo, para que una escritura interrumpida por el cambio de líder todavía pueda confirmarse.

**Salida**, en cuanto se cumpla una de estas condiciones:
- cada bloque de cada versión viva tiene al menos una réplica en un nodo que ha enviado un latido desde la elección;
- se alcanza el tope `safe_mode_max_wait_s` (60 s por defecto). En ese caso sale igualmente y registra un aviso con los bloques sin ninguna réplica viva: esos bloques están perdidos, y esperar no los recupera.

**Efecto.** En un cambio de líder con todos los nodos de datos vivos, el modo seguro termina en uno o dos latidos (3–6 s). Después, un nodo que no ha enviado ningún latido desde la elección se declara caído a los 30 s de la elección, y sus bloques se re-replican con normalidad.

**Límite.** Las escrituras esperan a que termine el modo seguro, y esa espera se suma a la elección. Como cada arrendamiento recupera su TTL completo, un cliente muerto conserva el suyo hasta 30 s más.

## 9.6 Arranque en frío

Al acabar cada sesión del Learner Lab, el laboratorio para las instancias y en la siguiente sesión las arranca todas a la vez [8]. Es una caída y un rearranque de todo el clúster, y el diseño la trata como un escenario más:
- **Docker** está activado al arrancar el sistema, y los contenedores tienen la política de reinicio `always`, así que vuelven solos [19].
- **Los volúmenes EBS** de los servidores de metadatos y de los nodos de datos se montan por UUID con `nofail`, y ningún servidor arranca si el suyo no está montado. Si el volumen no se monta y nadie lo comprueba, el punto de montaje es un directorio vacío del disco raíz y el nodo escribe allí sin ningún error.
- **Los nombres no cambian**, porque la IP privada se conserva (§3.6).
- **Raft** elige líder en cuanto hay dos servidores de metadatos en marcha, y el líder entra en modo seguro hasta que los nodos de datos envían sus latidos.

El experimento E9 mide este escenario (§12.2).

## 9.7 Disponibilidad: resumen

- **Datos (RNF2).** Con R = 3 y cinco nodos de datos, cualquier bloque sobrevive a la caída simultánea de dos nodos, y tras la re-replicación vuelve a tolerar otras dos.
- **Localización.** Replicar los bloques no basta si nadie sabe dónde están [12]. Con tres servidores de metadatos, la localización sobrevive a la caída de uno.
- **Escrituras.** Necesitan un líder de metadatos y dos nodos de datos vivos.
- **Lecturas.** Necesitan un líder para abrir el archivo y una réplica viva de cada bloque.
- **Lo que no se tolera:** la caída de la zona de disponibilidad completa (L1) y la caída de dos servidores de metadatos a la vez (L3).

# 10. Seguridad

RNF6 pide cifrado en tránsito y en reposo, autenticación, autorización y protección de las comunicaciones entre nodos. La Figura 14 resume dónde actúa cada mecanismo.

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 14 ]** · archivo: `docs/diagramas/14-seguridad.png` 🟥🟥

**Figura 14.** Mecanismos de seguridad: TLS, TLS mutuo, tokens y cifrado de sobre.

## 10.1 Modelo de amenazas

**Tabla 30.** Amenazas consideradas y mecanismo que las cubre.

| Amenaza | Mecanismo | Lo que no cubre |
|---|---|---|
| Escucha o alteración del tráfico en la red | TLS en todas las conexiones (§10.4) | — |
| Un proceso de la VPC se hace pasar por un nodo | TLS mutuo con certificados de una CA interna; grupos de seguridad | Que alguien robe la clave privada de un nodo |
| Un usuario lee o modifica archivos de otro | Espacio de nombres por usuario y comprobación del propietario en cada RPC (§10.3) | — |
| Un cliente accede a un nodo de datos sin permiso | Token de bloque firmado, ligado a un bloque, a una operación y a una caducidad de 10 min | Un token robado vale hasta que caduca |
| Un cliente malicioso intenta hacer borrar réplicas sanas | Solo el nodo de datos puede confirmar que una réplica está corrupta (§8.5) | — |
| Robo del disco de un nodo de datos o de una instantánea de EBS | Los bloques están cifrados por el cliente; además, cifrado del volumen EBS (§10.5) | — |
| Robo del volumen de un servidor de metadatos o de una copia de seguridad de S3 | Solo contienen hashes de contraseñas y claves de datos envueltas; la clave de envoltura nunca está en ellos (§10.7); además, volumen cifrado y bucket privado y cifrado | Los nombres y tamaños de los archivos van en claro (L8) |
| Un nodo de datos comprometido | Solo ve texto cifrado. Si sirve datos alterados, lo detectan el hash y GCM | Comparte la clave de firma de los tokens de bloque: podría emitir tokens válidos, aunque solo daría acceso a bloques cifrados |
| Un servidor de metadatos comprometido | — | Tiene la clave de envoltura y puede descifrarlo todo (L7) |
| Repetición de una petición capturada | TLS impide capturarla; los tokens caducan; las mutaciones son idempotentes | — |
| Fuerza bruta contra contraseñas | scrypt con sal por usuario | No se limitan los intentos fallidos; se decidirá en la fase II |

## 10.2 Autenticación

**Usuarios.**
- Los da de alta un administrador con `CreateUser`; no hay autorregistro. El primer administrador lo crea el script de despliegue a partir de un secreto que no se versiona.
- La contraseña se guarda con scrypt [34] y una sal por usuario. Nunca se guarda en claro.
- `Authenticate` devuelve un **token de acceso** firmado con HMAC-SHA256 [35], que contiene el `user_id` y caduca en 1 h. Cualquier servidor de metadatos puede verificarlo, porque comparten la clave de firma.

**Nodos.** Se autentican con el certificado de su rol, por TLS mutuo (§10.4).

## 10.3 Autorización

**En el servidor de metadatos.** Cada RPC comprueba el token de acceso y que la ruta pertenece al espacio de nombres del usuario. Como cada usuario tiene su propia raíz `/`, las rutas de otro usuario no existen para él. Los descriptores de archivo están firmados por el servidor, así que el cliente no puede fabricar uno para un archivo ajeno.

**En los nodos de datos: el token de bloque.** Si los nodos de datos consultaran al servidor de metadatos en cada acceso, este se convertiría en el cuello de botella. Si no comprobaran nada, cualquiera que conociera un `block_id` podría leerlo. Por eso, junto con las ubicaciones, el servidor de metadatos entrega un **token de bloque**:
- contiene el `block_id`, la operación (`read` o `write`) y una caducidad de 10 min;
- está firmado con HMAC-SHA256, con una clave que comparten los servidores de metadatos y los nodos de datos;
- el nodo de datos verifica la firma y la caducidad sin consultar a nadie, con el margen de reloj de la §10.6.

**Entre nodos.** Las órdenes de re-replicación y el reenvío de la primaria a las secundarias se autentican con TLS mutuo. Además, cada RPC interno comprueba que el certificado es de un rol autorizado para esa llamada: un cliente no puede llamar a `ReportBlockReceived`.

**Límite.** Un token solo se revoca cuando caduca: 1 h el de acceso y 10 min el de bloque.

## 10.4 Cifrado en tránsito

**Tabla 31.** Alternativas de cifrado en tránsito.

| Alternativa | Ventaja | Inconveniente |
|---|---|---|
| Sin TLS dentro de la VPC | Ningún coste | Incumple RNF6. El laboratorio de gRPC del curso usa `add_insecure_port` [26] |
| TLS solo de servidor en todas las conexiones | Canal cifrado | Los nodos no se autentican entre sí: cualquier proceso de la VPC podría hacerse pasar por un nodo de datos |
| **TLS mutuo entre nodos; TLS de servidor más token para el cliente** (elegida) | Canal cifrado y nodos autenticados | La clave de la CA es el secreto más sensible; la rotación de certificados es manual |

**Decisión.**
- Todas las conexiones usan TLS 1.3 [36].
- El script de despliegue genera una **CA interna** del proyecto y un certificado por nombre de host, con `<rol>-<n>` en el campo SAN.
- En los RPC internos, cada extremo exige un certificado firmado por esa CA y de un rol autorizado.
- El cliente verifica el certificado del servidor con la CA y se autentica con su token.
- Los grupos de seguridad solo abren los puertos del clúster entre los grupos del proyecto (§3.6).

El coste de TLS en CPU se mide con el experimento E8.

## 10.5 Cifrado en reposo

El profesor dejó a criterio del diseño elegir entre cifrar el volumen EBS o cifrar por bloque, con la condición de elegir lo que mejor se defienda desde la arquitectura, y aclaró que los metadatos no necesitan cifrado [9]. La Tabla 32 compara las opciones.

**Tabla 32.** Alternativas de cifrado en reposo.

| Alternativa | Qué protege | Qué no protege |
|---|---|---|
| Cifrado del volumen EBS | El robo del disco o de una instantánea [37] | Quien entra en el sistema operativo del nodo lee en claro; no hay ninguna decisión de diseño que defender |
| Cifrado en el nodo de datos con una clave por nodo | El disco | El nodo y la red interna ven el texto en claro; re-replicar obliga a descifrar y volver a cifrar |
| **Cifrado de sobre en el cliente** (elegida) | El disco, el nodo de datos y la red interna: ninguno ve nunca el texto en claro | Quien comprometa un servidor de metadatos tiene la clave de envoltura |

**Decisión: cifrado de sobre.** Los datos se cifran con una clave de datos, y esa clave se guarda cifrada con otra, la clave de envoltura [38]:
- **Claves.** Al crear un archivo, el servidor de metadatos genera una **clave de datos** aleatoria de 256 bits y la guarda envuelta con la **clave de envoltura**, que solo tienen los servidores de metadatos. En `open()` se la entrega al propietario autenticado, por TLS.
- **Cifrado de cada bloque.** El cliente cifra con AES-256-GCM [32], con un nonce aleatorio de 96 bits por bloque y el `block_id` como dato asociado, para que no se puedan intercambiar bloques entre posiciones. El bloque guardado es *nonce ‖ texto cifrado ‖ etiqueta*, 28 bytes más que el bloque en claro.
- **Integridad.** El `block_sha256` se calcula sobre el bloque cifrado y es lo que verifican los nodos de datos. La etiqueta GCM verifica el bloque de extremo a extremo en el cliente.
- **Nonces.** Como los bloques son inmutables, una modificación crea un bloque nuevo con un nonce nuevo: nunca se reutiliza un nonce con la misma clave.
- **Defensa en profundidad.** Además, el volumen EBS de cada nodo de datos y de cada servidor de metadatos se cifra con la clave gestionada `aws/ebs`. Se comprobó en el Learner Lab el 23 de octubre de 2026 con un volumen de prueba, que quedó disponible y cifrado.

**Se gana:**
- Ni los nodos de datos, ni sus discos, ni la red interna ven nunca el texto en claro.
- La re-replicación copia texto cifrado sin necesitar claves.
- La evidencia es sencilla: un volcado de un bloque en el disco es ilegible.

**Límites (L7, L8).** La clave de envoltura es un punto crítico: quien comprometa un servidor de metadatos puede descifrarlo todo. Los nombres y los tamaños de los archivos quedan en claro en los servidores de metadatos, como permite el profesor. La rotación de la clave de envoltura queda fuera de alcance.

## 10.6 Sincronización de relojes

Varios mecanismos comparan instantes fijados por un nodo con el reloj de otro. El token de bloque lo firma el líder de metadatos y comprueba su caducidad el nodo de datos. El token de acceso lo emite un servidor de metadatos, pero tras un cambio de líder lo comprueba otro. Los certificados se comprueban con el reloj de cada nodo. Si los relojes se separan, se rechazan tokens válidos o se aceptan tokens caducados. La sincronización de relojes físicos es un problema clásico de los sistemas distribuidos [6, cap. 5].

**Decisión.**
- El script de despliegue configura **chrony** en todas las instancias con el servicio de hora de Amazon, en su dirección local de la VPC [7], y comprueba que el reloj sincroniza. Si no sincroniza, el despliegue falla.
- Las comprobaciones de caducidad admiten un margen de 30 s, muy pequeño frente a la vida de los tokens (10 min y 1 h) y muy grande frente al desfase normal de chrony, que es de milisegundos.

**No dependen de los relojes:**
- Los arrendamientos: los gestiona solo el líder y tras una elección recuperan su TTL completo (§9.5).
- Raft, que usa plazos relativos [2].

**Límite.** Un token caducado se acepta hasta 30 s después de caducar.

## 10.7 Gestión de secretos

Ningún secreto se versiona en el repositorio. Los secretos del despliegue son:
- la clave privada de la CA y las de cada nodo;
- la clave de firma de los tokens de acceso, que comparten los servidores de metadatos;
- la clave de firma de los tokens de bloque, que comparten los servidores de metadatos y los nodos de datos;
- la clave de envoltura, que nunca se escribe en el volumen de metadatos ni en la copia de seguridad;
- la contraseña del primer administrador.

El script de despliegue los genera y los copia a cada instancia, que los monta en el contenedor desde fuera de la imagen. Ningún componente usa credenciales de AWS mientras funciona: solo el script de despliegue, con las de la sesión del lab.

**Copias de seguridad de los metadatos.** Contienen los hashes de las contraseñas y las claves de datos envueltas, nunca en claro. Se guardan en un bucket privado de S3, cifrado (§4.2).

**Separación de la clave de envoltura.** El volumen de metadatos y la copia de seguridad contienen las claves de datos envueltas. Si la clave de envoltura estuviera junto a ellas, quien robara cualquiera de los dos podría descifrar todos los archivos. Por eso se monta en el contenedor como secreto desde el disco raíz de cada servidor de metadatos y nunca se escribe en su volumen ni en la copia. El administrador la guarda fuera del clúster y fuera del repositorio. El script la vuelve a copiar si se sustituye una instancia, y hace falta para restaurar una copia. Si se perdiera, ningún archivo se podría descifrar, así que su custodia es tan crítica como la de la clave de la CA.

# 11. Escenarios obligatorios de razonamiento

Cada escenario de §4.2 del enunciado se analiza como un fallo o un conflicto parcial: qué ocurre paso a paso, por qué, qué observa el cliente y qué límite tiene la respuesta.

## 11.1 Escenario 1: dos procesos escriben el mismo bloque a la vez

**Situación.** Los procesos P1 y P2 abren `/datos.bin` y quieren modificar el bloque 3 a la vez (Figura 15).

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 15 ]** · archivo: `docs/diagramas/15-escenario-concurrencia.png` 🟥🟥

**Figura 15.** Escenario 1: dos procesos escriben el mismo bloque a la vez.

**Qué sucede.**
1. P1 pide el arrendamiento del bloque 3 (`LockBlocks`) y lo obtiene, con un TTL de 30 s.
2. P2 pide un rango que incluye el bloque 3 y recibe al momento `ABORTED` + `LOCK_CONFLICT`. No se queda esperando: decide si reintenta más tarde.
3. P1 escribe un bloque nuevo para el índice 3 (copia en escritura) y confirma en `close()`. La versión pasa de *v* a *v + 1*, y su arrendamiento se libera.
4. P2 reintenta, obtiene el arrendamiento y la respuesta le indica que la versión actual es *v + 1*. Como abrió la versión *v*, tiene que volver a abrir y leer el bloque 3 de *v + 1* antes de aplicar su cambio. Si confirmara a partir de *v*, recibiría `VERSION_CONFLICT`.

**Variantes.**
- **P1 muere con el arrendamiento.** Caduca en 30 s como máximo, y P2 puede escribir. Si P1 reaparece y trata de confirmar, recibe `LEASE_EXPIRED`: su escritura en curso se descarta y sus bloques quedan huérfanos.
- **P1 y P2 escriben bloques distintos del mismo archivo.** Sus rangos no se solapan, así que los dos obtienen su arrendamiento, escriben a la vez y confirman los dos. La segunda confirmación se aplica sobre la primera (§8.2).

**Por qué.** El arrendamiento coordina a los escritores mientras escriben, y la comprobación de versión al confirmar cubre lo que pasó antes de obtenerlo. El hash del bloque no habría resuelto nada: dos escrituras íntegras pueden seguir pisándose [1].

**Qué observa el cliente.** Una de las dos escrituras gana. La otra recibe un error explícito y nunca queda una mezcla de las dos.

**Límite.** Los anexados concurrentes se serializan, porque los dos piden la cola del archivo.

## 11.2 Escenario 2: una réplica está desconectada durante una escritura

**Situación.** Se escribe un bloque asignado a `datanode-2` (primaria), `datanode-4` y `datanode-5`, y `datanode-5` está desconectado (Figura 16).

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 16 ]** · archivo: `docs/diagramas/16-escenario-replica.png` 🟥🟥

**Figura 16.** Escenario 2: una réplica está desconectada durante una escritura.

**Qué sucede.**
1. La primaria guarda el bloque y lo reenvía en paralelo a `datanode-4` y a `datanode-5`.
2. `datanode-4` lo guarda y avisa al servidor de metadatos. `datanode-5` no responde.
3. Con dos réplicas verificadas, la primaria responde OK: se alcanza W = 2. La escritura no espera a que se detecte la caída.
4. `CommitFile` comprueba que el bloque tiene dos avisos de bloque recibido y confirma la versión nueva. **Las ubicaciones de la versión nueva solo incluyen las réplicas que avisaron:** `datanode-2` y `datanode-4`.
5. A los 30 s sin latido, `datanode-5` se declara caído y el bloque, que tiene dos réplicas, se re-replica a otro nodo vivo.
6. Si `datanode-5` vuelve, envía su informe de bloques. Los bloques que tiene de versiones anteriores siguen siendo válidos, porque son inmutables. Si alguno sobra porque ya se re-replicó, se borra.

**Qué observan los lectores.**
- Un `open()` posterior a la confirmación ve la versión nueva (G2), con las ubicaciones de `datanode-2` y `datanode-4`. Ningún lector intenta leer la versión nueva de la réplica desconectada, porque no figura en sus ubicaciones.
- Un lector que tenía abierta la versión anterior sigue leyéndola (G3). Si sus bloques estaban en `datanode-5`, pasa a otra réplica de la versión anterior.
- No hay réplicas *distintas* de un mismo bloque: el de `datanode-5` existe con el contenido correcto o no existe.

**Por qué.** La consistencia se formula por lo que puede observar un lector, no por lo que tiene cada disco [15]. Como la versión nueva solo anuncia réplicas verificadas, la réplica atrasada nunca se lee.

**Límite.** Hasta que termina la re-replicación, el bloque tiene dos réplicas, y una segunda caída en ese intervalo lo deja con una. Si fallan dos de las tres réplicas durante la escritura, no se alcanza W: la primaria responde `QUORUM_NOT_REACHED` y el cliente vuelve a reservar el bloque en otros nodos.

## 11.3 Escenario 3: un nodo falla después de recibir parte de un bloque

**Situación.** La primaria `datanode-2` cae después de recibir 9 de los 16 MiB de un bloque (Figura 17).

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 17 ]** · archivo: `docs/diagramas/17-escenario-fallo-parcial.png` 🟥🟥

**Figura 17.** Escenario 3: un nodo falla después de recibir parte de un bloque.

**Qué sucede.**
1. Los 9 MiB recibidos están en el **área temporal** de `datanode-2`. Nunca se renombran al almacén de bloques, porque el bloque no se completó ni se verificó su hash. Por tanto, no generan aviso de bloque recibido.
2. El cliente recibe `UNAVAILABLE` o agota el plazo de `WriteBlock`. Como no sabe si alguna réplica llegó a guardarlo, no confirma nada.
3. El cliente vuelve a llamar a `AllocateBlocks` para ese índice. Recibe un `block_id` nuevo y otros tres nodos de datos, y envía el bloque otra vez. El `block_id` anterior queda huérfano.
4. `CommitFile` solo se acepta cuando **todos** los bloques nuevos tienen W = 2 avisos. Hasta entonces, el archivo sigue en su versión anterior para todos los lectores.
5. Cuando `datanode-2` vuelve, descarta su área temporal al arrancar. La recolección de basura borra el bloque huérfano allí donde haya llegado a guardarse.

**Variante.** Si el cliente es el que muere a mitad de la carga, no llega a llamar a `CommitFile`: su arrendamiento caduca a los 30 s, la escritura en curso se descarta y sus bloques quedan huérfanos.

**Por qué.** Hay un único punto de visibilidad: la entrada del log que confirma la versión (§8.4). Todo lo anterior es invisible por construcción.

**Qué observa el cliente.** Una carga más lenta. Los demás clientes no ven nada: ni un archivo a medias ni un error (G4).

**Límite.** Los bloques huérfanos ocupan disco hasta la recolección de basura, como máximo unos minutos tras el siguiente informe de bloques.

## 11.4 Escenario 4: el cliente desconoce la ubicación física de los bloques

**Situación.** El cliente solo se configura con `DFSHA_METADATA_ADDRS=metadata-1:50051,metadata-2:50051,metadata-3:50051` (Figura 18).

> 🟥🟥 **[ INSERTAR AQUÍ LA FIGURA 18 ]** · archivo: `docs/diagramas/18-escenario-descubrimiento.png` 🟥🟥

**Figura 18.** Escenario 4: el cliente descubre dinámicamente la ubicación de los bloques.

**Qué sucede.**
1. El cliente pregunta a cualquiera de los servidores de metadatos, por ejemplo `metadata-3`.
2. Si no es el líder, responde `UNAVAILABLE` + `NODE_NOT_LEADER`, con `leader_addr: metadata-1:50051`. El cliente repite la llamada en el líder y lo recuerda.
3. `OpenFile` y `GetBlockLocations` devuelven, para cada bloque, los **nombres** de los nodos de datos que tienen sus réplicas (`datanode-2:50052`), nunca direcciones IP.
4. El sistema operativo resuelve cada nombre con `/etc/hosts`, que genera el script de despliegue a partir de las IP privadas.
5. Si una réplica no responde, el cliente prueba otra de la lista. Si ninguna responde o los tokens caducaron, vuelve a pedir las ubicaciones.

**Por qué.** El servidor de metadatos hace de *binder* de DFSha: el cliente le pregunta dónde está el servicio y después lo llama [39]. RNF7 permite que el cliente conozca el servidor de metadatos como punto de entrada; lo importante es que **no sepa dónde están los bloques** [9].

**Qué observa el cliente.** Nada: trabaja con rutas lógicas. Añadir, quitar o sustituir nodos de datos no cambia su configuración.

**Límite.** El cliente sí necesita los nombres de los servidores de metadatos. Si se sustituye un servidor de metadatos, hay que actualizar `DFSHA_METADATA_ADDRS` y regenerar `/etc/hosts`. Es aceptable, porque son tres y cambian muy rara vez.

# 12. Métricas y experimentos

El enunciado pide definir métricas y experimentos de latencia, tasa de transferencia, concurrencia, fallos, replicación y escalabilidad, y justificar los compromisos técnicos. En la fase II se pide además medir al menos dos condiciones [1]. DFSha va más allá del mínimo: cada parámetro de diseño que se ha elegido sin medir tiene un experimento que lo sostiene o que obliga a cambiarlo.

## 12.1 Métricas

**Tabla 33.** Métricas.

| Métrica | Unidad | Cómo se mide |
|---|---|---|
| Latencia (`latency_ms`) | ms; se informa la mediana y el percentil 95 | En el cliente, desde la llamada hasta la respuesta |
| Tasa de transferencia (`throughput_mb_s`) | MB/s (megabytes por segundo) | Bytes del archivo en claro / tiempo total de `put` o `get` |
| Tasa de transferencia agregada | MB/s | Suma de las tasas de los clientes concurrentes |
| Conflictos | Número y porcentaje de operaciones | Respuestas `LOCK_CONFLICT` y `VERSION_CONFLICT` |
| Tiempo de detección | s | Desde que se para el nodo hasta que el líder lo marca caído (registro del servidor) |
| Tiempo de re-replicación | s | Desde que el nodo se marca caído hasta que todos sus bloques vuelven a tener R réplicas |
| Lecturas fallidas durante una caída | Número | Lecturas que agotan su plazo antes de pasar a otra réplica |
| Tiempo sin servicio de metadatos | s | Desde que se tumba el líder hasta que vuelve a aceptar escrituras, separando la elección del modo seguro |
| Uso de CPU | % | En cada instancia, durante el experimento |

## 12.2 Experimentos

**Tabla 34.** Experimentos previstos.

| Exp. | Variable | Métrica | Qué decisión sostiene |
|---|---|---|---|
| E1 | Tamaño del archivo: 16 MiB, 256 MiB y 1 GiB | Latencia de `put` y `get` | Línea base |
| E2 | Número de nodos de datos: 3, 4 y 5 | Tasa de transferencia de `put` y `get` | Escalabilidad (RNF1) y topología (§3.6) |
| E3 | W = 2 frente a W = 3 | Latencia de la escritura de un bloque | Confirmación por mayoría (§4.4) |
| E4 | Clientes concurrentes: 1, 2, 4 y 8, sobre archivos distintos y sobre el mismo | Tasa agregada y número de conflictos | Arrendamientos por rango y su TTL (§8.1, RNF5) |
| E5 | Tamaño de bloque: 4, 16 y 64 MiB | Tasa de transferencia y latencia de la modificación parcial | Tamaño de bloque (§4.1) |
| E6 | Caída de un nodo de datos | Tiempo de detección, tiempo de re-replicación y lecturas fallidas | Umbrales de detección (§9.2) |
| E7 | Caída del líder de metadatos | Tiempo sin servicio de metadatos, separando elección y modo seguro; escrituras rechazadas con `SAFE_MODE_ACTIVE`; latencia de las escrituras de metadatos con `fsync` | Raft (§3.3), persistencia (§4.2) y modo seguro (§9.5) |
| E8 | Con y sin cifrado en reposo y TLS | Coste en tasa de transferencia y CPU | Seguridad (§10.4, §10.5) y verificación del hash al leer (§8.5) |
| E9 | Arranque en frío: parar las 9 instancias y arrancarlas, también al terminar la sesión del lab | Tiempo hasta que los contenedores vuelven solos y hasta salir del modo seguro; si sale por la condición o por el tope; re-replicaciones y borrados lanzados, que deben ser 0 | Modo seguro y arranque en frío (§9.5, §9.6) |

## 12.3 Método

- **Repeticiones.** Al menos 5 por cada punto, informando la mediana y el percentil 95.
- **Datos.** Archivos de contenido aleatorio, para que ninguna capa comprima.
- **Dónde se mide.** Los tiempos se miden en el cliente, en `client-1`, y siempre en AWS: el entorno local no reproduce la red real.
- **Créditos de CPU.** Las instancias t3 tienen un rendimiento base con ráfagas que consumen créditos de CPU [40]. Agotarlos falsea las mediciones, así que se anota el modo de créditos de cada instancia y su saldo antes de cada serie.
- **Resultados.** Se guardan en CSV, un archivo por experimento y fecha, con todos los parámetros de la ejecución.
- **Unidades.** Las tasas se dan en MB/s y los tamaños en MiB, sin mezclar bits y bytes.

**Validez.** Con instancias pequeñas y una sola zona de disponibilidad, los números absolutos no se pueden extrapolar a producción. Lo que vale son las comparaciones entre condiciones dentro del mismo entorno.

## 12.4 Plan de validación de las pruebas mínimas

La Tabla 35 relaciona cada prueba mínima de §5.2 del enunciado con la evidencia que el diseño permite producir en la fase II.

**Tabla 35.** Pruebas mínimas del enunciado y evidencia prevista.

| Prueba (§5.2 del enunciado) | Cómo se demuestra en DFSha | Garantía o mecanismo |
|---|---|---|
| Carga y recuperación | `put` de un archivo de 1 GiB; listado de sus 64 bloques repartidos en los 5 nodos; `get` y comparación de hashes | §4.5, §6.1, §6.2 |
| Acceso RF3 | `read` en varios `offset`; `write` en los cuatro modos, con la versión resultante | §7.2 |
| Concurrencia | Dos clientes sobre el mismo bloque (uno recibe `LOCK_CONFLICT`) y sobre bloques distintos del mismo archivo (los dos confirman) | Escenario 1, §11.1 |
| Replicación y fallos | Se para un nodo de datos durante un `get`, que termina con otra réplica; se mide la re-replicación | §9.2, §9.3, E6 |
| Consistencia | Una réplica desconectada durante una escritura; los lectores ven G2 y G3 | Escenario 2, §11.2 |
| Seguridad | Acceso denegado a un archivo ajeno y con un token caducado; captura de tráfico cifrado; volcado ilegible de un bloque en disco | §10 |
| Rendimiento | E1 y E2: latencia y tasa de transferencia con al menos dos tamaños de archivo y dos números de nodos de datos | §12.2 |

# 13. Compromisos técnicos

## 13.1 Compromisos principales

Cada decisión del diseño gana algo a cambio de algo. La Tabla 36 reúne los compromisos más importantes, con lo que se acepta perder y el experimento que dirá si el precio vale la pena.

**Tabla 36.** Compromisos técnicos principales.

| Decisión | Se gana | Se acepta perder | Se valida con |
|---|---|---|---|
| Bloques inmutables con copia en escritura | Réplicas siempre idénticas o inexistentes; los cuatro modos de RF3 sin simplificar | Amplificación de escritura: cambiar un byte reescribe 16 MiB | E5 |
| Consistencia de apertura-cierre | Garantías comprobables; lecturas sin consultar los metadatos | Un cliente no ve lo que escribe otro hasta volver a abrir | Pruebas de G1–G4 |
| R = 3, W = 2, reenvío en paralelo desde la primaria | Latencia de las dos réplicas más rápidas; se escribe con un nodo caído | Un intervalo con dos réplicas; el doble de tráfico de salida en la primaria | E3 |
| Raft en tres servidores de metadatos | Sin punto único de fallo ni cerebro dividido | Un viaje hasta la mayoría por cada cambio; tres instancias; sin servicio con dos caídos | E7 |
| Arrendamientos por rango de bloques | Escritores concurrentes en zonas distintas de un archivo | Renovaciones periódicas en el log | E4 |
| Detección en 30 s | Caídas visibles en segundos | Falsos positivos con la red lenta, que solo crean réplicas de más | E6 |
| Bloques de 16 MiB | Buen reparto con archivos de 100 MiB a 1 GiB | Más peticiones por GiB que con 64 MiB | E5 |
| gRPC sin MOM | Un solo stack, contrato tipado, flujos y plazos | Sin desacoplamiento temporal, compensado con la reconciliación en cada latido | — |
| Cifrado de sobre en el cliente | Ningún nodo de datos ve el texto en claro | CPU en el cliente; la clave de envoltura es un punto crítico | E8 |
| Modo seguro tras cada elección | Sin re-replicaciones ni borrados falsos | Escrituras rechazadas unos segundos tras cada elección | E7, E9 |

## 13.2 Parámetros de diseño

Todos los parámetros son configurables. La Tabla 37 recoge sus valores iniciales, el motivo de cada uno y el experimento que lo ajusta.

**Tabla 37.** Parámetros de diseño y sus valores iniciales.

| Parámetro | Valor inicial | Motivo | Ajuste |
|---|---|---|---|
| `block_size_bytes` | 16 MiB | Granularidad para archivos de 100 MiB a 1 GiB (§4.1) | E5 |
| Tamaño de mensaje de transferencia | 1 MiB | Un bloque nunca está entero en un mensaje (§5.2) | E1 |
| `replication_factor` | 3 | Tolera dos caídas (§4.4) | — |
| `write_quorum` | 2 | Mayoría de 3 (§4.4) | E3 |
| Intervalo de latido | 3 s | Igual que HDFS (§9.2) | E6 |
| Umbral de sospechoso | 9 s | Tres latidos perdidos | E6 |
| Umbral de caído | 30 s | Caídas visibles en el vídeo; pocos falsos positivos | E6 |
| Intervalo del informe de bloques | 5 min | Recolección de basura y resincronización (§9.3) | — |
| TTL del arrendamiento | 30 s | Un escritor muerto retiene el rango poco tiempo (§8.1) | E4 |
| TTL del registro de `request_id` | 10 min | Reintentos del cliente (§8.6) | — |
| Periodo de gracia | 10 min | Lectores de versiones sustituidas (§7.3) | — |
| Vida del token de acceso | 1 h | Sesión de trabajo (§10.2) | — |
| Vida del token de bloque | 10 min | Una lectura larga (§10.3) | — |
| Margen de reloj (`clock_skew_tolerance_s`) | 30 s | Desfase residual (§10.6) | — |
| Tope del modo seguro (`safe_mode_max_wait_s`) | 60 s | No quedar en solo lectura para siempre (§9.5) | E9 |
| Periodo de la verificación periódica | 1 día | Bloques que nadie lee (§8.5) | — |
| Ritmo máximo de la verificación periódica | 4 MB/s | No competir con el tráfico normal (§8.5) | E8 |
| Copia de seguridad de los metadatos | Al final de cada sesión de trabajo | Recuperarse de la pérdida de los tres servidores o de un borrado por error (§4.2) | — |

# 14. Conclusiones y trabajo para la fase II

DFSha cumple RF1–RF3 y RNF1–RNF7 sin simplificaciones. Lo hace con tres ideas que se refuerzan entre sí:
1. **Separar el control de los datos.** Los servidores de metadatos dicen dónde están los bloques y los nodos de datos los transfieren. Así el plano de control no limita la tasa de transferencia, y el cliente no necesita saber dónde están los bloques.
2. **Hacer los bloques inmutables.** Toda escritura crea bloques nuevos y se confirma como una versión nueva con una sola entrada del log replicado. De ahí salen casi todas las garantías: réplicas que nunca divergen, lecturas sin quórum, confirmación atómica, lectores que no ven versiones a medias y re-replicación que solo copia bytes cifrados.
3. **Replicar también el plano de control.** Con Raft en tres servidores de metadatos y un modo seguro tras cada elección, ni la caída de un servidor de metadatos ni el rearranque de todo el clúster pierden escrituras confirmadas o lanzan re-replicaciones sin motivo.

El diseño declara sus límites (§1.4). Los más importantes son:
- no tolera la caída de la zona de disponibilidad ni la de dos servidores de metadatos;
- la clave de envoltura es un punto crítico;
- leer un byte transfiere un bloque entero.

**Pendiente para la fase II:**
- Elegir la implementación de Raft (etcd o PySyncObj) después de probar las dos, comprobar que escribe cada entrada en disco antes de confirmarla (§4.2) y fijar sus tiempos de elección.
- Decidir cómo llegan las imágenes a las instancias: construirlas en cada una o usar ECR, que el Learner Lab permite en lectura desde las instancias.
- Fijar las versiones exactas de las dependencias.
- Comprobar que el Learner Lab permite crear el bucket de S3, y automatizar en el script la copia de seguridad de los metadatos y su restauración (§4.2).
- Ejecutar los experimentos E1–E9 y ajustar con ellos los parámetros de la §13.2.
- Registrar en el registro de decisiones cualquier cambio respecto a este documento, para la tabla de cambios del informe final.

# Referencias

[1] Universidad Pontificia Bolivariana, «Proyecto 1 · DFSha: diseño e implementación de un sistema de archivos distribuido con alta disponibilidad, rendimiento y seguridad», enunciado del proyecto, Sistemas Distribuidos 2026-2, 2026.

[2] D. Ongaro y J. Ousterhout, «In search of an understandable consensus algorithm», en *Proc. USENIX Annual Technical Conf. (ATC)*, Philadelphia, PA, EE. UU., 2014, pp. 305–319. Versión extendida disponible en: https://raft.github.io/raft.pdf (consultado: 23 oct. 2026).

[3] S. Ghemawat, H. Gobioff y S.-T. Leung, «The Google file system», en *Proc. 19th ACM Symp. Operating Systems Principles (SOSP)*, Bolton Landing, NY, EE. UU., 2003, pp. 29–43. doi: 10.1145/945445.945450.

[4] D. Borthakur, «HDFS architecture guide», Apache Hadoop 1.2.1 Documentation, The Apache Software Foundation, 2013. [En línea]. Disponible en: https://hadoop.apache.org/docs/r1.2.1/hdfs_design.html (consultado: 23 oct. 2026).

[5] A. Ospina Sanjuan, «Introducción y conceptos», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 26 jul. 2026.

[6] M. van Steen y A. S. Tanenbaum, *Distributed Systems*, 4.ª ed. (v. 4.03). distributed-systems.net, 2025. [En línea]. Disponible en: https://www.distributed-systems.net/index.php/books/ds4/ (consultado: 23 oct. 2026).

[7] Amazon Web Services, «Precision clock and time synchronization on your EC2 instance», Amazon EC2 User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/set-time.html (consultado: 23 oct. 2026).

[8] AWS Academy, «AWS Academy Learner Lab: Readme», Vocareum, 2026. Documento interno del laboratorio, accesible desde la sesión del Learner Lab.

[9] A. Ospina Sanjuan, aclaraciones sobre el enunciado del Proyecto 1 (A1–A8), comunicación personal, oct. 2026.

[10] DFSha, «Registro de decisiones de arquitectura (ADR 0001–0033)», repositorio del proyecto, carpeta docs/decisiones, 2026. [En línea]. Disponible en: https://github.com/pjg09/dfsha/tree/main/docs/decisiones (consultado: 23 oct. 2026).

[11] A. Ospina Sanjuan, «Arquitecturas peer-to-peer», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 24 sep. 2026.

[12] A. Ospina Sanjuan, «P2P: índices, control y datos», clase (transcripción de audio), Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 2026.

[13] G. M. Amdahl, «Validity of the single processor approach to achieving large scale computing capabilities», en *Proc. AFIPS Spring Joint Computer Conf.*, 1967, pp. 483–485. doi: 10.1145/1465482.1465560.

[14] A. Ospina Sanjuan, «Capítulo 2: Arquitecturas», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 13 ago. 2026.

[15] A. Ospina Sanjuan, «MOM: mensajes, trabajo y réplicas», clase (transcripción de audio), Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 2026.

[16] etcd Authors, «etcd documentation». [En línea]. Disponible en: https://etcd.io/docs/ (consultado: 23 oct. 2026).

[17] bakwc, «PySyncObj: A library for replicating your python class between multiple servers, based on raft protocol», GitHub, licencia MIT. [En línea]. Disponible en: https://github.com/bakwc/PySyncObj (consultado: 23 oct. 2026).

[18] A. Ospina Sanjuan, «hdfs-hadoop», repositorio del laboratorio de HDFS, GitHub, 2026. [En línea]. Disponible en: https://github.com/aospina/hdfs-hadoop (consultado: 23 oct. 2026).

[19] Docker Inc., «Start containers automatically», Docker Docs. [En línea]. Disponible en: https://docs.docker.com/engine/containers/start-containers-automatically/ (consultado: 23 oct. 2026).

[20] Amazon Web Services, «How Amazon EC2 instance stop and start works», Amazon EC2 User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html (consultado: 23 oct. 2026).

[21] K. Davis, B. Peabody y P. Leach, «Universally unique identifiers (UUIDs)», RFC 9562, IETF, may. 2024. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc9562 (consultado: 23 oct. 2026).

[22] A. Ospina Sanjuan, «Llamadas a procedimientos remotos. gRPC: de la invocación local a los microservicios modernos», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 24 sep. 2026.

[23] Google, «Protocol Buffers documentation». [En línea]. Disponible en: https://protobuf.dev/ (consultado: 23 oct. 2026).

[24] A. Ospina Sanjuan, «Message-Oriented Middleware: comunicación asíncrona y desacoplada entre procesos distribuidos», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 24 sep. 2026.

[25] gRPC Authors, «Deadlines», gRPC Documentation. [En línea]. Disponible en: https://grpc.io/docs/guides/deadlines/ (consultado: 23 oct. 2026).

[26] A. Ospina Sanjuan, «gRPC», repositorio del laboratorio de gRPC, GitHub, 2026. [En línea]. Disponible en: https://github.com/aospina/gRPC (consultado: 23 oct. 2026).

[27] gRPC Authors, «Status codes and their use in gRPC», gRPC Documentation. [En línea]. Disponible en: https://grpc.io/docs/guides/status-codes/ (consultado: 23 oct. 2026).

[28] gRPC Authors, «Error handling», gRPC Documentation. [En línea]. Disponible en: https://grpc.io/docs/guides/error/ (consultado: 23 oct. 2026).

[29] J. H. Howard *et al.*, «Scale and performance in a distributed file system», *ACM Trans. Computer Systems*, vol. 6, n.º 1, pp. 51–81, feb. 1988. doi: 10.1145/35037.35059.

[30] C. G. Gray y D. R. Cheriton, «Leases: An efficient fault-tolerant mechanism for distributed file cache consistency», en *Proc. 12th ACM Symp. Operating Systems Principles (SOSP)*, 1989, pp. 202–210. doi: 10.1145/74850.74870.

[31] National Institute of Standards and Technology, «Secure Hash Standard (SHS)», FIPS PUB 180-4, ago. 2015. doi: 10.6028/NIST.FIPS.180-4.

[32] M. Dworkin, «Recommendation for block cipher modes of operation: Galois/Counter Mode (GCM) and GMAC», NIST, Gaithersburg, MD, EE. UU., SP 800-38D, nov. 2007. doi: 10.6028/NIST.SP.800-38D.

[33] A. Ospina Sanjuan, «RPC: fallos y plazos», clase (transcripción de audio), Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 2026.

[34] C. Percival y S. Josefsson, «The scrypt password-based key derivation function», RFC 7914, IETF, ago. 2016. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc7914 (consultado: 23 oct. 2026).

[35] H. Krawczyk, M. Bellare y R. Canetti, «HMAC: Keyed-hashing for message authentication», RFC 2104, IETF, feb. 1997. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc2104 (consultado: 23 oct. 2026).

[36] E. Rescorla, «The Transport Layer Security (TLS) protocol version 1.3», RFC 8446, IETF, ago. 2018. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc8446 (consultado: 23 oct. 2026).

[37] Amazon Web Services, «Amazon EBS encryption», Amazon EBS User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-encryption.html (consultado: 23 oct. 2026).

[38] Amazon Web Services, «AWS KMS cryptography essentials: Envelope encryption», AWS Key Management Service Developer Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/kms/latest/developerguide/kms-cryptography.html (consultado: 23 oct. 2026).

[39] A. Ospina Sanjuan, «Llamadas a procedimientos remotos (RPC)», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 13 ago. 2026.

[40] Amazon Web Services, «Burstable performance instances», Amazon EC2 User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances.html (consultado: 23 oct. 2026).

# Anexo A. Especificación completa de las APIs

Este anexo contiene los contratos gRPC completos del paquete `dfsha.v1`, en tres archivos: `common.proto` (tipos compartidos), `metadata.proto` (`MetadataService`) y `datanode.proto` (`DataNodeService`). Son el punto de partida de la carpeta `proto/` en la fase II; cualquier cambio posterior se registrará como una decisión.

Convenciones del contrato:
- **Identificadores.** Los RPC usan la forma *verbo + objeto*, y cada RPC tiene su par `<Rpc>Request` / `<Rpc>Response`, aunque hoy estén vacíos, para poder añadir campos sin romper la compatibilidad.
- **Unidades.** Los campos con unidad la llevan como sufijo (`size_bytes`).
- **Enumeraciones.** Los valores llevan como prefijo el nombre del tipo y el valor 0 es `_UNSPECIFIED`.
- **Autenticación.** El token de acceso viaja en los metadatos de la llamada (`authorization: Bearer <token>`), no en los mensajes. Las llamadas de los nodos de datos se autentican con su certificado (TLS mutuo).
- **Errores.** Se devuelven con un código de estado gRPC y un `google.rpc.ErrorInfo` con el código de motivo (§5.4).
- **Hashes.** `block_sha256` son los 32 bytes del SHA-256 del bloque **tal como se guarda** (cifrado).

## A.1 `common.proto`

```protobuf
syntax = "proto3";

package dfsha.v1;

import "google/protobuf/timestamp.proto";

// Operación que autoriza un token de bloque.
enum BlockOperation {
  BLOCK_OPERATION_UNSPECIFIED = 0;
  BLOCK_OPERATION_READ = 1;
  BLOCK_OPERATION_WRITE = 2;
}

// Modo de escritura de write() (RF3).
enum WriteMode {
  WRITE_MODE_UNSPECIFIED = 0;
  WRITE_MODE_CREATE = 1;   // el archivo no existe
  WRITE_MODE_REPLACE = 2;  // sustituye el contenido completo
  WRITE_MODE_APPEND = 3;   // añade al final
  WRITE_MODE_PARTIAL = 4;  // cambia bloques en cualquier offset
}

// Autorización firmada por el servidor de metadatos para leer o escribir
// un bloque concreto. El nodo de datos la verifica sin consultar a nadie.
message BlockToken {
  string block_id = 1;
  BlockOperation operation = 2;
  google.protobuf.Timestamp expires_at = 3;  // 10 min tras su emisión
  bytes signature = 4;                       // HMAC-SHA256 de los campos 1 a 3
}

// Rango de índices de bloque consecutivos. block_count = 0 significa
// "desde first_block_index hasta el final del archivo".
message BlockRange {
  uint64 first_block_index = 1;
  uint64 block_count = 2;
}

// Ubicación de un bloque: qué nodos de datos tienen sus réplicas.
message BlockLocation {
  uint64 block_index = 1;
  string block_id = 2;
  bytes block_sha256 = 3;               // hash que guarda el servidor de metadatos
  uint64 size_bytes = 4;                // tamaño del bloque guardado (cifrado)
  repeated string datanode_addrs = 5;   // "datanode-2:50052"; al escribir, la primera es la primaria
  BlockToken block_token = 6;
}
```

## A.2 `metadata.proto`

```protobuf
syntax = "proto3";

package dfsha.v1;

import "google/protobuf/timestamp.proto";
import "dfsha/v1/common.proto";

service MetadataService {
  // --- Usuarios ---------------------------------------------------------
  rpc Authenticate(AuthenticateRequest) returns (AuthenticateResponse);
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);            // solo administradores

  // --- Espacio de nombres (RF1) ----------------------------------------
  rpc ListDirectory(ListDirectoryRequest) returns (ListDirectoryResponse);   // ls
  rpc GetFileInfo(GetFileInfoRequest) returns (GetFileInfoResponse);
  rpc CreateDirectory(CreateDirectoryRequest) returns (CreateDirectoryResponse);  // mkdir
  rpc DeleteDirectory(DeleteDirectoryRequest) returns (DeleteDirectoryResponse);  // rmdir
  rpc DeleteFile(DeleteFileRequest) returns (DeleteFileResponse);            // rm
  rpc MovePath(MovePathRequest) returns (MovePathResponse);                  // mv

  // --- Acceso a archivos (RF2, RF3) ------------------------------------
  rpc OpenFile(OpenFileRequest) returns (OpenFileResponse);
  rpc GetBlockLocations(GetBlockLocationsRequest) returns (GetBlockLocationsResponse);
  rpc LockBlocks(LockBlocksRequest) returns (LockBlocksResponse);
  rpc UpdateLease(UpdateLeaseRequest) returns (UpdateLeaseResponse);         // renovar
  rpc UnlockBlocks(UnlockBlocksRequest) returns (UnlockBlocksResponse);
  rpc AllocateBlocks(AllocateBlocksRequest) returns (AllocateBlocksResponse);
  rpc CommitFile(CommitFileRequest) returns (CommitFileResponse);
  rpc AbortFile(AbortFileRequest) returns (AbortFileResponse);

  // --- Nodos de datos (TLS mutuo, certificado de rol datanode) ----------
  rpc RegisterDataNode(RegisterDataNodeRequest) returns (RegisterDataNodeResponse);
  rpc ReportHeartbeat(ReportHeartbeatRequest) returns (ReportHeartbeatResponse);
  rpc ReportBlocks(ReportBlocksRequest) returns (ReportBlocksResponse);
  rpc ReportBlockReceived(ReportBlockReceivedRequest) returns (ReportBlockReceivedResponse);

  // --- Nodos de datos o clientes ----------------------------------------
  // El servidor deduce el origen del aviso de la identidad del llamante
  // (certificado o token), nunca de un campo del mensaje.
  rpc ReportCorruptReplica(ReportCorruptReplicaRequest) returns (ReportCorruptReplicaResponse);
}

// ===== Tipos =============================================================

enum EntryType {
  ENTRY_TYPE_UNSPECIFIED = 0;
  ENTRY_TYPE_FILE = 1;
  ENTRY_TYPE_DIRECTORY = 2;
}

enum OpenMode {
  OPEN_MODE_UNSPECIFIED = 0;
  OPEN_MODE_READ = 1;
  OPEN_MODE_WRITE = 2;    // el archivo debe existir
  OPEN_MODE_CREATE = 3;   // el archivo no debe existir; se crea al confirmar
}

message FileInfo {
  string file_id = 1;
  string path = 2;
  uint64 size_bytes = 3;          // tamaño en claro
  uint64 version = 4;
  uint64 block_size_bytes = 5;    // fijado al crear el archivo
  uint64 block_count = 6;
  google.protobuf.Timestamp modified_at = 7;
}

message DirectoryEntry {
  string name = 1;
  EntryType type = 2;
  uint64 size_bytes = 3;          // 0 para directorios
  uint64 version = 4;             // 0 para directorios
  google.protobuf.Timestamp modified_at = 5;
}

// Bloque de una versión nueva, tal como lo envía el cliente al confirmar.
message CommittedBlock {
  uint64 block_index = 1;
  string block_id = 2;
  bytes block_sha256 = 3;
  uint64 size_bytes = 4;
}

// Bloque que un nodo de datos tiene en su almacén.
message StoredBlock {
  string block_id = 1;
  bytes block_sha256 = 2;
  uint64 size_bytes = 3;
}

enum DataNodeCommandType {
  DATA_NODE_COMMAND_TYPE_UNSPECIFIED = 0;
  DATA_NODE_COMMAND_TYPE_REPLICATE = 1;          // copiar block_id a target_addr
  DATA_NODE_COMMAND_TYPE_DELETE = 2;             // borrar block_id
  DATA_NODE_COMMAND_TYPE_VERIFY = 3;             // recalcular el hash de block_id
  DATA_NODE_COMMAND_TYPE_SEND_BLOCK_REPORT = 4;  // enviar un informe de bloques
}

// Orden que el servidor de metadatos envía en la respuesta al latido.
message DataNodeCommand {
  DataNodeCommandType type = 1;
  string block_id = 2;              // vacío en SEND_BLOCK_REPORT
  string target_addr = 3;           // solo en REPLICATE
  BlockToken target_block_token = 4;  // solo en REPLICATE: token de escritura en el destino
}

// ===== Usuarios ==========================================================

message AuthenticateRequest {
  string username = 1;
  string password = 2;
}
message AuthenticateResponse {
  string access_token = 1;                   // HMAC-SHA256; contiene user_id y caducidad
  google.protobuf.Timestamp expires_at = 2;  // 1 h
}

message CreateUserRequest {
  string request_id = 1;
  string username = 2;
  string password = 3;
  bool is_admin = 4;
}
message CreateUserResponse {
  string user_id = 1;
}

// ===== Espacio de nombres ================================================

message ListDirectoryRequest {
  string path = 1;                // absoluta dentro del espacio del usuario
}
message ListDirectoryResponse {
  repeated DirectoryEntry entries = 1;
}

message GetFileInfoRequest {
  string path = 1;
}
message GetFileInfoResponse {
  FileInfo info = 1;
}

message CreateDirectoryRequest {
  string request_id = 1;
  string path = 2;
}
message CreateDirectoryResponse {}

message DeleteDirectoryRequest {
  string request_id = 1;
  string path = 2;
}
message DeleteDirectoryResponse {}

message DeleteFileRequest {
  string request_id = 1;
  string path = 2;
}
message DeleteFileResponse {}

message MovePathRequest {
  string request_id = 1;
  string source_path = 2;
  string target_path = 3;
}
message MovePathResponse {}

// ===== Acceso a archivos =================================================

message OpenFileRequest {
  string path = 1;
  OpenMode mode = 2;
}
message OpenFileResponse {
  bytes file_handle = 1;    // opaco y firmado: file_id, versión, modo, usuario
  FileInfo info = 2;        // versión abierta
  bytes data_key = 3;       // clave de datos en claro (256 bits), solo por TLS
}

message GetBlockLocationsRequest {
  bytes file_handle = 1;
  BlockRange block_range = 2;
}
message GetBlockLocationsResponse {
  repeated BlockLocation locations = 1;   // con tokens de lectura
}

message LockBlocksRequest {
  string request_id = 1;
  bytes file_handle = 2;
  BlockRange block_range = 3;   // se concede entero o nada
}
message LockBlocksResponse {
  string lease_id = 1;
  google.protobuf.Timestamp expires_at = 2;   // TTL de 30 s
  uint64 current_version = 3;                 // si difiere de la abierta, puede haber conflicto
}

message UpdateLeaseRequest {
  string request_id = 1;
  string lease_id = 2;
}
message UpdateLeaseResponse {
  google.protobuf.Timestamp expires_at = 1;
}

message UnlockBlocksRequest {
  string request_id = 1;
  string lease_id = 2;
}
message UnlockBlocksResponse {}

message AllocateBlocksRequest {
  string request_id = 1;
  bytes file_handle = 2;
  string lease_id = 3;
  repeated uint64 block_indices = 4;   // dentro del rango arrendado
}
message AllocateBlocksResponse {
  repeated BlockLocation blocks = 1;   // block_id nuevos, primaria primero, tokens de escritura
}

message CommitFileRequest {
  string request_id = 1;
  bytes file_handle = 2;               // fija la versión base
  string lease_id = 3;
  WriteMode write_mode = 4;
  repeated CommittedBlock blocks = 5;  // índices nuevos o sustituidos
  uint64 size_bytes = 6;               // tamaño en claro de la versión nueva
}
message CommitFileResponse {
  uint64 version = 1;
}

message AbortFileRequest {
  string request_id = 1;
  bytes file_handle = 2;
  string lease_id = 3;
}
message AbortFileResponse {}

// ===== Nodos de datos ====================================================

message RegisterDataNodeRequest {
  string node_id = 1;          // el de la marca de su volumen de datos
  string hostname = 2;         // "datanode-2"
  uint64 capacity_bytes = 3;
  uint64 free_bytes = 4;
}
message RegisterDataNodeResponse {
  bool is_block_report_required = 1;
}

message ReportHeartbeatRequest {
  string node_id = 1;
  uint64 free_bytes = 2;
  uint64 used_bytes = 3;
  uint32 active_transfers = 4;
}
message ReportHeartbeatResponse {
  repeated DataNodeCommand commands = 1;
}

message ReportBlocksRequest {
  string node_id = 1;
  repeated StoredBlock blocks = 2;
}
message ReportBlocksResponse {
  repeated DataNodeCommand commands = 1;
}

message ReportBlockReceivedRequest {
  string node_id = 1;
  StoredBlock block = 2;       // guardado y con el hash verificado
}
message ReportBlockReceivedResponse {}

message ReportCorruptReplicaRequest {
  string block_id = 1;
  string node_id = 2;          // nodo que guarda la réplica corrupta
}
message ReportCorruptReplicaResponse {}
```

## A.3 `datanode.proto`

```protobuf
syntax = "proto3";

package dfsha.v1;

import "dfsha/v1/common.proto";

service DataNodeService {
  // Flujo del llamante al nodo: una cabecera y después el bloque en
  // mensajes de 1 MiB. Lo usan el cliente (hacia la primaria), la primaria
  // (hacia las secundarias, con secondary_addrs vacío) y el nodo origen de
  // una re-replicación (hacia el destino).
  rpc WriteBlock(stream WriteBlockRequest) returns (WriteBlockResponse);

  // Flujo del nodo al cliente: una cabecera y después el bloque en
  // mensajes de 1 MiB. Si el hash no coincide al terminar, la llamada
  // acaba con DATA_LOSS + BLOCK_CORRUPTED.
  rpc ReadBlock(ReadBlockRequest) returns (stream ReadBlockResponse);
}

message WriteBlockHeader {
  string block_id = 1;
  BlockToken block_token = 2;           // operación WRITE
  bytes block_sha256 = 3;               // hash del bloque cifrado completo
  uint64 size_bytes = 4;
  repeated string secondary_addrs = 5;  // solo en la llamada a la primaria
}

message WriteBlockRequest {
  oneof content {
    WriteBlockHeader header = 1;   // primer mensaje del flujo
    bytes data = 2;                // mensajes siguientes, de 1 MiB como máximo
  }
}

message WriteBlockResponse {
  // Réplicas que tienen el bloque guardado y verificado. La primaria
  // responde en cuanto hay write_quorum (2); si no lo alcanza, la llamada
  // acaba con UNAVAILABLE + QUORUM_NOT_REACHED.
  repeated string stored_on = 1;
}

message ReadBlockRequest {
  string block_id = 1;
  BlockToken block_token = 2;           // operación READ
}

message ReadBlockHeader {
  uint64 size_bytes = 1;
  bytes block_sha256 = 2;
}

message ReadBlockResponse {
  oneof content {
    ReadBlockHeader header = 1;    // primer mensaje del flujo
    bytes data = 2;                // mensajes siguientes, de 1 MiB como máximo
  }
}
```

# Anexo B. Registro de decisiones

Cada decisión del diseño tiene un registro de decisión de arquitectura (ADR) en el repositorio del proyecto [10], con su contexto, las opciones consideradas y sus consecuencias. La Tabla 38 los relaciona con la sección del documento que los desarrolla. En la fase II, cualquier cambio respecto a este diseño se registrará como un ADR nuevo que sustituya al anterior. La tabla de cambios del informe final se construirá a partir de esos registros.

**Tabla 38.** Decisiones de diseño y sección que las desarrolla.

| ADR | Decisión | Sección |
|---|---|---|
| 0008 | Python 3.12, gRPC y Docker sobre varias instancias EC2 | §3.8, §5.1 |
| 0009 | Bloques inmutables y versiones de archivo: semántica de `write()` | §7.2 |
| 0010 | Consistencia de apertura-cierre (G1–G4) | §7.3 |
| 0011 | Arrendamientos exclusivos por rango de bloques | §8.1, §8.2 |
| 0012 | Replicación: R = 3, W = 2, reenvío desde la réplica primaria | §4.4 |
| 0013 | Confirmación atómica de archivos y escrituras interrumpidas | §8.4 |
| 0014 | Servidor de metadatos replicado con Raft en tres nodos | §3.3, §9.4 |
| 0015 | Topología: 3 servidores de metadatos, 5 nodos de datos y 1 cliente | §3.6 |
| 0016 | Tamaño de bloque de 16 MiB, configurable | §4.1 |
| 0017 | Ubicación de réplicas y reparto de bloques | §4.3 |
| 0018 | Detección de fallos, re-replicación y recolección de basura | §9.2, §9.3 |
| 0019 | gRPC en todas las interfaces, sin MOM ni API REST | §5.1 |
| 0020 | Reintentos: al menos una vez, con operaciones idempotentes | §8.6 |
| 0021 | Descubrimiento: el cliente solo conoce los servidores de metadatos | §3.6, §11.4 |
| 0022 | Autenticación, autorización y tokens de bloque | §10.2, §10.3 |
| 0023 | Cifrado en tránsito: TLS con el cliente y TLS mutuo entre nodos | §10.4 |
| 0024 | Cifrado en reposo: cifrado de sobre en el cliente con AES-256-GCM | §10.5 |
| 0025 | Espacio de nombres por usuario y operaciones de RF1 | §2.3, §6.5 |
| 0026 | Almacenamiento de bloques en un volumen EBS por nodo de datos | §3.4, §3.6 |
| 0027 | Despliegue en AWS: una imagen por rol y un contenedor por instancia | §3.6 |
| 0028 | Métricas y experimentos | §12 |
| 0029 | Especificación de las APIs en el documento | §5, Anexo A |
| 0030 | Entorno local de desarrollo con las mismas imágenes que AWS | §3.7 |
| 0031 | Modo seguro tras cada elección de líder | §9.5, §9.6 |
| 0032 | Réplicas corruptas y verificación periódica de bloques | §8.5 |
| 0033 | Sincronización de relojes entre nodos | §10.6 |
| 0035 | Persistencia de los metadatos en un volumen EBS por servidor de metadatos | §3.6, §3.8, §4.2, §10.7 |

Los ADR 0001 a 0007 y el 0034 son decisiones de proceso: idioma, convenciones de nombres, commits y versiones, tabla de cambios entre fases, diagramas como código y formato de este documento y de sus figuras.
