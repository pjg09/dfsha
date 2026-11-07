# Notas para el informe de la fase II

Material que el informe técnico final necesitará y que no está en otro sitio ([ADR 0036](../decisiones/0036-evidencias-y-material-del-informe.md)).
Se anota en el momento, en viñetas con fecha y commit; el informe se redacta al final.

Un cambio de diseño no va aquí: va en un ADR (ADR 0006). Una evidencia tampoco: va en `evidencias/`.

## Comprobaciones del entorno

- **2026-11-06 · Limpieza de la cuenta del Learner Lab** (etapa 0). Antes de crear nada se terminaron
  las instancias y se borraron el EFS, el bucket y los grupos de seguridad de prácticas anteriores, en
  `us-east-1` y `us-west-2`. Quedan solo los recursos del propio laboratorio: VPC y grupo de seguridad por
  defecto, el par de claves `vockey`, la pila de CloudFormation y las funciones Lambda del lab con sus
  logs. Así las 9 plazas de instancia quedan libres para el clúster (§3.6).
- **2026-11-06 · S3** (etapa 0, ADR 0035). Con las credenciales de la sesión se crea un bucket en
  `us-east-1`, se bloquea el acceso público, se fija el cifrado SSE-S3 (`AES256`), se escribe y se lee un
  objeto de 1 MiB (idéntico) y se borra el bucket. El Learner Lab permite todo lo que necesita la copia de
  seguridad de los metadatos.
- **2026-11-06 · Docker en una t3.micro** (etapa 0, ADR 0027). Ubuntu 26.04.1 LTS, 2 vCPU, 908 MiB de RAM
  y sin swap. Docker 29.1.3 y Docker Compose 2.40.3, de los repositorios de Ubuntu, se instalan en 31 s y
  quedan activados al arrancar. Con Docker en marcha y una imagen de Python 3.12 ejecutada quedan 420 MiB
  disponibles. El disco raíz tiene 3,1 GiB usados de 6,7.
- **2026-11-06 · Imágenes** (etapa 0). Imagen de prueba: `python:3.12-slim` con `grpcio` 1.85.1,
  `grpcio-tools` y `cryptography` 50.0.2. Construirla en la t3.micro tarda 20 s; obtenerla de ECR, 5 s.
  Con `LabInstanceProfile` la instancia inicia sesión en ECR, lee y también escribe, en contra de lo que
  decían los consejos (corregido). Desde la máquina de administración, enviarla a ECR tarda 21 s.
- **2026-11-06 · Hora** (etapa 0, ADR 0033). En la AMI de Ubuntu 26.04, chrony ya usa el servicio de hora
  de Amazon como fuente principal sin configurar nada. El script de despliegue solo tiene que comprobarlo
  con `chronyc tracking`.

- **2026-11-07 · `put` y `get` de 1 GiB en local** (etapa 5, versión 0.7.1.dev). En Docker en la máquina
  de desarrollo, con 5 nodos de datos y bloques de 16 MiB: `put` en 4,3 s (248 MB/s) y `get` en 1,8 s
  (608 MB/s), mismo SHA-256. Sin cifrado ni TLS todavía (etapa 6). No son valores de rendimiento del
  sistema: no hay red real; E1 y E2 se miden en AWS.
- **2026-11-07 · `put` y `get` de 1 GiB con la seguridad activada** (etapa 6, local). Con TLS mutuo y
  cifrado AES-256-GCM en el cliente: `put` en 5,2 s (206 MB/s) y `get` en 2,6 s (415 MB/s), mismo SHA-256.
  Sin seguridad eran 4,3 s y 1,8 s (etapa 5). Es una referencia del coste de TLS y del cifrado; E8 lo mide
  en AWS.
- **2026-11-07 · Primer despliegue en AWS** (etapa 7, imágenes v0.9.0, `57d91bc`). `deploy.sh images` construye
  y envía las tres imágenes a ECR en 1 min 34 s; `up` crea los grupos de seguridad, las 9 instancias y los 8
  volúmenes en 5 min 20 s (los volúmenes, uno tras otro, unos 24 s cada uno); `install` configura los 9 hosts
  en paralelo en 1 min. `metadata-1` sale elegido líder y los cinco nodos de datos se dan de alta en cuanto
  hay líder. El directorio de datos de etcd queda con `0700`.
