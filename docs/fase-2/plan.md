# Plan de la fase II

Desde el diseño cerrado (etiqueta `entrega-fase-1`, versión 0.1.0) hasta la entrega en Teams y la defensa.
Qué hay que entregar: enunciado §5.3. Cómo se califica: enunciado §6.

## Reglas del plan

- **Orden sin dependencias hacia delante.** Cada etapa usa solo lo que dejaron las anteriores.
- **Cada etapa deja algo que funciona y se puede comprobar**, commiteado y en `main`, con las pruebas
  automatizadas pasando. Se da por terminada cuando cumple su criterio «Terminada cuando».
- **Se implementa lo que declara `docs/fase-1.md`.** Cualquier desviación va primero en un ADR y después
  en el código (ADR 0006). Si cambia algo que sale en una figura, la figura cambia en la misma tanda.
- **Evidencias en el momento** (ADR 0036). Desde la etapa 7, cada etapa termina desplegada en AWS con sus
  evidencias registradas. Cada prueba mínima tiene un script que la ejecuta y guarda su salida, para
  poder repetirla con la versión final sin rehacerla a mano.
- **Las instrucciones de instalación y ejecución del `README.md`** se actualizan en la etapa que cambia
  algo, no al final (§5.3: instrucciones reproducibles).
- **Versiones.** Cada etapa con funcionalidad nueva genera una versión *minor* (0.2.0, 0.3.0…). La 1.0.0
  sale con la entrega (etapa 13).

## Estado

| Etapa | Nombre | Criterio de §6 al que aporta | Estado |
|---|---|---|---|
| 0 | Supuestos de AWS y del profesor | — | Terminada |
| 1 | Esqueleto del repositorio y contratos | Implementación RF1–RF3 | Terminada |
| 2 | Elección de Raft | Alta disponibilidad | Terminada |
| 3 | Nodo de datos y entorno local | Distribución y comunicaciones | Terminada |
| 4 | Servidor de metadatos | Distribución; alta disponibilidad | Terminada |
| 5 | Cliente: RF1 y RF2 de extremo a extremo | Implementación RF1–RF3 | Terminada |
| 6 | Seguridad | Seguridad | Terminada |
| 7 | Despliegue en AWS | Distribución y comunicaciones | Terminada |
| 8 | RF3 en el cliente y concurrencia | Implementación RF1–RF3; consistencia | Pendiente |
| 9 | Tolerancia a fallos | Alta disponibilidad, replicación y consistencia | Pendiente |
| 10 | Experimentos y pruebas finales | Pruebas de rendimiento | Pendiente |
| 11 | Informe técnico final | Documentación | Pendiente |
| 12 | Vídeo | Vídeo | Pendiente |
| 13 | Entrega | — | Pendiente |
| 14 | Defensa | Defensa | Pendiente |

## Etapas

### 0. Supuestos de AWS y del profesor
Confirmar lo que la fase I dejó sin probar, antes de escribir código que dependa de ello.
- **Learner Lab:** terminar la instancia de prueba `ubuntu-26.04`, porque el clúster ocupa las 9 plazas;
  crear y borrar un bucket de S3 cifrado (ADR 0035); comprobar si una instancia puede obtener imágenes de
  ECR o si hay que construirlas en cada una (§14); comprobar Docker en una t3.micro.
- **Profesor:** formato y extensión del informe, si acepta las evidencias en texto en el repositorio y
  cómo será la defensa. Respondido en A9 y A10.

**Terminada cuando:** las respuestas del profesor están en `aclaraciones.md` (A9 y A10), lo
comprobado en AWS está en `notas.md` y lo que cambie el diseño tiene su ADR (al menos, cómo llegan las
imágenes a las instancias).

### 1. Esqueleto del repositorio y contratos
- `pyproject.toml` con Python 3.12 y las versiones exactas de las dependencias (ADR 0008).
- `proto/dfsha/v1/` a partir del Anexo A, con su código generado.
- Paquete `dfsha/` con `common/`: configuración por variables de entorno, logging y errores con código
  de motivo (§5.4).
- Workflow de GitHub Actions que ejecuta pytest y pyright en cada push.

**Terminada cuando:** la instalación, pytest y pyright pasan en local y en GitHub Actions.

### 2. Elección de Raft
- Prototipo con etcd y con PySyncObj, tres nodos en Docker Compose (ADR 0014).
- Comprobar en cada uno: que escribe cada entrada en disco antes de confirmarla (§4.2), las instantáneas,
  los tiempos de elección y la caída del líder.

**Terminada cuando:** hay un ADR con la elección, los tiempos medidos y lo que cambia en la §3.3. El
código del prototipo no se queda en el repositorio; sus resultados, en el ADR.

