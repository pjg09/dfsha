# 0006 · Tabla de cambios entre fases en lugar de la matriz comparativa

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §2, §5.1 y §5.3 del enunciado; aclaraciones A1 y A2

## Contexto
§5.1 pide una matriz comparativa de las propuestas individuales y un registro de las decisiones del
equipo. §5.3 pide que el informe final explique los «cambios frente a los diseños individuales». El
proyecto es individual (A1) y el profesor dispensó la matriz (A2): no hay propuestas que comparar. Lo que
sí puede pasar es que la implementación de la fase II se aparte del diseño de la fase I, y §2 pide
registrar «qué decisiones cambian y por qué».

## Opciones consideradas
1. **No hacer nada.** Lo permite A2, pero la sección de cambios de §5.3 queda vacía y se pierde la
   trazabilidad entre el diseño calificado en la fase I y lo implementado.
2. **Una matriz entre alternativas de diseño.** Repite las «Opciones consideradas» que ya tiene cada ADR.
3. **Tabla de cambios de la fase I a la fase II**, alimentada por los ADR.

## Decisión
Opción 3. El informe de la fase II incluye una tabla con las columnas *Decisión de la fase I · Qué cambió
en la fase II · Por qué · ADR*. Sus filas salen de los ADR que pasaron a `Sustituida por NNNN` después de
la etiqueta `entrega-fase-1`.

## Consecuencias
- Cumple §2 y la sección de cambios de §5.3 sin un artefacto nuevo: basta con mantener al día el registro de decisiones.
- **Límite:** la tabla solo recoge lo que pasó por un ADR. Un cambio de diseño hecho directamente en el
  código no aparecería. Regla que se deriva: **ningún cambio de diseño sin su ADR**.
