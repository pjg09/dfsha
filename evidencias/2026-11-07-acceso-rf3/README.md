# Acceso RF3: read() y write() con la semántica declarada

- **Fecha:** 2026-11-07
- **Commit y versión:** `91d8595` · v0.10.0 (imágenes `0.10.0` en ECR)
- **Entorno:** aws · las pruebas salen de `client-1`, con bloques de 16 MiB
- **Cubre:** prueba mínima «Acceso RF3» de §5.2
- **Resultado esperado:** fase I §7. Granularidad de byte en la interfaz y de bloque por dentro (§7.1). Los cuatro modos de la Tabla 22, con copia en escritura: cada escritura crea bloques nuevos solo para los índices que cambian y reutiliza los demás. Consistencia de apertura-cierre con las garantías G2, G3 y G4 de la Tabla 23.
- **Resultado obtenido:** coincide.
  - **Contenido:** las cinco escrituras (creación, anexado, dos modificaciones parciales y reemplazo) dejan un archivo cuyo SHA-256 coincide con un modelo local en el que se aplicó lo mismo.
  - **Bloques nuevos y reutilizados:**
    - Anexado: crea el último bloque, que no estaba lleno, y uno nuevo; reutiliza los demás.
    - Modificación que cruza los bloques 0 y 1: reescribe solo esos dos.
    - Escritura más allá del final: reescribe el último bloque y crea el siguiente; el hueco queda con ceros.
    - Reemplazo: todo nuevo.
  - **Garantías:**
    - G4: un `open()` durante una escritura sin confirmar ve la versión anterior.
    - G3: quien ya tenía el archivo abierto sigue leyendo su versión, entera, después de la confirmación.
    - G2: un `open()` posterior ve la versión confirmada.
  - **Línea de órdenes:** `read` con offset y longitud, `write` (parcial) y `append` dan los resultados esperados.

## Comandos
```bash
evidencias/2026-11-07-acceso-rf3/ejecutar.sh > evidencias/2026-11-07-acceso-rf3/salida.txt 2>&1
```

`rf3.py` se ejecuta dentro del contenedor `client-1` con la biblioteca del cliente. La contraseña de `pedro` le llega por la entrada estándar y no aparece en la salida.

## Archivos
- `ejecutar.sh`: la prueba.
- `rf3.py`: escrituras con la biblioteca, comparadas con el modelo local, y comprobación de G2 a G4.
- `salida.txt`: salida completa.
