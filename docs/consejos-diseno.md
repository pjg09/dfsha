# Consejos y condicionantes de diseño

Lo que se vio en clase, en los labs y en el entorno de AWS que **condiciona el diseño de DFSha** o
la forma de defenderlo. Recopilado el 2026-10-21 de la base de conocimiento del curso.

Cada consejo tiene un identificador (`C1`, `C2`…) para citarlo en ADR y documentos, su **fuente** y
su **implicación** para el proyecto. Esto es material de apoyo, no requisitos: los requisitos están
en el [enunciado](enunciado.md).

**Fuentes** (rutas dentro de la base de conocimiento):

| Etiqueta | Origen | Fiabilidad |
|---|---|---|
| `[D03]`, `[D04]`… | Diapositivas del profesor (`fuentes/texto/NN-*.txt`) | Alta: material oficial |
| `[G1]`, `[G3]`, `[G4]` | Guías de las transcripciones de audio de clase 1 (P2P), 3 (RPC) y 4 (MOM) | Media-alta: lo dijo el profesor, reconstruido por estudiantes |
| `[Ap]` | Apuntes de clase de una estudiante | Media: puede tener errores de toma de notas |
| `[Lab HDFS]`, `[Lab gRPC]` | Labs del profesor (`practicas/`, `fuentes/repos-profesor/`) | Alta para el comportamiento comprobado |
| `[AWS]` | Comprobado en la cuenta del Learner Lab durante el curso | Alta, pero puede cambiar |
| `[Libro]` | Tanenbaum & van Steen, 4.ª ed. | Alta |
| `[Inferencia]` | Conclusión propia a partir de las anteriores | **Verificar** |

> El tema *sistemas de archivos distribuidos* **no tiene diapositivas**. Ningún consejo de este
> documento sale de una clase sobre DFS; se trasladan de temas vecinos (C/S, P2P, RPC, MOM, HDFS).

---

## 1. Cómo evalúa el profesor

**C1 · Lo que puntúa es la justificación, no la elección.** — `[G3]`, examen del parcial 2
«Ojo, el cambio es válido si usted justifica por qué». El examen real fueron preguntas abiertas de
justificar, diagnosticar y proponer mitigaciones.
→ Cada decisión del documento de la fase I sigue el esquema **dato → concepto → consecuencia →
límite**: qué se observa o se exige, qué concepto lo explica, qué se gana y **qué no cubre**. Una
decisión sin su límite declarado parece no entendida.

**C2 · «El enunciado debe especificarlo».** — `[G1]`
Ante «¿los archivos siempre pasan por el superpeer?», el profesor respondió que depende del diseño y
que hay que especificarlo.
→ Todo lo que el enunciado deja abierto se **declara explícitamente**: semántica de `write()` (RF3),
modelo de consistencia (RNF3), qué es «confirmar» (§7), qué pasa en cada fallo. Lo no declarado se
evalúa como no resuelto.

**C3 · Las simplificaciones se aprueban antes de implementar.** — enunciado §7
→ Toda simplificación de RF3 o de las garantías va en la fase I como **propuesta explícita** y se
lleva al profesor para aprobarla antes de la fase II.

## 2. Arquitectura cliente/servidor

**C4 · Los puntos únicos de fallo no se arreglan optimizando código.** — `[D04]`
La arquitectura fija el acoplamiento, los SPOF y la escalabilidad. En C/S el servidor concentra el
control, el cuello de botella y el SPOF.
→ El **servidor de metadatos** es el SPOF natural de DFSha. Hay que replicarlo **o** justificar por
qué no y qué garantía se pierde. Callarlo es el error más visible del diseño.

**C5 · Control ≠ datos.** — `[G1]`, `[D09]`, `[Ap]`
Analogías del profesor: el sobre y el contenido de una carta, la secretaría y el médico, el directorio
telefónico y los negocios. Primero se pregunta *dónde*; luego se va directamente *allí*.
→ El cliente pide al servidor de metadatos **solo ubicaciones** y transfiere los bloques
**directamente con los nodos de datos**. Si los bloques pasan por el servidor de metadatos, ese
servidor es a la vez SPOF y cuello de botella de ancho de banda (RNF1, RNF5).

