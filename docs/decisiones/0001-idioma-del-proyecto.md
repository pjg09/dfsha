# 0001 · Código en inglés, documentación en español

- **Estado:** Aceptada
- **Fecha:** 2026-10-21
- **Requisitos relacionados:** ninguno directo; afecta a todo el proyecto

## Contexto
El proyecto se evalúa en español: documento de la fase I, informe, vídeo y defensa oral. Al mismo
tiempo, el código usa librerías y protocolos con API en inglés (gRPC, FastAPI/Flask, la biblioteca
estándar de Python), y el enunciado ya nombra en inglés las primitivas de RF1–RF3 (`open`, `read`,
`write`, `lock`, `put`/`get`, `ls`, `mkdir`…). Sin una regla, el código acaba mezclando idiomas
(`get_bloque_by_nodo`) y con identificadores sin tildes (`tamano`).

## Opciones consideradas
1. Todo en español, código incluido.
2. Todo en inglés, documentación incluida.
3. Código en inglés y documentación en español.

## Decisión
Opción 3. Identificadores, códigos de error y nombres técnicos en inglés y en ASCII. Comentarios,
docstrings, mensajes al usuario, logs, documentación y descripciones de commit en español. El detalle
está en [`convenciones.md` §1](../convenciones.md#1-idioma).

## Consecuencias
- El código es coherente con las librerías y con los nombres que da el enunciado.
- Hace falta una correspondencia fija entre el término en español y el identificador en inglés,
  para que en la defensa el documento y el código hablen de lo mismo. Eso se resuelve con el
  glosario (ADR 0002).