- **2026-11-07 · Despliegue desde cero con una orden** (etapa 7, `ddb9bc6`). Con la cuenta vacía,
  `deploy.sh all` levanta los 9 hosts en 6 min 50 s sin intervención, y el clúster pasa la prueba de carga y
  recuperación. `down` necesitó dos pasadas para borrar los grupos de seguridad, que se citan entre sí.
- **2026-11-07 · Un nodo de datos congelado detiene lecturas durante minutos** (etapa 10, E6, v0.13.0). Con
  `docker pause`, el nodo acepta conexiones pero no responde. El cliente, con la conexión ya abierta, espera los
  120 s del plazo de transferencia por cada bloque que lee de ese nodo, y dentro de un mismo `get` lo vuelve a
  probar con otros bloques: lecturas de 120, 240 y 360 s. Ninguna falla, pero la §11.4 pide pasar a otra réplica
  si una no responde. Con el nodo parado (conexión rechazada), el cambio de réplica es inmediato.
- **2026-11-07 · Bloques de 4 MiB rinden como los de 16** (etapa 10, E5, v0.13.0). La tasa de transferencia es
  la misma con 4 y 16 MiB y baja un 12 % con 64 MiB; la modificación parcial de 4 KiB tarda 204, 513 y
  1 828 ms. 4 MiB sería mejor para escrituras parciales, a cambio de cuatro veces más bloques en los metadatos,
  coste que no se midió. Se mantiene 16 MiB (ADR 0016) y se cuenta la alternativa en el informe.
- **2026-11-07 · El SHA-256 cuesta más que el cifrado** (etapa 10, E8, v0.13.0). En `client-1` (t3.small),
  AES-256-GCM cifra a 1,5 GB/s y SHA-256 va a 397 MB/s. TLS mutuo quita entre un 25 y un 32 % a un canal gRPC
  (unos 450 frente a 615 MB/s). Ninguna pieza explica por sí sola el techo de unos 130 MB/s de un cliente.
- **2026-11-07 · Varios clientes en el mismo host tampoco escalan** (etapa 10, E4, v0.12.1). Con 4 y 8 clientes
  a la vez en `client-1` (t3.small), la tasa agregada se queda en 128–136 MB/s, el mismo techo que un solo
  cliente: el límite es la máquina cliente. Para mostrar RNF1 harían falta clientes en varias máquinas; con el
  tope de 9 instancias del Learner Lab no hay ninguna libre. Sobre el mismo bloque, los conflictos crecen más
  deprisa que los clientes (498 con 8 clientes en 5 repeticiones) porque el cliente reintenta enseguida.
- **2026-11-07 · Un solo cliente no escala con los nodos de datos** (etapa 10, E2, v0.12.1). Con 3, 4 y 5 nodos,
  un `put` de 1 GiB va a 127–128 MB/s y un `get` a 136–137 MB/s: el límite lo pone el cliente, no los nodos.
  La escalabilidad de RNF1 hay que mostrarla con la tasa agregada de varios clientes (E4). No se midió qué
  limita al cliente (CPU del cifrado y del hash, red o disco).
- **2026-11-07 · RF3 y concurrencia en AWS** (etapa 8, v0.10.0). Los cuatro modos de escritura coinciden con
  un modelo local y solo reescriben los bloques que cambian (Tabla 22). En el escenario 1 con procesos
  reales, el segundo escritor recibe `LOCK_CONFLICT` al momento y `VERSION_CONFLICT` si reintenta desde la
  versión que abrió. Tras un `kill -9` al primero, el segundo escribe 27 s después, dentro del TTL de 30 s
  (`evidencias/2026-11-07-acceso-rf3` y `evidencias/2026-11-07-concurrencia`).
- **2026-11-07 · Memoria del cliente en AWS** (etapa 9, v0.12.0). Pico del proceso (`getrusage`) en `client-1`,
  una t3.micro con unos 514 MiB disponibles: `put` de 1 GiB 247 MiB y `get` de 1 GiB 291 MiB, con 4
  transferencias en paralelo. Basta para un cliente; dos o más procesos cliente de 1 GiB a la vez en la misma
  t3.micro no caben (E4, etapa 10).
- **2026-11-07 · Memoria de los nodos de datos en AWS** (etapa 7). Durante el `put` de 1 GiB, el pico del
  proceso (`VmHWM`) de cada nodo de datos fue de 103 a 132 MiB, con unos 440 MiB disponibles en cada t3.micro.
  Confirma en AWS la medición local de la etapa 3.