**C6 · Hay dos disponibilidades distintas.** — `[G1]`
«Si se cae el índice, los datos siguen existiendo; el problema es que encontrarlos puede ser
imposible.» Disponibilidad de **localización** ≠ disponibilidad de **datos**.
→ Replicar bloques (RNF2) no basta: si cae el servidor de metadatos, los bloques existen pero nadie
puede encontrarlos. El diseño tiene que decir qué pasa con **los metadatos** cuando falla su
servidor. Si el cliente guarda en caché las ubicaciones, puede seguir leyendo un rato, pero entonces
hay que decir cuánto tiempo y con qué riesgo de leer datos viejos.

**C7 · El servidor de metadatos es el *binder* de DFSha.** — `[D06]`, `[G1]`
En RPC, el cliente pregunta al binder dónde está el servicio y luego lo llama. El profesor lo enlazó
con el patrón control ≠ datos.
→ Es la respuesta natural al escenario obligatorio «¿cómo descubre el cliente la ubicación de los
bloques?» y a RNF7. Lo único que el cliente debe conocer es **cómo llegar al servidor de metadatos**,
y eso por nombre lógico (`metadata-1`), no por IP.

## 3. Replicación y consistencia

**C8 · Réplicas ≠ trabajadores.** — `[G4]`
Las réplicas conservan estado; los trabajadores procesan. Añadir réplicas no acelera, y añadir
trabajadores no replica.
→ El factor de replicación se justifica por **tolerancia a fallos**, no por rendimiento. Si se
quiere leer en paralelo desde varias réplicas, eso es otra decisión y hay que justificarla aparte.

**C9 · Quórum de mayoría: Q = ⌊N/2⌋ + 1.** — `[G4]`
N=3 → Q=2, tolera 1 fallo; N=5 → Q=3, tolera 2. Con una sola réplica viva de tres no se aceptan
escrituras nuevas, **lo que no significa que se hayan perdido datos**.
→ Si se usa quórum: cuántas réplicas, cuántas fallas tolera la escritura, cuántas la lectura, y qué
hace el sistema por debajo del quórum (rechazar, encolar, degradarse).

**C10 · Confirmar a una mayoría no es esperar a todas.** — `[G4]`
Ejemplo de clase, saldo de 50 a 100 en A, B y C, con respuestas en 12, 20 y 55 ms: con mayoría se
confirma a los 20 ms (un 63,6 % menos de espera), pero C queda atrasada un tiempo.
→ Es el **compromiso latencia/consistencia** que pide justificar la fase I: «cuándo una escritura se
considera confirmada» (§7). Hay que medirlo en la fase II (prueba de rendimiento con al menos dos
condiciones, §5.2).

**C11 · Tres errores sobre consistencia que conviene no cometer.** — `[G4]`, `[Libro §7.2]`
1. «Consistencia fuerte = todas las copias iguales en cada instante». Falso: se define por **lo que
   pueden observar las operaciones**, no por el estado interno.
2. «Una mayoría hace fuerte cualquier lectura». Falso: hacen falta reglas de lectura, escritura y consenso.
3. «Eventual = siempre habrá incoherencia». Falso: significa **converger** cuando cesan las escrituras.
→ La respuesta al escenario «una réplica está desconectada durante una escritura» se formula en
términos de **qué ve el lector**, no de qué tiene cada disco.

**C12 · Escribir una sola vez simplifica mucho la consistencia.** — `[Lab HDFS]`
HDFS es *write-once-read-many*: no hay escrituras aleatorias, y eso simplifica la consistencia de las réplicas.
→ RF3 deja **declarar** qué admite `write()`. Admitir modificación parcial de bloques multiplica la
complejidad (concurrencia, versiones, réplicas a medio actualizar). Si se admite, que sea por una
razón; si no, declararlo y llevarlo a aprobación (C3).

