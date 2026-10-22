---
name: adr
description: Redacta un registro de decisión (ADR) de DFSha con la plantilla y numeración del repositorio, lo presenta para revisión y, al aprobarlo, lo guarda en docs/decisiones/ y actualiza el índice.
argument-hint: "<decisión o pregunta a decidir> (p. ej. «tamaño de bloque»)"
disable-model-invocation: true
---

# /adr — registrar una decisión

Decisión: `$ARGUMENTS`

El registro de decisiones cumple el §2 del enunciado («debe registrar qué decisiones cambian y por
qué»). Reglas completas en `docs/decisiones/README.md`.

## 1. Preparar
1. Lee `docs/decisiones/README.md` (reglas, índice y plantilla) y los ADR relacionados.
2. Lee lo que condiciona la decisión: `docs/enunciado.md` (requisitos RF/RNF y §7),
   `docs/consejos-diseno.md` (consejos C1–C30) y `docs/glosario.md`.
3. Si la decisión **cambia** un ADR aceptado, el nuevo ADR lo **sustituye**: los ADR aceptados no se editan.
4. Número: el mayor de `docs/decisiones/NNNN-*.md` + 1, con 4 cifras. Nombre del fichero:
   `NNNN-titulo-en-kebab.md`, en ASCII (sin tildes ni `ñ`).

## 2. Redactar
Usa la plantilla del índice, en español y en **una página como máximo**:

- **Estado:** `Propuesta` (solo el usuario la pasa a `Aceptada`).
- **Fecha:** la de hoy (`date +%F`).
- **Requisitos relacionados:** RF, RNF, secciones del enunciado y consejos (`C17`…) que la condicionan.
- **Contexto:** el problema y las fuerzas que obligan a decidir, con datos concretos.
- **Opciones consideradas:** al menos dos, con su coste real. Una opción de relleno no cuenta.
- **Decisión:** una o dos frases.
- **Consecuencias:** qué se gana, **qué se pierde o no se cubre** (el límite, consejo C1) y qué queda pendiente.

Términos del glosario. Si hace falta un término nuevo, propón añadirlo antes al glosario. No inventes
fuentes: si un dato no está comprobado, dilo.

## 3. Revisar y guardar
1. Muestra el ADR en la terminal y **espera** a que el usuario lo apruebe o lo corrija.
2. Al aprobarlo, crea el fichero y añade su fila al índice de `docs/decisiones/README.md`.
3. Si sustituye a otro, en el antiguo cambia **solo** la línea de estado a `Sustituida por NNNN`.
4. No hagas commit. Recuérdale al usuario que el ADR va en su propio commit
   `docs(adr): …`, antes de los commits que lo aplican (`CONTRIBUTING.md` §6.1), y que puede usar `/commit`.