- **2026-11-07 · Reparto de réplicas en AWS** (etapa 7). Con un volumen por nodo, las 192 réplicas de 1 GiB
  quedan en 39, 38, 39, 38 y 38. El reparto desigual del entorno local venía del disco compartido.
- **2026-11-07 · Copia de seguridad de etcd en S3** (etapa 7, ADR 0035). `deploy.sh backup` guarda una
  instantánea de 120 KiB (con 1 GiB y 1 MiB cargados) en el bucket `dfsha-copias-<sufijo>`, con SSE-S3 y
  acceso público bloqueado, en 11 s.
- **2026-11-07 · Bloques ilegibles en disco** (etapa 6, local). Un archivo de texto con una marca repetida
  20 000 veces se carga con `put`, y ningún bloque de los cinco nodos de datos contiene la marca. Cada
  bloque guardado mide 28 bytes más que el bloque en claro (nonce y etiqueta de AES-GCM).

- **2026-11-07 · Fin de la sesión del Learner Lab sin copia de seguridad** (etapa 9). La sesión caducó a las
  08:46 UTC, mientras se construían las imágenes de la v0.11.0: la política `voc-cancel-cred` deniega todo
  y no se llegó a instalar nada. No se hizo `deploy.sh backup` antes, en contra del ADR 0035; los metadatos
  siguen en los volúmenes EBS de las instancias paradas. El siguiente arranque es un arranque en frío real
  (§9.6) con la v0.10.0.

## Limitaciones descubiertas

- **2026-11-06 · Memoria de los nodos de datos, por confirmar** (etapa 0). Una t3.micro sin swap deja unos
  420 MiB para el contenedor. Con bloques de 16 MiB enviados en mensajes de 1 MiB debería bastar, pero hay
  que medir el consumo del nodo de datos en la etapa 3 y vigilar que el kernel no mate el proceso por falta
  de memoria.
- **2026-11-06 · Memoria de los nodos de datos, medida en local** (etapa 3, versión 0.2.1.dev6). Bloques de
  16 MiB + 28 bytes hacia una primaria que reenvía a dos secundarias, 32 bloques por prueba, en Docker en la
  máquina de desarrollo. Pico de memoria del proceso (`VmHWM`) de la primaria con `MALLOC_ARENA_MAX=2`: unos
  75 MiB con 1 escritura, 115 MiB con 4 y una mediana de 167 MiB (164–196, 5 repeticiones) con 8. La
  secundaria se queda por debajo de 100 MiB. Cabe en los 420 MiB libres de una t3.micro, pero **hay que
  volver a medirlo en AWS** (etapa 7): allí cambian la red, el disco y la CPU.

- **2026-11-07 · Crear un archivo en un directorio que se mueve** (etapa 4, ADR 0041). Un `put` guarda en
  su descriptor la entrada del directorio padre tal como estaba al abrir. Si alguien mueve o borra ese
  directorio antes de la confirmación, `CommitFile` falla y el cliente tiene que repetir la carga. Es el
  precio de que `mv` de un directorio sea una sola clave.
- **2026-11-07 · Escrituras rechazadas justo después de una elección** (etapa 4, §9.5). Tras cada elección,
  ningún nodo de datos cuenta como vivo hasta que envía un latido al nuevo líder; hasta entonces
  `AllocateBlocks` responde `QUORUM_NOT_REACHED`, y el cliente tiene que reintentar con espera (etapa 5).

- **2026-11-07 · Un certificado por máquina cliente** (etapa 6, ADR 0043). Como todas las conexiones usan
  TLS mutuo, cada máquina cliente necesita un certificado de la CA interna. En el despliegue el único
  cliente es `client-1`.
- **2026-11-07 · El bloqueo por intentos fallidos vive en la memoria del líder** (etapa 6, ADR 0043): tras
  5 fallos seguidos, el usuario queda bloqueado 30 s, pero un cambio de líder reinicia el contador.

- **2026-11-07 · La contraseña de ECR caduca a las 12 h** (etapa 7). `install` la entrega a cada instancia
  y las imágenes quedan en caché, así que reiniciar un contenedor no la necesita; recrear una instancia
  pasadas 12 h exige volver a ejecutar `install`.