## 4. Fallos y detección

**C13 · Un *timeout* no significa «no se ejecutó».** — `[G3]`
Pudo perderse la petición, retrasarse el servidor o perderse la respuesta. Reintentar algo con efectos
puede duplicarlo.
→ Cada operación de escritura de DFSha se diseña para que se pueda **reintentar sin duplicar**:
operaciones idempotentes o `request_id` que el servidor reconoce.

**C14 · Un ID sin registro de lo ya procesado no evita duplicados.** — `[G1]`
Ejemplo del profesor: un retiro de 100 cuya respuesta se pierde; reenviarlo sin ID puede retirar 300.
Con el mismo ID el servidor reconoce el duplicado, **pero solo si guarda qué IDs ya procesó**.
→ El `request_id` necesita un registro con alguna duración en el servidor, y eso hay que dimensionarlo.

**C15 · Semánticas ante fallos: *at-least-once*, *at-most-once* y *exactly-once*.** — `[D06]`, `[Libro]`, `[G4]`
*Exactly-once* no es alcanzable en general. La solución práctica es *at-least-once* con operaciones
idempotentes. Hacer el *ack* **después** de aplicar el efecto, más idempotencia.
→ Hay que declarar la semántica de cada operación entre cliente, servidor de metadatos y nodos de datos.

**C16 · La detección de fallos tarda, y ese tiempo hay que fijarlo.** — `[Lab HDFS]`
Por defecto, HDFS tarda unos **10,5 minutos** en dar por muerto un DataNode (2 × 5 min de recheck +
10 × 3 s de heartbeat). Durante ese tiempo lo sigue mostrando como vivo.
→ El intervalo de latido y el umbral de «caído» son **parámetros de diseño** con su compromiso:
detectar rápido produce falsos positivos ante la lentitud de la red. Además, en el vídeo de 10–15 min
la caída tiene que notarse en segundos, no en 10 minutos.

**C17 · Con tantas réplicas como nodos no se puede re-replicar.** — `[Lab HDFS]`
Con 3 DataNodes y factor de replicación 3, al caer uno los bloques quedan sin la réplica que falta
hasta que el nodo vuelve: no hay dónde crear la tercera copia.
→ Para demostrar **recuperación** en la prueba «Replicación y fallos» (§5.2) hacen falta **más nodos
de datos que el factor de replicación** (por ejemplo, 4 nodos con factor 3, o 3 nodos con factor 2).
Esto condiciona el número de EC2 (C28).

**C18 · Los fallos son parciales.** — `[D03]`
Cada componente falla por separado; un SD no se cae entero, se cae a trozos.
→ Cada escenario de §4.2 se analiza como un **fallo parcial**: qué componente falla, qué sigue
funcionando y qué observa el cliente.

## 5. Rendimiento y tamaño de bloque

**C19 · Distribuir conviene solo si t_proc ≫ t_com.** — `[G1]`, `[D03]`
Ejemplo de los pintores: con 4 pintores va bien; con un millón, explicar el trabajo cuesta más que
pintarlo. Modelo de clase T(p) = 120/p + 2p.
→ El **tamaño de bloque** es una decisión de **granularidad**. Bloques pequeños reparten mejor la
carga pero multiplican metadatos y peticiones; bloques grandes hacen lo contrario. HDFS usa 128 MB
(`[Lab HDFS]`). Hay que elegirlo y justificarlo con el tamaño de los archivos de prueba.

**C20 · El servidor de metadatos es la fracción secuencial.** — `[Inferencia]` a partir de Amdahl (examen del parcial 2)
Si todas las operaciones pasan por un único servidor de metadatos, esa parte no escala al añadir
nodos de datos y limita la mejora.
→ Hay que reducir las consultas al servidor de metadatos por operación (pedir las ubicaciones de
todos los bloques de una vez, caché en el cliente) y medirlo en el experimento de escalabilidad.

