# 0025 · Espacio de nombres por usuario y operaciones de RF1

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RF1, RF2, RF3; aclaración A7

## Contexto
RF1 pide `ls`, `cd`, `mkdir`, `rmdir`, `rm` «y operaciones equivalentes», con un espacio propio para cada
usuario. Hay que decidir dónde vive el directorio actual y qué pasa con los bloques de lo que se borra o
se sustituye, sabiendo que los lectores abiertos siguen viendo su versión (ADR 0010).

## Opciones consideradas
**Directorio actual (`cd`):**
1. **En el servidor.** Exige guardar y replicar el estado de cada sesión.
2. **En el cliente.** El cliente guarda el directorio actual y envía rutas absolutas.

**Liberación del espacio:**
- **Borrado inmediato.** Rompe a los lectores que tienen abierta la versión borrada.
- **Borrado diferido con periodo de gracia.**

## Decisión
**Directorio actual:** en el cliente (opción 2). Cada usuario tiene su espacio de nombres con raíz `/`, y
al servidor solo llegan rutas absolutas.

**Operaciones:**

| Operación | Comportamiento | Error |
|---|---|---|
| `ls` | Lista un directorio | — |
| `mkdir` | Crea un solo nivel | `NOT_FOUND` si no existe el directorio padre |
| `rmdir` | Borra solo un directorio vacío | `FAILED_PRECONDITION` + `DIRECTORY_NOT_EMPTY` |
| `rm` | Borra un archivo | `ABORTED` + `LOCK_CONFLICT` si tiene un arrendamiento de escritura activo |
| `mv` | Mueve o renombra un archivo o directorio dentro del espacio del usuario, de forma atómica | — |
| `put` / `get` (RF2) | Creación o reemplazo completo, y lectura completa, sobre las primitivas de RF3 | — |

**Borrado y versiones sustituidas:**
- Dejan de ser visibles en cuanto se confirma el `rm` o la versión nueva.
- Sus bloques se borran pasado un periodo de gracia de 10 min.
- Si un lector sigue con esa versión abierta después del periodo, `read()` devuelve `FAILED_PRECONDITION` + `FILE_VERSION_EXPIRED`.

## Consecuencias
- **Se gana:**
  - El servidor no guarda estado de sesión.
  - Borrar un archivo no rompe a sus lectores durante el periodo de gracia.
- **Se pierde:**
  - El espacio no se libera al momento.
  - Un lector que mantiene una versión abierta más de 10 min puede fallar.
- **Fuera de alcance** (RF1 no lo exige): papelera y recuperación de borrados, enlaces y cuotas.
- **Cambia la convención:** `mv` se añade al glosario y a la lista de comandos de `convenciones.md` §3.