### 3. Nodo de datos y entorno local
- Imagen `dfsha-datanode` y `deploy/local/compose.yaml` (ADR 0030).
- `WriteBlock` en flujo con área temporal y hash SHA-256, `ReadBlock`, reenvío en paralelo desde la
  réplica primaria (§4.4) y almacenamiento en su volumen (ADR 0026).

**Terminada cuando:** las pruebas escriben un bloque en tres nodos de datos con reenvío desde la
primaria, lo leen con el mismo hash y rechazan un bloque corrupto.

### 4. Servidor de metadatos
- Sobre etcd (ADR 0039), con el modelo de claves y el cliente del ADR 0041: espacio de nombres, versiones de
  archivo, `OpenFile`, `AllocateBlocks`, `CommitFile` atómico, `AbortFile`, `GetBlockLocations`, ubicación de
  réplicas (§4.3), registro de nodos con latidos y respuesta con el nombre del líder (§3.3, §4.2).
- **Líder y cercado** (ADR 0039): elección con la clave `leader`, renuncia anticipada y época del líder en
  cada transacción y en las órdenes a los nodos de datos (`leader_epoch`, cambio compatible del contrato).
- **Arrendamientos en el servidor**, traídos de la etapa 8 porque `put` los necesita (§6.1, ADR 0041):
  `LockBlocks`, `UpdateLease` y `UnlockBlocks` con TTL (§8.1), conflicto inmediato con `LOCK_CONFLICT` y
  comprobación de versión al confirmar (§8.2).
- Reintentos idempotentes con `request_id` en todas las RPC que cambian metadatos (§8.6).
- Un **único usuario implícito** hasta la etapa 6, sin clave de datos y con descriptores de archivo sin
  firmar; las claves ya llevan el `user_id` (ADR 0041).
- Los tres servidores de metadatos y los tres miembros de etcd en el entorno local (ADR 0040).
- **Pendiente de la etapa 3:** conectar el nodo de datos al servidor de metadatos. Hoy los avisos de
  bloque recibido (`ReportBlockReceived`) solo se escriben en el log (`LoggingBlockReporter`), y faltan
  el alta (`RegisterDataNode`), los latidos y el informe de bloques.

**Terminada cuando:** cada RPC tiene sus pruebas y la caída del líder no pierde ninguna confirmación.

### 5. Cliente: RF1 y RF2 de extremo a extremo
- CLI y biblioteca con las operaciones de RF1 y RF2 de la Tabla 4 (`ls`, `cd`, `mkdir`, `rmdir`, `rm`,
  `mv`, `put`, `get`), con bloques en paralelo y verificación del hash.

- Reintentos con espera ante `UNAVAILABLE`: `NODE_NOT_LEADER` (repetir en el líder indicado) y
  `QUORUM_NOT_REACHED` justo después de una elección (pendiente de la etapa 4, `notas.md`).

**Terminada cuando:** en local, `put` de 1 GiB y `get` devuelven el mismo hash.

**Punto de control de alcance.** Revisar si alguna parte del diseño ha resultado inviable de implementar.
Si es así, la simplificación se declara y se lleva al profesor **ahora**, antes de implementarla
(enunciado §7, A7), no al final.

### 6. Seguridad
- Usuarios y tokens de acceso (§10.2), autorización por propietario y tokens de bloque (§10.3), TLS con
  el cliente y TLS mutuo entre nodos con una CA interna (§10.4), cifrado de sobre con AES-256-GCM (§10.5),
  gestión de secretos (§10.7).
- Va antes del despliegue en AWS para que todas las evidencias se tomen ya con la seguridad del diseño.
- **Pendiente de la etapa 3:** el nodo de datos todavía no verifica el token de bloque de `WriteBlock` ni
  de `ReadBlock`, y escucha sin TLS.
- **Pendiente de la etapa 4** (ADR 0041): sustituir el usuario implícito por el del token de acceso,
  firmar los descriptores de archivo, generar y envolver la clave de datos en `OpenFile`, emitir tokens de
  bloque en `AllocateBlocks` y `GetBlockLocations`, y TLS mutuo con etcd (ADR 0039).

**Terminada cuando:** en local, un acceso a un archivo ajeno y otro con un token caducado se rechazan, y
un bloque en disco no se puede leer sin la clave.

### 7. Despliegue en AWS
- `deploy/aws/`: el script repetible de la §3.6. Cuenta las instancias en marcha (9 como máximo), crea
  los grupos de seguridad y los volúmenes EBS, instala Docker y chrony, genera `/etc/hosts` y los
  certificados, y arranca los contenedores.