**C21 · Bytes no son bits.** — `[G1]`
40 MB por un enlace de 64 Mb/s tardan 5 s, no 0,6 s.
→ Las métricas del proyecto usan unidades explícitas (`throughput_mb_s` = **megabytes** por segundo,
ver `convenciones.md`), y el informe dice cuál es cuál.

**C22 · Una respuesta siempre, y en un tiempo razonable.** — `[Ap]`
«Necesito que la interacción con el cliente sea en un tiempo razonable, que siempre exista una respuesta.»
→ Ninguna llamada del cliente puede quedarse colgada: plazos (*deadlines*) en todas las RPC y
errores explícitos (C23).

## 6. Comunicación

**C23 · El lab de gRPC del profesor no pone *deadline*.** — `[Lab gRPC]`
Si el servidor se cuelga, el cliente espera indefinidamente. Además usa `add_insecure_port`, sin TLS.
→ En DFSha, **toda llamada gRPC lleva *deadline*** y el canal va cifrado con TLS (RNF6). Copiar el lab
tal cual incumple las dos cosas.

**C24 · Colas frente a tópicos.** — `[G4]`, examen del parcial 2
Para repartir trabajo entre N nodos: **colas** (consumidores que compiten). Los tópicos duplican el
mensaje en cada suscriptor.
→ Si se usa MOM (el enunciado lo sugiere «cuando proceda»), por ejemplo para tareas de
re-replicación o notificaciones, hay que elegir cola o tópico según si el trabajo se reparte o se difunde.

## 7. Seguridad

**C25 · Un hash prueba integridad, no autoría.** — `[G1]`
«Tengo la canción» no basta: hace falta identidad (CA) e integridad (hash de referencia confiable).
El hash es determinista, pero no dice quién creó el contenido.
→ SHA-256 por bloque cubre la integridad. La autenticación y autorización (RNF6, RF1) van aparte:
TLS entre nodos, credenciales de usuario y comprobación del propietario. Además, el enunciado avisa
(§7) de que la integridad tampoco sustituye la coordinación de escrituras concurrentes.

## 8. Entorno: AWS Academy Learner Lab

**C26 · La topología cambia, y en AWS cambia todos los días.** — `[D03]` (falacias de Deutsch) + `[AWS]`
«La topología no cambia» es una de las falacias. En el Learner Lab, **la IP pública de las instancias
cambia en cada sesión**.
→ Es la razón práctica de RNF7 y de los nombres `<rol>-<n>` (ADR 0003). Ninguna configuración guarda IP.

**C27 · Las credenciales caducan con la sesión, y al acabar la sesión se paran las instancias.** — `[AWS]`, Readme del Learner Lab (consultado el 2026-10-23)
Las sesiones del lab duran unas 4 h, y el temporizador se amplía pulsando *Start Lab* otra vez. Al
caducar, las credenciales del CLI devuelven `ExpiredToken`. Al acabar la sesión, el lab **para las
instancias en marcha y en la siguiente sesión las vuelve a arrancar todas a la vez**. La IP pública
cambia; la privada se conserva, según la documentación de AWS (sin comprobar en el lab).
→ Los scripts de despliegue tienen que ser **repetibles** y no pueden depender de una sesión
anterior. Ningún componente de DFSha usa credenciales de AWS en tiempo de ejecución. El clúster tiene
que aguantar un **arranque en frío** de todos los nodos a la vez (ADR 0031), y Docker tiene que estar
activado al arrancar el sistema (ADR 0040, que sustituye al 0027).

**C28 · Límites del lab e instancias pequeñas.** — `[AWS]`, Readme del Learner Lab (consultado el 2026-10-23) y comprobaciones con el CLI de esa fecha
- La t3.micro de prueba tiene **908 MiB de RAM** y 8 GiB de disco.
- **Instancias:**
  - Como máximo **9 en marcha a la vez**, sea cual sea su tamaño: las que sobran se terminan.
  - Con 20 o más, la cuenta se desactiva y se borra todo.
  - Máximo de 32 vCPU, tipos de nano a large y solo On-Demand.
  - Regiones: us-east-1 y us-west-2.
