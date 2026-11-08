# Concurrencia, con la versión final

- **Fecha:** 2026-11-08, de 04:40:40 a 04:42:57 UTC
- **Commit y versión:** imágenes `v0.13.1` (`17c5dbd`), la versión final de la etapa 10; scripts de `32c0dba`
- **Entorno:** aws · `metadata-1` a `metadata-3` (t3.small), `datanode-1` a `datanode-5` (t3.micro, volumen gp3 de 10 GiB cifrado), `client-1` (t3.small, ADR 0045); `us-east-1a`. Configuración por defecto, sin los parámetros de los experimentos.
- **Cubre:** prueba mínima «Concurrencia» de §5.2, repetida con la versión final. La primera ejecución está en [`2026-11-07-concurrencia`](../2026-11-07-concurrencia/), con la explicación de cada parte.
- **Resultado esperado:** dos clientes sobre el mismo archivo y bloque se ordenan por los arrendamientos (fase I §11.1).
- **Resultado obtenido:** coincide, con la misma salida que la primera ejecución salvo las horas:
  - **A, mismo bloque:** P2 recibe `LOCK_CONFLICT` mientras P1 tiene el arrendamiento. P1 confirma la versión 2. P2 reintenta, y al cerrar recibe `VERSION_CONFLICT`. Vuelve a abrir la versión 2, lee el cambio de P1 y confirma la 3. El bloque 3 queda en «P1-cambia-el-bloque-3+P2».
  - **B, bloques distintos:** los dos confirman (versiones 4 y 5) y se conservan los dos cambios.
  - **C, P1 muere:** tras un `kill -9` a P1, P2 recibe `LOCK_CONFLICT` cuatro veces y escribe 27 s después, sin intervención: el arrendamiento caduca a los 30 s.
  - **D, P1 reaparece:** confirma pasados 35 s y recibe `ABORTED` + `LEASE_EXPIRED`.

## Comandos
```bash
evidencias/2026-11-07-concurrencia/ejecutar.sh > evidencias/2026-11-08-concurrencia/salida.txt 2>&1
```

## Archivos
- `salida.txt`: salida completa. Las dos líneas de la primera ejecución que no son errores de la prueba también aparecen aquí: el `close` a un proceso que ya no existe (C) y «No se pudo abortar la escritura» (D).
