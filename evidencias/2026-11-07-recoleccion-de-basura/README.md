# Recolección de basura de bloques

- **Fecha:** 2026-11-07
- **Commit y versión:** `91d8595` · v0.10.0 (imágenes `0.10.0` en ECR); líder `metadata-3`
- **Entorno:** aws · los cinco nodos de datos, tras las evidencias de acceso RF3 y de concurrencia
- **Cubre:** escrituras interrumpidas y recolección de basura de la etapa 8 (fase I §8.4 y §9.3)
- **Resultado esperado:** los bloques que no pertenecen a ninguna versión viva ni a una escritura en curso con arrendamiento vigente se borran. Eso incluye los de escrituras abortadas o con el arrendamiento caducado, y los de versiones sustituidas hace más de 10 min. Los bloques vivos no se tocan.
- **Resultado obtenido:** coincide.
  - **Antes:** a las 07:26:13 UTC, al terminar las pruebas de concurrencia, había 270 réplicas en disco (53, 55, 53, 55 y 54), contadas en la sesión con la misma orden que usa `comprobar.sh`.
  - **Borrados:** el líder ordenó borrar 3 réplicas a las 07:25, de escrituras con el arrendamiento caducado, y 57 a las 07:35, de versiones sustituidas cuyo periodo de gracia había terminado (`recuento-07-43.txt`).
  - **Después:** quedan 213 réplicas, exactamente las de la versión vigente de los cuatro archivos (71 bloques × 3).
  - **Nada vivo se borró:** `/grande.bin` (1 GiB) se lee con el mismo SHA-256 que antes, y los otros tres archivos se leen enteros.

## Comandos
```bash
for h in 1 2 3 4 5; do deploy/aws/run.sh ssh datanode-$h "sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' | wc -l"; done
evidencias/2026-11-07-recoleccion-de-basura/comprobar.sh > evidencias/2026-11-07-recoleccion-de-basura/salida.txt 2>&1
```

La primera orden se ejecutó a las 07:26 y otra vez a las 07:42, junto con los logs del líder (`recuento-07-43.txt`).

`salida.txt` es la tercera ejecución de `comprobar.sh`, y las dos anteriores no sirven como evidencia:
- **Primera ejecución:** guardaba las copias con un nombre mal formado.
- **Segunda ejecución:** el disco raíz de `client-1` se había llenado con las copias de 1 GiB que fueron dejando las pruebas. El `get` falló, y `sha256sum` mostró el hash de la copia anterior.

Se borraron esas copias, y ahora el script muestra el espacio libre antes de leer y borra sus copias al terminar.

## Archivos
- `comprobar.sh`: réplicas en disco frente a las esperadas, y lectura de los archivos vivos.
- `recuento-07-43.txt`: recuento de las 07:42 y las órdenes de borrado del líder.
- `salida.txt`: salida de `comprobar.sh`.