- **EBS:**
  - Hasta 100 GB por volumen, de tipo gp2, gp3, sc1 o standard, sin IOPS provisionadas.
  - **Se pueden cifrar** con la clave gestionada `aws/ebs`. Comprobado con un volumen de prueba: quedó
    `available` y `Encrypted=true`, y después se borró. El cifrado por defecto de la cuenta está desactivado.
- **IAM:** no se pueden crear roles; las instancias usan `LabInstanceProfile`.
- **Otros servicios:**
  - ECR: el usuario del lab crea repositorios y envía imágenes. Con `LabRole` se lee **y también se
    escribe**: comprobado el 2026-11-06, una instancia con `LabInstanceProfile` envió una imagen a un
    repositorio de prueba.
  - Session Manager funciona con `LabInstanceProfile`.
  - Route 53 responde, y el Readme solo prohíbe registrar dominios.
  - Service Quotas devuelve `AccessDenied`, así que el límite de vCPU solo consta en el Readme.
- **Presupuesto:** AWS Budgets se actualiza cada 8–12 h. Si se supera el presupuesto, la cuenta se
  desactiva y se pierde todo.

→ La topología del ADR 0015 ocupa las 9 instancias y no cabe ninguna más:
- Ni siquiera cabe la de prueba (`ubuntu-26.04`, en marcha el 2026-10-23). Hay que pararla o terminarla
  antes de desplegar.
- El script de despliegue cuenta las instancias en marcha antes de lanzar ninguna.

Hay que dimensionar los nodos y los archivos de prueba con estos recursos. No hay que fiarse del saldo del
lab, porque llega con horas de retraso.

**C29 · Discos EBS: montaje persistente o datos perdidos sin aviso.** — `[AWS]`, `practicas/ebs-volumen/`
Si un volumen montado a mano no está en `fstab` (por UUID y con `nofail`), tras reiniciar el punto de
montaje es un directorio vacío del disco raíz y se escribe allí **sin ningún error**. El volumen raíz se
borra al terminar la instancia (`DeleteOnTermination=true`).
→ Los nodos de datos (ADR 0026) y los servidores de metadatos (ADR 0035) guardan sus datos en un volumen
EBS propio: el montaje va en el script de despliegue y cada servidor **comprueba al arrancar** que su
directorio de datos está montado.

**C30 · Grupos de seguridad.** — `[AWS]`
El grupo que crea el asistente de lanzamiento (`launch-wizard-1` en la instancia de prueba) solo
abre el 22/tcp, y además a todo Internet (`0.0.0.0/0`).
→ Los puertos entre nodos se abren **solo entre los grupos de seguridad del proyecto**
(`dfsha-sg-<rol>`), no a `0.0.0.0/0`. Esto también es evidencia de RNF6.

## 9. Trampas del enunciado

| Trampa | Dónde | Consecuencia |
|---|---|---|
| «La integridad no sustituye la coordinación de escrituras concurrentes» | §7 | Responder al escenario de dos escrituras simultáneas solo con hashes pierde puntos |
| «No basta una simulación local monolítica» | §5 | Varios contenedores en una sola máquina no cuentan como producto final. Hacen falta varias EC2 con comunicación real por red |
| Garantías «comprobables» | §7 | «El sistema es consistente» no vale. Hay que decir cuándo se confirma y qué se puede leer |
| Nota individual no sustituible | §6 | El documento de la fase I se califica por sí solo |
| Matriz comparativa de propuestas individuales | §5.1 | Confirmado: el proyecto es individual y la matriz no aplica. Si se quiere un artefacto equivalente, que registre qué decisiones del diseño de la fase I cambian en la fase II y por qué |
