# Carga y recuperación de un archivo de 1 GiB, con la versión final

- **Fecha:** 2026-11-08, de 04:35 a 04:37 UTC
- **Commit y versión:** imágenes `v0.13.1` (`17c5dbd`), la versión final de la etapa 10; scripts de `32c0dba`
- **Entorno:** aws · `metadata-1` a `metadata-3` (t3.small), `datanode-1` a `datanode-5` (t3.micro, volumen gp3 de 10 GiB cifrado), `client-1` (t3.small, ADR 0045); `us-east-1a`. Configuración por defecto, sin los parámetros de los experimentos.
- **Cubre:** prueba mínima «Carga y recuperación» de §5.2, repetida con la versión final (plan de la fase II, etapa 10). La primera ejecución, con la `v0.9.0`, está en [`2026-11-07-carga-y-recuperacion`](../2026-11-07-carga-y-recuperacion/).
- **Resultado esperado:** el archivo se divide en bloques de 16 MiB, cada uno con 3 réplicas en nodos de datos distintos (fase I §4.3 y §8), y el archivo recuperado es idéntico al original (mismo SHA-256).
- **Resultado obtenido:** coincide.
  - **Reparto:** el clúster ya tenía datos (243 réplicas: 45, 60, 57, 57 y 24). Tras la carga hay 435, es decir, las 192 de los 64 bloques nuevos: 43, 26, 30, 30 y 63 por nodo. `/grande.bin` pasa a la versión 2, y las réplicas de la versión 1 siguen en disco durante el periodo de gracia de 10 min.
  - **Tamaño:** cada réplica de 16 MiB mide 16 777 244 bytes, 16 MiB más los 28 bytes del nonce y la etiqueta de AES-GCM.
  - **Hash:** `get` devuelve el mismo SHA-256 (`adfb3af2…58c41811`), y `cmp` confirma que los dos archivos son idénticos.
  - **Tiempos:** `put` en 7,9 s según la CLI (137 MB/s), y 11,0 s medidos desde la máquina de administración. `get` en 8,7 s (124 MB/s) y 12,1 s. No es una medición de rendimiento: esa es E1.
  - **Memoria:** el pico de memoria del proceso de cada nodo de datos (`VmHWM`) va de 98 a 121 MiB, con 465 a 504 MiB disponibles en cada t3.micro.

## Comandos
Desde la raíz del repositorio, con el script de la primera ejecución, sin cambios:

```bash
evidencias/2026-11-07-carga-y-recuperacion/ejecutar.sh > evidencias/2026-11-08-carga-y-recuperacion/salida.txt 2>&1
```

## Archivos
- `salida.txt`: salida completa.
