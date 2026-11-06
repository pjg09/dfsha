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

## Problemas encontrados y cómo se resolvieron

- **2026-11-06 · Memoria de la primaria con escrituras simultáneas** (etapa 3). Con 8 escrituras a la vez,
  el pico de memoria del proceso tenía una mediana de 257 MiB (246–269, 5 repeticiones), por las arenas de
  `malloc` de glibc que crea cada hilo. Con `MALLOC_ARENA_MAX=2` en la imagen base baja a 167 MiB, sin
  perder tasa de transferencia (unos 200 MB/s en local). Una primera medición con `docker stats` daba más,
  porque incluye la caché de páginas de los bloques escritos; se midió con `VmHWM` del proceso.
- **2026-11-06 · Versión en las etiquetas de imagen** (etapa 3). La versión entre releases lleva `+`
  (`0.2.1.dev6+gfe3854f`), que Docker no admite en una etiqueta. `scripts/get-version.sh --image` la da
  con `-`; en los releases la versión no lleva `+` y la etiqueta coincide con ella (ADR 0037).
