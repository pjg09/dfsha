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
| 0 | Supuestos de AWS y del profesor | — | Pendiente |
| 1 | Esqueleto del repositorio y contratos | Implementación RF1–RF3 | Pendiente |
| 2 | Elección de Raft | Alta disponibilidad | Pendiente |
| 3 | Nodo de datos y entorno local | Distribución y comunicaciones | Pendiente |
| 4 | Servidor de metadatos | Distribución; alta disponibilidad | Pendiente |
| 5 | Cliente: RF1 y RF2 de extremo a extremo | Implementación RF1–RF3 | Pendiente |
| 6 | Seguridad | Seguridad | Pendiente |
| 7 | Despliegue en AWS | Distribución y comunicaciones | Pendiente |
| 8 | RF3, arrendamientos y concurrencia | Implementación RF1–RF3; consistencia | Pendiente |
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
- **Profesor:** fecha de entrega; formato y extensión del informe; si acepta las evidencias en texto en el
  repositorio; dónde se entrega el vídeo; cómo será la defensa.

**Terminada cuando:** las respuestas del profesor están en `aclaraciones.md` (A9 en adelante), lo
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
- Sobre la implementación de Raft de la etapa 2: espacio de nombres, versiones de archivo,
  `AllocateBlocks`, `CommitFile` atómico, `GetBlockLocations`, ubicación de réplicas (§4.3), registro de
  nodos con latidos, respuesta con el nombre del líder e instantáneas (§3.3, §4.2).
- Los tres servidores de metadatos en el entorno local.

**Terminada cuando:** cada RPC tiene sus pruebas y la caída del líder no pierde ninguna confirmación.

### 5. Cliente: RF1 y RF2 de extremo a extremo
- CLI y biblioteca con las operaciones de RF1 y RF2 de la Tabla 4 (`ls`, `cd`, `mkdir`, `rmdir`, `rm`,
  `mv`, `put`, `get`), con bloques en paralelo y verificación del hash.

**Terminada cuando:** en local, `put` de 1 GiB y `get` devuelven el mismo hash.

**Punto de control de alcance.** Comparar lo avanzado con la fecha de entrega. Si no da el tiempo, la
simplificación se declara y se lleva al profesor **ahora**, antes de implementar (enunciado §7, A7), no al
final.

### 6. Seguridad
- Usuarios y tokens de acceso (§10.2), autorización por propietario y tokens de bloque (§10.3), TLS con
  el cliente y TLS mutuo entre nodos con una CA interna (§10.4), cifrado de sobre con AES-256-GCM (§10.5),
  gestión de secretos (§10.7).
- Va antes del despliegue en AWS para que todas las evidencias se tomen ya con la seguridad del diseño.

**Terminada cuando:** en local, un acceso a un archivo ajeno y otro con un token caducado se rechazan, y
un bloque en disco no se puede leer sin la clave.

### 7. Despliegue en AWS
- `deploy/aws/`: el script repetible de la §3.6. Cuenta las instancias en marcha (9 como máximo), crea
  los grupos de seguridad y los volúmenes EBS, instala Docker y chrony, genera `/etc/hosts` y los
  certificados, y arranca los contenedores.
- Copia de seguridad de los metadatos en S3 y su restauración (§4.2, ADR 0035).

**Terminada cuando:** el clúster de 9 instancias se levanta desde cero con un comando y pasa la prueba de
carga y recuperación. **Primeras evidencias:** «Carga y recuperación» y «Seguridad».

### 8. RF3, arrendamientos y concurrencia
- `open`, `read`, `write`, `lock`, `unlock` y `close` con consistencia de apertura-cierre (§7), los cuatro
  modos de escritura, arrendamientos con TTL (§8.1), comprobación de versión al confirmar (§8.2),
  escrituras interrumpidas y recolección de basura (§8.4), reintentos idempotentes (§8.6).

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
- Figuras actualizadas y PDF (o el formato que pida el profesor).
- Revisar el `README.md` siguiendo sus instrucciones desde cero: clonar, desplegar y probar.

**Terminada cuando:** el PDF está generado y revisado.

### 12. Vídeo
- Guion de 10–15 min: arquitectura, ejecución distribuida, fallos y resultados medidos (§5.3).
- Grabación en AWS en una sola sesión del lab, ensayada antes.

**Terminada cuando:** el vídeo está exportado y dura entre 10 y 15 min.

### 13. Entrega
- ADR y cambio de `.releaserc.json` para la 1.0.0 (procedimiento del ADR 0005), y release `v1.0.0`.
- Etiqueta `entrega-fase-2` (`CONTRIBUTING.md` §7.3).
- Entrega en Teams: informe, enlace al vídeo y enlace al repositorio.

**Terminada cuando:** la tarea aparece entregada en Teams.

### 14. Defensa
- Repasar cada decisión con su ADR y las preguntas probables. Tener el clúster listo para desplegarse en
  una sesión, por si hay demostración.
- Después de la defensa: terminar las instancias y borrar los volúmenes y el bucket.

**Terminada cuando:** la defensa está hecha y AWS está limpio.
