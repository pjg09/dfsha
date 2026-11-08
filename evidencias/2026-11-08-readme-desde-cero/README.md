# El README seguido desde cero

- **Fecha:** 2026-11-08, de 06:11 a 06:31 UTC
- **Commit y versión:** clon limpio de GitHub en `11da6a5` (después de `v0.13.2`, solo con commits de documentación; el código de la aplicación es el mismo). `deploy.sh all` construyó las imágenes `0.13.3.dev3-g11da6a5`; al terminar se volvió a instalar la `v0.13.2`.
- **Entorno:** la máquina de administración para la instalación, las pruebas y el entorno local; aws para el despliegue, en una cuenta sin instancias, volúmenes ni grupos del proyecto tras `deploy.sh down`.
- **Cubre:** la revisión del `README.md` desde cero de la etapa 11 (plan de la fase II) y las «instrucciones reproducibles de instalación, configuración y ejecución» de §5.3.
- **Resultado esperado:** cada orden del README, ejecutada tal como está escrita en un clon sin secretos, hace lo que el README dice.
- **Resultado obtenido:** todo funciona salvo dos fallos del README y uno de `deploy.sh status`, que se corrigieron:
  1. **Instalación y pruebas:** `uv sync --locked`, `uv run pytest` (158 pruebas), `uv run pyright` (0 errores) y `generate-proto.sh` sin cambios en `dfsha/v1/`.
  2. **Entorno local:** los secretos, `docker compose up -d --build` y el alta de `pedro` funcionan. **Fallo 1:** el ejemplo carga `/data/archivo.bin`, pero ningún paso lo crea, y `put` y `get` fallan (`No such file or directory`). Con el archivo creado antes, la carga y la recuperación dan el mismo SHA-256. Los ejemplos de RF3 funcionan, y el modo interactivo también, con las órdenes por la entrada estándar. **Fallo 2:** el README decía que `unlock` libera el rango, pero con escrituras sin confirmar lo rechaza («Hay escrituras sin confirmar; usa close()»), como está diseñado. El texto no lo decía.
  3. **Despliegue en AWS:** `down` deja 0 instancias, 0 volúmenes y 0 grupos. `pki` y `deploy.sh all` construyen las imágenes, crean los recursos e instalan los 9 hosts sin intervención, en 6 min 19 s. **Fallo 3:** `deploy.sh status` también listaba las 9 instancias terminadas por `down`, que AWS muestra cerca de una hora: 18 filas en lugar de 9.
  4. **Cliente en AWS:** el alta de `pedro` funciona, y el `put` del README falla igual que en local (fallo 1). Con el archivo creado antes, la carga y la recuperación de 100 MiB dan el mismo SHA-256.
  5. **Carga y recuperación de 1 GiB** con el script de la prueba mínima: 64 bloques con 3 réplicas repartidas entre los cinco nodos (42 o 43 réplicas cada uno) y archivos idénticos.
  6. **Versión final:** de vuelta a la `v0.13.2`, los datos se leen con el mismo SHA-256.

## Correcciones
- **`README.md`:**
  - un paso que crea el archivo de prueba antes de `put`, en local y en AWS, y la comprobación del hash;
  - qué es `/data` en `client-1`;
  - la semántica de `unlock`;
  - la lista de órdenes que remite a las de RF3;
  - la copia de seguridad, tras cada cambio importante.
- **`deploy/aws/deploy.sh status`:** ya no lista las instancias terminadas (`6-status-corregido.txt`).

## Qué cambió en el clúster
- **El clúster es nuevo**, con secretos nuevos: otra CA, otros certificados y otra clave de envoltura. Los datos de las pruebas anteriores ya no están, incluidos los 6 528 directorios vacíos de E7 en `/bench`.
- **Las copias de seguridad de S3 anteriores a las 06:16 UTC** solo se pueden restaurar con los secretos antiguos, que quedaron guardados fuera del repositorio en la máquina de administración. La última hecha con ellos es `etcd-20261108T061405Z.db`, y la primera con los nuevos, `etcd-20261108T063023Z.db`.
- **El usuario `pedro`** del clúster nuevo tiene la contraseña de ejemplo del README («una-contraseña»), porque se siguió al pie de la letra. Para entrar hace falta además el certificado de un host del clúster (TLS mutuo, §10).

## Comandos
Desde un clon nuevo (`git clone git@github.com:pjg09/dfsha.git`), las órdenes de cada sección del README en su orden. La salida de cada una, con su código de salida, está en los archivos numerados. Hay tres diferencias con el texto del README:
- `docker compose logs -f` se cortó a los 8 s, porque no termina solo.
- `dfsha shell` recibió las órdenes por la entrada estándar en lugar de con `-it`.
- Antes del despliegue se ejecutó `deploy.sh down` para partir de una cuenta vacía.

## Archivos
- `1-instalacion-y-pruebas.txt`: `uv sync`, pruebas, pyright y regeneración de los `.proto`.
- `2-entorno-local.txt`: el entorno local y el cliente, como estaba el README y con la corrección.
- `3-despliegue-aws.txt`: `down`, la comprobación de que no queda nada, `pki`, `all` y `status`.
- `4-cliente-aws.txt`: el cliente en AWS, como estaba el README y con la corrección.
- `5-carga-y-recuperacion.txt`: la prueba de carga y recuperación de 1 GiB en el clúster nuevo.
- `6-status-corregido.txt`: `status` con la corrección.
