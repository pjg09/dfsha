# 0016 · Tamaño de bloque de 16 MiB, configurable

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF1, RNF4, RNF5; C19, C20, C28

## Contexto
El tamaño de bloque es una decisión de granularidad (C19). HDFS usa 64 MB en la versión 1.2.1 y 128 MB en
las posteriores, porque está pensado para archivos de GB o TB. DFSha trabaja en otras condiciones:
- discos de 8 GiB más un volumen de datos, y 908 MiB de RAM (C28);
- archivos de prueba de entre 100 MiB y 1 GiB;
- copia en escritura (ADR 0009), que amplifica la modificación parcial en proporción al tamaño de bloque.

## Opciones consideradas
1. **4 MiB.** Reparto muy fino: 256 bloques por GiB, con más RPC y más metadatos.
2. **16 MiB.** 64 bloques por GiB.
3. **64 MiB.** 16 bloques por GiB: un archivo pequeño se reparte mal entre 5 nodos de datos, y una
   modificación parcial reescribe 64 MiB.

## Decisión
- `block_size_bytes` = 16 MiB (16 777 216) por defecto, configurable en el clúster.
- Cada archivo guarda el tamaño de bloque con el que se creó, para que cambiar la configuración no afecte
  a los archivos ya existentes.
- El último bloque puede ser más pequeño.
- Los bloques se transfieren en mensajes de 1 MiB (ADR 0019): un bloque nunca está entero en memoria.

## Consecuencias
- **Ejemplo:** un archivo de 1 GiB tiene 64 bloques y 192 réplicas, unas 38 por nodo de datos (≈ 614 MiB por nodo).
- **Se pierde:** hay más peticiones por GiB que con 64 MiB.
- **Medición:** se comparan 4, 16 y 64 MiB (ADR 0028).
