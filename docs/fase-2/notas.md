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

## Problemas encontrados y cómo se resolvieron

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