- **2026-11-07 · Un servidor de metadatos que se para responde `UNKNOWN`** (etapa 7). Mientras se cierra, las
  llamadas que ya atendía fallan con el canal de etcd cerrado y llegan como `UNKNOWN`, no como `UNAVAILABLE`.
  El nodo de datos ya lo tolera; el cliente no reintenta `UNKNOWN`, así que una operación en curso durante la
  parada del líder puede fallar en lugar de reintentarse. Por revisar en la etapa 9 (tolerancia a fallos).

- **2026-11-07 · El disco de `client-1` se llena con las pruebas** (etapa 8). Tiene un disco raíz de 8 GiB, y
  cada `get` de 1 GiB deja una copia en `/srv/dfsha/client`. Una comprobación falló por falta de espacio y,
  peor, mostró el hash de una copia anterior. Los scripts de evidencia tienen que borrar sus copias y mirar
  el espacio libre antes de leer; para los experimentos de la etapa 10 (E1, archivos grandes) puede hacer
  falta un volumen para el cliente.
- **2026-11-07 · Un modo de escritura por apertura** (etapa 8). `CommitFile` lleva un solo modo y un solo
  arrendamiento, así que cada apertura del archivo admite un modo (salvo al crear, donde anexar y modificar
  forman parte de la creación) y las escrituras tienen que caber en el rango arrendado: una escritura fuera
  de él falla y pide `lock()` con el rango completo. `write()` prepara los bloques en un archivo temporal
  local y `close()` los envía, así que cerrar un archivo con muchos cambios tarda lo que tarda enviarlos.

## Problemas encontrados y cómo se resolvieron

- **2026-11-07 · gRPC para Python no permite un certificado de cliente opcional** (etapa 6, ADR 0043). Con
  `require_client_auth=False` el servidor no recibe el certificado del otro extremo, así que no podía
  distinguir un nodo de datos de un cliente en el mismo puerto. Se pasó a TLS mutuo en todas las
  conexiones, también las del cliente, con un certificado para `client-1`.
- **2026-11-07 · Avisos de etcd en el entorno local** (etapa 6). etcd avisa de que su directorio de datos
  tiene permisos `drwxr-xr-x` y recomienda `0700`. En AWS el script de despliegue tiene que dejar el
  directorio de datos de etcd con `0700` (etapa 7).

- **2026-11-07 · Dos modos por defecto mal elegidos en el cliente** (etapa 8). Al abrir para escribir, el
  modo por defecto era reemplazar, que pide el archivo entero y chocaba con un `lock` de un rango; y al
  abrir para crear no se podía anexar. Lo encontró la prueba de la sesión de `dfsha shell`, antes de
  publicarse: el modo por defecto pasó a ser la modificación parcial, como en POSIX.
- **2026-11-07 · Una confirmación parcial podía truncar lo anexado por otro escritor** (etapa 8). `CommitFile`
  tomaba el tamaño de la versión nueva del cliente, calculado sobre su versión base. Con un escritor que anexa
  y confirma primero y otro que modifica el bloque 0 y confirma después, el archivo volvía al tamaño antiguo y
  lo anexado quedaba fuera, en contra de la Tabla 24. Se vio al diseñar la biblioteca del cliente, antes de
  que ningún cliente usara esos modos. Como anexar y modificar no encogen el archivo, ahora vale el mayor de
  los dos tamaños; una prueba reproduce el caso (falla sin la corrección).
- **2026-11-07 · La recolección de basura recorre todos los metadatos** (etapa 8, §9.3). Con cada informe de
  bloques, el líder lee todas las versiones, arrendamientos y escrituras en curso. Con 5 nodos cada 5 min y
  pocos archivos es barato; con muchos archivos habría que llevar un índice de bloques vivos.
- **2026-11-07 · Un nodo de datos lleno seguía recibiendo bloques** (etapa 10, v0.12.1). La primera ejecución
  de E2 se cortó al llenarse el volumen de 10 GiB de un nodo. Con 3 nodos y R = 3 cada nodo guarda todos los
  bloques, y los archivos borrados de E1 seguían vivos durante su periodo de gracia de 10 min. Salieron dos
  fallos: el líder elegía nodos sin espacio (ordenaba por espacio libre pero no descartaba los llenos, y solo
  comprobaba W en el primer bloque de cada reserva), y el nodo lleno respondía `UNKNOWN` en lugar de
  `RESOURCE_EXHAUSTED`. Corregidos, con pruebas que fallan sin la corrección. Para medir, `deploy.sh` admite
  ahora `DFSHA_EXTRA_ENV` con parámetros como el periodo de gracia o W.
