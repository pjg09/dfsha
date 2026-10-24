# 0009 · Bloques inmutables y versiones de archivo: semántica de `write()`

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RF3, RNF3, RNF5, §7; aclaración A7; C2, C3, C12

## Contexto
RF3 obliga a declarar si `write()` admite creación, reemplazo, anexado y modificación parcial. El objetivo
es no simplificar (A7), así que hay que admitir los cuatro modos. Pero admitir la modificación parcial
sobre bloques que cambian obliga a ordenar las escrituras entre réplicas y a resolver réplicas a medio
actualizar (C12).

## Opciones consideradas
1. **Solo creación y reemplazo** (*write-once-read-many*, como HDFS 1.x). Es lo más simple, pero es una
   simplificación de RF3 que habría que aprobar.
2. **Bloques mutables con modificación en el sitio.** La escritura parcial es barata, pero las réplicas
   de un bloque pueden quedar con contenidos distintos. Eso exige una réplica que ordene las escrituras,
   versiones por bloque y lecturas con quórum.
3. **Bloques inmutables con copia en escritura.** Toda escritura crea bloques nuevos y se confirma como
   una versión nueva del archivo.

## Decisión
Opción 3. `write()` admite los cuatro modos (`WriteMode`): creación, reemplazo, anexado y modificación
parcial en cualquier `offset`.

**Regla general:**
- Un bloque escrito no cambia nunca.
- Cada escritura confirmada produce una **versión de archivo** nueva, que es la lista ordenada de los
  `block_id` del archivo.

**Cada modo:**
- **Modificación parcial:** el cliente lee los bloques afectados, aplica el cambio y escribe bloques
  nuevos. Los bloques no afectados se reutilizan por referencia.
- **Anexado:** el último bloque, si no estaba lleno, se reescribe como un bloque nuevo, y después se
  añaden los bloques que hagan falta.
- **Reemplazo:** todos los bloques son nuevos.

## Consecuencias
- **Se gana:** las réplicas de un bloque son idénticas o no existen; nunca hay réplicas con contenido
  distinto. En eso se apoyan los ADR 0010, 0012, 0013 y 0018.
- **Se pierde:**
  - Hay amplificación de escritura: cambiar un byte reescribe un bloque entero (16 MiB, ADR 0016).
  - La modificación parcial cuesta una lectura y una escritura.
  - Las versiones sustituidas ocupan disco hasta la recolección de basura (ADR 0018 y 0025).
- **Términos nuevos en el glosario:** versión de archivo y copia en escritura.
