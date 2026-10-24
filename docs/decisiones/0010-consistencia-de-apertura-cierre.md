# 0010 · Consistencia de apertura-cierre para `read()` y `write()`

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RF3, RNF3, RNF5, §7; C2, C11, C20

## Contexto
§7 exige garantías de consistencia comprobables: cuándo se confirma una escritura y qué pueden leer los
demás clientes. Con el ADR 0009, cada escritura confirmada es una versión de archivo nueva.

## Opciones consideradas
1. **Linealizable a nivel de byte.** Cada `read()` ve la última escritura de cualquier cliente. Obliga a
   consultar al servidor de metadatos en cada lectura, que pasa a ser el cuello de botella (C20).
2. **Eventual.** Los lectores pueden ver versiones antiguas sin límite de tiempo. Es difícil de comprobar
   y no responde a §7.
3. **Apertura-cierre** (*close-to-open*, como AFS y NFS). `open()` fija la versión que se lee, y las
   escrituras se vuelven visibles cuando se confirman al cerrar.

## Decisión
Opción 3, con estas garantías:
- **G1. Cuándo se confirma.** Una escritura está confirmada cuando `close()` devuelve OK. En ese momento,
  la versión nueva está en los metadatos replicados (ADR 0014) y cada bloque tiene al menos W réplicas (ADR 0012).
- **G2. Qué ve un `open()` posterior.** Todo `open()` posterior a la confirmación lee esa versión o una más reciente.
- **G3. Qué ve un lector que ya tenía el archivo abierto.** Sigue viendo la misma versión, completa,
  aunque otro cliente confirme otra mientras tanto.
- **G4. Qué no se ve nunca.** Una versión no confirmada o una mezcla de dos versiones.

`read(handle, offset, size_bytes)` funciona en cualquier `offset` y no toma cerrojo.

## Consecuencias
- **Se gana:**
  - Las cuatro garantías se pueden comprobar con pruebas (§5.2, prueba de consistencia).
  - Las lecturas no consultan los metadatos en cada `read()`.
- **Se pierde:**
  - Un cliente no ve lo que escribe otro hasta que este cierra y él vuelve a abrir.
  - Un lector que mantiene el archivo abierto mucho tiempo lee una versión antigua. Esa versión se
    conserva durante el periodo de gracia (ADR 0025); si vence, `read()` falla con `FAILED_PRECONDITION`
    y el motivo `FILE_VERSION_EXPIRED`.
- **Requisito para el ADR 0014:** G2 exige que las lecturas de metadatos sean linealizables.
