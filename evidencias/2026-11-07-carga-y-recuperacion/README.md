# Carga y recuperación de un archivo de 1 GiB

- **Fecha:** 2026-11-07
- **Commit y versión:** imágenes `v0.9.0` (`c82e0e1`) en ECR; despliegue con `deploy/aws/deploy.sh` de `57d91bc`
- **Entorno:** aws · `metadata-1` a `metadata-3` (t3.small), `datanode-1` a `datanode-5` (t3.micro, volumen gp3 de 10 GiB cifrado), `client-1` (t3.micro); `us-east-1a`
- **Cubre:** prueba mínima «Carga y recuperación» de §5.2
- **Resultado esperado:** el archivo se divide en bloques de 16 MiB, cada uno con 3 réplicas en nodos de datos distintos (fase I §4.3 y §8), y el archivo recuperado es idéntico al original (mismo SHA-256).
- **Resultado obtenido:** coincide.
  - 1 GiB en 64 bloques, con 192 réplicas repartidas entre los cinco nodos de datos: 39, 38, 39, 38 y 38. El reparto desigual que se vio en local (22 a 57, `docs/fase-2/notas.md`) no aparece con un volumen por nodo.
  - Cada réplica mide 16 777 244 bytes: 16 MiB más los 28 bytes del nonce y la etiqueta de AES-GCM.
  - `get` devuelve el mismo SHA-256 (`4993c4a8…66a4be1`), y `cmp` confirma que los dos archivos son idénticos.
  - `put`: 7,8 s según la CLI (137 MB/s), 11,6 s medidos desde la máquina de administración, que incluyen la consulta a AWS, SSH y el arranque del proceso. `get`: 7,9 s y 10,8 s. No es una medición de rendimiento: E1 la hará con repeticiones.
  - Pico de memoria del proceso de cada nodo de datos (`VmHWM`) desde su arranque, que incluye la carga: de 103 a 132 MiB, con unos 440 MiB disponibles en cada t3.micro. Ningún contenedor se reinició.

## Comandos
`ejecutar.sh`, desde la raíz del repositorio, con el clúster en marcha y el usuario `pedro` creado:

```bash
deploy/aws/deploy.sh images && deploy/aws/deploy.sh up && deploy/aws/deploy.sh install
NEW_PASSWORD_FILE=deploy/aws/secrets/pedro-password deploy/aws/run.sh dfsha admin useradd pedro
evidencias/2026-11-07-carga-y-recuperacion/ejecutar.sh > evidencias/2026-11-07-carga-y-recuperacion/salida.txt 2>&1
```

En esa ejecución fallaron dos pasos del script, que se corrigieron después:
- **El pico de memoria:** `pgrep -f` también encontraba la shell remota; ahora es `pgrep -xf`. La medición se repitió en cuanto se corrigió, con los mismos procesos, y está en `memoria.txt`.
- **El log del líder:** el patrón buscaba líneas que el líder no escribe con nivel INFO, así que el paso se quitó.

## Archivos
- `ejecutar.sh`: la prueba, ya corregida.
- `salida.txt`: salida completa de la ejecución, con los dos pasos fallidos tal como salieron.
- `memoria.txt`: pico de memoria de cada nodo de datos, medido tras la carga.
- `consola-ec2-instancias.png`: consola de EC2 con las 9 instancias en ejecución (tipos, zona y comprobaciones de estado). Captura de Pedro a las 06:27 UTC, del mismo clúster ya actualizado a `v0.9.1`, no del momento de la carga.