- **2026-11-07 · Al repetir un bloque, el líder devolvía el nodo que acababa de caer** (etapa 9, ADR 0044). En
  el escenario 3 en AWS, `datanode-4` cayó durante una carga de 1 GiB. El líder lo sigue contando como vivo
  hasta 9 s y, por ser el de más espacio libre, lo dio como primaria en las cuatro reservas del bloque 58: el
  cliente agotó sus intentos y la carga falló. En la primera ejecución no pasó por casualidad. La §11.3 dice
  que al repetir el bloque se reciben «otros tres» nodos; el ADR 0044 añade a `AllocateBlocks` los nodos que
  ya fallaron. Un primer intento de corrección excluía siempre la primaria y rompió otra prueba: con las
  secundarias caídas, la primaria está sana y responde `QUORUM_NOT_REACHED`, así que ahora indica ella qué
  secundarias fallaron.
- **2026-11-07 · Un `get` con un nodo de datos caído agotaba la memoria del cliente** (etapa 9, `v0.11.1`). En
  la primera ejecución de «Replicación y fallos», el kernel de `client-1` mató el `get` de 1 GiB por falta de
  memoria (573 MB de memoria anónima en una t3.micro de 908 MB), sin mensaje de error. Con todos los nodos el
  pico es de unos 280–330 MiB; con uno caído pasaba de 500 MiB. Causa: en gRPC la llamada de lectura que
  falla se lanza a sí misma como excepción, y su traza retiene los marcos que la contienen. Ese ciclo solo lo
  libera el recolector cíclico, que se dispara por número de objetos y no por bytes, así que cada réplica
  fallida retenía el bloque de 16 MiB leído después. Se rompe el ciclo borrando la traza al capturar el
  error; una prueba con el recolector cíclico desactivado lo detecta (retenía 12 MiB con bloques de 1 MiB).
  En local, con un nodo parado, el pico pasa de 501–522 MiB a 304–331 MiB.
- **2026-11-07 · El hilo de latidos del nodo de datos moría con un error del líder** (etapa 7, `v0.9.1`). Al
  restaurar los metadatos, un líder que se paraba respondió `UNKNOWN` a `ReportBlocks` (su canal con etcd ya
  estaba cerrado). La excepción salió del bucle y el hilo de latidos murió en los cinco nodos de datos: el
  proceso seguía en marcha, pero el nuevo líder nunca los vio vivos y `get` falló con `BLOCK_LOST`. Puede pasar
  en cualquier parada del líder, no solo al restaurar. Ahora el bucle registra cualquier error y reintenta
  (`fix(datanode)`); en la repetición el mismo error llegó a tres nodos y siguieron funcionando.
- **2026-11-07 · Restaurar una copia hace retroceder las revisiones de etcd** (etapa 7, ADR 0035). La época
  del líder es una revisión de etcd, y los nodos de datos descartan épocas menores que la mayor que ya vieron.
  Restaurar una copia antigua daría al nuevo líder una época menor y los nodos de datos lo rechazarían.
  `deploy.sh restore` usa `etcdutl snapshot restore --bump-revision 1000000000 --mark-compacted`; tras la
  restauración, el líder tuvo la época 2 000 000 252.
- **2026-11-07 · Las 9 instancias se instalaron como `client-1`** (etapa 7). En `deploy.sh`, el bucle de
  `hosts_file` usaba la variable `host` sin declararla local, y en bash eso pisa la variable local de la
  función que llama. Cada instalación terminaba con el nombre, el `compose.yaml` y los secretos de `client-1`.
  Se detectó en la salida de la primera instalación, antes de cargar ningún dato; se corrigió y se reinstaló.
- **2026-11-07 · Un contenedor en marcha deja de ver sus secretos** (etapa 7). `install` sustituía el
  directorio de secretos (`rm -rf` y `mv`); un contenedor que no se recreaba seguía montando el directorio
  borrado. Ahora se cambia el contenido sin borrar el directorio.
- **2026-11-07 · Pruebas de seguridad que no probaban lo que decían** (etapa 7). Al pasar las contraseñas a
  `client-1`, la contraseña nueva de `useradd` llegaba vacía y la CLI fallaba sin llamar al servidor. Y el
  bloqueo por intentos fallidos, probado con un proceso por intento (unos 3 s cada uno), aceptó una vez la
  contraseña correcta cuando debía estar bloqueada; lo más probable es que pasaran los 30 s, pero no se guardó
  la hora de cada intento. Repetido a mano con la hora, el bloqueo se cumplió. Las dos pruebas se rehicieron y
  la evidencia es la tercera ejecución (`evidencias/2026-11-07-seguridad/README.md`).