- Copia de seguridad de los metadatos en S3 y su restauración (§4.2, ADR 0035).
- **Cómo se hace** (decidido al empezar la etapa 7): `deploy/aws/deploy.sh` con las órdenes `images`
  (construye y envía a ECR), `up` (grupos de seguridad, volúmenes e instancias), `install` (por SSH con
  `~/.ssh/labsuser.pem`: nombre de host, `/etc/hosts`, Docker, volumen montado por UUID con `nofail`,
  secretos, `compose.yaml` del rol con red del host y arranque), `status`, `backup` y `down`.
- **Pendiente de la etapa 6** (ADR 0043): generar los secretos con `python -m dfsha.common.pki`, copiar a
  cada instancia solo los de su host, con dueño el usuario de las imágenes (10001) y permisos de solo
  lectura, y dejar el directorio de datos de etcd con permisos `0700`.

**Terminada cuando:** el clúster de 9 instancias se levanta desde cero con un comando y pasa la prueba de
carga y recuperación. **Primeras evidencias:** «Carga y recuperación» y «Seguridad».

### 8. RF3 en el cliente y concurrencia
- En la biblioteca y la CLI del cliente: `open`, `read`, `write`, `lock`, `unlock` y `close` con
  consistencia de apertura-cierre (§7), los cuatro modos de escritura (§7.2), renovación del arrendamiento
  mientras se escribe y reintentos con el mismo `request_id` (§8.6).
- Escrituras interrumpidas y recolección de basura de los bloques huérfanos (§8.4).
- Pruebas de concurrencia: dos escritores sobre el mismo bloque y sobre bloques distintos del mismo
  archivo, y un escritor que muere con el arrendamiento (escenario 1, §11.1).
- Los arrendamientos y la comprobación de versión del servidor ya existen desde la etapa 4 (ADR 0041).

**Terminada cuando:** pasan en AWS «Acceso RF3» y «Concurrencia» (escenario 1, §11.1), con sus
evidencias registradas.

### 9. Tolerancia a fallos
- Estados de un nodo, re-replicación y resincronización (§9.2, §9.3), réplicas corruptas y verificación
  periódica (§8.5), modo seguro (§9.5) y arranque en frío (§9.6).

**Terminada cuando:** pasan en AWS «Replicación y fallos», «Consistencia» (escenario 2, §11.2) y los
escenarios 3 y 4 (§11.3, §11.4), con sus evidencias registradas.

### 10. Experimentos y pruebas finales
- E1–E9 en AWS (ADR 0028): 5 repeticiones por punto, mediana y p95, CSV en `bench/resultados/`.
- Ajustar los parámetros de la §13.2. Cambiar un valor por defecto lleva ADR.
- Repetir las siete pruebas mínimas con la versión final, con sus scripts.

**Terminada cuando:** el índice de `evidencias/README.md` está completo.

### 11. Informe técnico final
- En `docs/fase-2/`: arquitectura, tabla de cambios frente a la fase I (ADR 0006), APIs, algoritmos,
  despliegue, pruebas, resultados y limitaciones (§5.3). Fuentes: ADR 0036.
- Figuras actualizadas y PDF, sin límite de extensión (A9).
- Revisar el `README.md` siguiendo sus instrucciones desde cero: clonar, desplegar y probar.

**Terminada cuando:** el PDF está generado y revisado.

### 12. Vídeo
- Guion de 10–15 min: arquitectura, ejecución distribuida, fallos y resultados medidos (§5.3).
- Revisión del guion y del vídeo grabado. La grabación en AWS se hace en una sola sesión del lab,
  ensayada antes. La entrega del vídeo la gestiona Pedro.

**Terminada cuando:** el vídeo está revisado y dura entre 10 y 15 min.

### 13. Entrega
- ADR y cambio de `.releaserc.json` para la 1.0.0 (procedimiento del ADR 0005), y release `v1.0.0`.
- Etiqueta `entrega-fase-2` (`CONTRIBUTING.md` §7.3).
- Entrega en Teams (la gestiona Pedro): informe, enlace al vídeo y enlace al repositorio.

**Terminada cuando:** la tarea aparece entregada en Teams.

### 14. Defensa
- 25 minutos: qué se hizo, cómo y por qué, con demostración en vivo y preguntas del profesor (A10).
- Guion de la demostración, ensayado en una sesión nueva del Learner Lab: desplegar desde cero y mostrar
  las pruebas mínimas elegidas.
- Repasar cada decisión con su ADR y las preguntas probables.
- Después de la defensa: terminar las instancias y borrar los volúmenes y el bucket.

**Terminada cuando:** la defensa está hecha y AWS está limpio.
