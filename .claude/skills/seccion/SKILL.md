---
name: seccion
description: Redacta en la terminal UNA sección del documento de diseño de la fase I de DFSha, cumpliendo la rúbrica, con elementos no textuales numerados y registro de fuentes, y se detiene a esperar revisión.
argument-hint: "<sección> (p. ej. «arquitectura» o «4.2 escenarios»); sin argumento, propone la estructura"
disable-model-invocation: true
---

# /seccion — una sección del documento de la fase I

Metodología elegida por el usuario (es la que recomienda el profesor): Claude propone el texto de
**una sección cada vez** y el usuario lo revisa contra sus apuntes y **decide qué escribe**. Claude no
escribe el documento final.

Sección pedida: `$ARGUMENTS`

## 0. Antes de escribir
Lee, si no lo has hecho en esta sesión:
- `docs/enunciado.md`, sobre todo §4 (fase I), §6 (rúbrica individual) y §7 (aclaraciones de alcance).
- `docs/fase-1/estado.md` (estructura y estado de cada sección) y `docs/fase-1/fuentes.md` (registro de fuentes).
- `docs/consejos-diseno.md`, `docs/glosario.md` y los ADR de `docs/decisiones/` relacionados con la sección.

**Si `docs/fase-1/estado.md` no existe**, todavía no hay estructura acordada. En ese caso no redactes
ninguna sección: propón la estructura del documento, con cada sección relacionada con sus actividades
de §4.1, escenarios de §4.2 y criterios de §6, y **espera** a que el usuario la apruebe. Cuando la
apruebe, crea `docs/fase-1/estado.md` con la tabla de estado (§4 de esta skill) y `docs/fase-1/fuentes.md`
vacío con su cabecera.

## 1. Cómo se redacta la sección
- **Solo la sección pedida**, en la terminal y en Markdown. No crees ni edites el documento de diseño.
- **Textos cortos, con el mínimo que exige el enunciado.** Sin párrafos de contexto ni observaciones
  que la rúbrica no pida.
- Cada decisión sigue **dato → concepto → consecuencia → límite** (consejo C1): qué se exige u
  observa, qué concepto lo explica, qué se gana y qué **no** cubre.
- Lo que el enunciado deja abierto se **declara explícitamente** (C2): semántica de `write()`,
  modelo de consistencia, qué significa «confirmar», qué pasa en cada fallo.
- Los términos salen de `docs/glosario.md` («bloque», «cerrojo», «servidor de metadatos»…).
- Las tablas van **en Markdown renderizado**, nunca dentro de un bloque de código.
- **Elementos no textuales** (diagrama, tabla de datos, ejemplo de mensaje, código, captura) se marcan
  en el punto exacto donde van:
  `[ELEMENTO N · Tipo — descripción de qué muestra y de dónde sale]`
  La numeración es **correlativa en todo el documento**: toma el siguiente número de `estado.md`.
- Si la sección exige una decisión de diseño que **no tiene ADR**, no la tomes en silencio: señálala
  y propón registrarla con `/adr` antes de darla por buena.

## 2. Fuentes
- Toda fuente que consultes (enunciado, libro, diapositivas, la base de conocimiento, internet,
  documentación de librerías) se anota **en el momento** en `docs/fase-1/fuentes.md`: qué es, qué se
  usó y en qué sección.
- **Nunca inventes una referencia.** Que no haya referencias es aceptable.
- Lo que solo se apoya en conocimiento general, sin fuente, se dice al usuario en las notas.

## 3. Al terminar
Después del texto, como mucho tres líneas de notas al usuario:
- elementos nuevos que hay que preparar (`ELEMENTO N…`);
- fuentes registradas;
- decisiones pendientes de ADR, si las hay.

Actualiza en `docs/fase-1/estado.md` la columna «Texto entregado» con la fecha (`date +%F`) y el
último número de elemento usado. Después **detente**. No pases a la siguiente sección hasta que el
usuario lo diga, y no menciones plazos ni el tiempo que queda.

Cuando el usuario diga que una sección está revisada, márcala en la columna «Revisada».

## 4. Formato de `docs/fase-1/estado.md`

```
# Fase I · estado del documento

Último elemento usado: ELEMENTO 0

| N.º | Sección | Alimenta (§4.1 / §4.2 / §6) | Texto entregado | Revisada |
|---|---|---|---|---|
```
