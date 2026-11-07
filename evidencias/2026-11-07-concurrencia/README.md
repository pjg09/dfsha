# Concurrencia: escenario 1, dos procesos escriben el mismo bloque a la vez

- **Fecha:** 2026-11-07
- **Commit y versión:** `91d8595` · v0.10.0 (imágenes `0.10.0` en ECR)
- **Entorno:** aws · procesos `dfsha shell` reales y simultáneos en `client-1`; `/datos.bin` de 4 bloques de 16 MiB
- **Cubre:** prueba mínima «Concurrencia» de §5.2, escenario 1 de la fase I §11.1 y la Tabla 24
- **Resultado esperado:**
  - El segundo escritor recibe `ABORTED` + `LOCK_CONFLICT` al momento, sin esperar.
  - Si reintenta tras la confirmación del primero partiendo de la versión que abrió, recibe `VERSION_CONFLICT`.
  - Con bloques distintos, los dos confirman.
  - Un escritor que muere pierde su arrendamiento en 30 s como máximo; si reaparece, recibe `LEASE_EXPIRED`.
  - Nunca queda una mezcla de las dos escrituras.
- **Resultado obtenido:** coincide.
  - **A, mismo bloque (pasos 1 a 4):** P2 recibe `LOCK_CONFLICT` mientras P1 tiene el arrendamiento. P1 confirma la versión 2. P2 reintenta, obtiene el arrendamiento y al cerrar recibe `VERSION_CONFLICT`. Vuelve a abrir la versión 2, lee el cambio de P1 y escribe el suyo a continuación: el bloque queda `P1-cambia-el-bloque-3+P2`, versión 3.
  - **B, bloques distintos:** P2 (bloque 3) confirma la versión 4 y P1 (bloque 0), que abrió la versión 3, la 5. Se conservan los dos cambios.
  - **C, P1 muere:** `kill -9` al proceso de P1 mientras tiene el arrendamiento del bloque 3. P2 recibe `LOCK_CONFLICT` cuatro veces y escribe 27 s después, sin intervención; el arrendamiento caduca 30 s después de la última renovación de P1.
  - **D, P1 reaparece:** deja de renovar y confirma pasados 35 s: `ABORTED` + `LEASE_EXPIRED`, y el bloque 3 no cambia.

## Comandos
```bash
evidencias/2026-11-07-concurrencia/ejecutar.sh > evidencias/2026-11-07-concurrencia/salida.txt 2>&1
```

`ejecutar.sh` lanza cada proceso como un `dfsha shell` en `client-1`. Un alimentador le envía las órdenes con esperas entre ellas y anota la hora de cada una (`envía:`); debajo va lo que respondió el proceso. La parte D usa la biblioteca (`reaparece.py`), porque un proceso de la CLI no puede dejar de renovar sin morir.

Dos líneas de la salida no son errores de la prueba:
- En C, el alimentador de P1 envía `close` a las 07:25:05 a un proceso que ya no existe; no tiene efecto.
- En D, «No se pudo abortar la escritura: El arrendamiento caducó» es el cliente intentando descartar su escritura después del rechazo. Sus bloques quedan huérfanos y los borra la recolección de basura.

## Archivos
- `ejecutar.sh`: la prueba.
- `reaparece.py`: variante del escritor que reaparece tras caducar su arrendamiento.
- `salida.txt`: salida completa.