- **2026-11-07 · Avisos de etcd en AWS** (etapa 7). «simple token is not cryptographically signed» se refiere
  a los tokens de los usuarios propios de etcd, que no se usan: los clientes de etcd se autentican con su
  certificado. «Running http and grpc server on single port» es informativo. Ninguno afecta al sistema.
- **2026-11-07 · Sin certificado, el servidor gRPC cierra la conexión sin alerta** (etapa 7). Con TLS 1.3 el
  cliente da la negociación por terminada antes de que el servidor compruebe su certificado; después, el
  servidor cierra la conexión y `openssl s_client` informa de «unexpected eof» en lugar de una alerta TLS.
- **2026-11-06 · Memoria de la primaria con escrituras simultáneas** (etapa 3). Con 8 escrituras a la vez,
  el pico de memoria del proceso tenía una mediana de 257 MiB (246–269, 5 repeticiones), por las arenas de
  `malloc` de glibc que crea cada hilo. Con `MALLOC_ARENA_MAX=2` en la imagen base baja a 167 MiB, sin
  perder tasa de transferencia (unos 200 MB/s en local). Una primera medición con `docker stats` daba más,
  porque incluye la caché de páginas de los bloques escritos; se midió con `VmHWM` del proceso.
- **2026-11-07 · Reparto desigual de réplicas en local** (etapa 5). En el `put` de 1 GiB, los 5 nodos
  recibieron 22, 22, 57, 51 y 40 réplicas. En local comparten el mismo disco: los que enviaron su latido
  después de crear el archivo de 1 GiB informaron 1 GiB menos libre, y la ubicación por espacio libre
  (§4.3) les dio menos bloques. En AWS cada nodo tiene su volumen; hay que comprobar el reparto allí
  (etapa 7).
- **2026-11-07 · Una prueba que pasaba sin probar lo que decía** (etapa 5). La prueba de un `put` con un
  nodo de datos caído pasaba, pero en los logs el nodo caído solo era secundaria: el quórum W = 2 bastaba y
  el cliente nunca repetía un bloque. Se separó en dos pruebas, y la de repetir bloques tira 2 de 4 nodos
  y comprueba en el log que el cliente reserva de nuevo.
- **2026-11-07 · Recuperación lenta de los nodos de datos tras caer el líder** (etapa 4). En el entorno local,
  al tirar el servidor de metadatos líder junto con su miembro de etcd, el nuevo líder se elegía en unos 8 s,
  pero los nodos de datos tardaban unos 14 s en volver a contar como vivos: cada intento contra el líder
  muerto agotaba un plazo de 5 s y luego esperaba el latido siguiente (3 s). Con un plazo de 2 s y un
  reintento a 1 s tras un fallo, la primera carga se confirma a los 5,0, 8,9 y 5,9 s de la caída (3 rondas,
  versión 0.6.1.dev, local). La explicación de los ~8 s hasta el nuevo líder (elección de etcd y espera al
  TTL de 5 s de la clave del líder) no está comprobada; E7 lo medirá en AWS separando cada parte.
- **2026-11-07 · Fallo en `etcd-sdk-python`** (etapa 4, ADR 0041). Su capa de alto nivel rellena
  `min_mod_revision` cuando se pide `min_create_revision` o `max_create_revision`. Se descartó a favor de un
  cliente propio sobre un subconjunto de los `.proto` de etcd.
- **2026-11-07 · Fallo intermitente en las pruebas del nodo de datos** (etapa 4). Una vez, de unas diez
  ejecuciones, una prueba falló al arrancar un servidor. La hipótesis, no confirmada, es que otro proceso
  tomó el puerto entre que la prueba lo reservaba y el servidor lo ocupaba; las pruebas ahora reintentan con
  otro puerto.
- **2026-11-06 · Versión en las etiquetas de imagen** (etapa 3). La versión entre releases lleva `+`
  (`0.2.1.dev6+gfe3854f`), que Docker no admite en una etiqueta. `scripts/get-version.sh --image` la da
  con `-`; en los releases la versión no lleva `+` y la etiqueta coincide con ella (ADR 0037).
