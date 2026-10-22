# 0002 · Glosario fijo y convención de nombres por tipo de artefacto

- **Estado:** Aceptada
- **Fecha:** 2026-10-21
- **Requisitos relacionados:** todos; especialmente la defensa oral (§5.3 del enunciado)

## Contexto
El repositorio va a contener artefactos muy distintos: documentos, contratos gRPC, código Python,
configuración, despliegue en Docker y AWS, pruebas, experimentos y evidencias. Cada ecosistema tiene
su propia convención, y además un mismo concepto tiene sinónimos que se cuelan con facilidad: bloque,
*chunk*, fragmento. En español hay además choques concretos: «bloqueo» se confunde con «bloque», y
«rendimiento» con «tasa de transferencia».

## Opciones consideradas
1. Seguir la convención de cada herramienta sin fijar los términos del dominio.
2. Fijar los términos del dominio en un glosario y la forma de cada artefacto en una sola guía.

## Decisión
Opción 2:
- [`glosario.md`](../glosario.md) es la fuente única de términos: el término en español, su
  identificador en inglés y los sinónimos prohibidos.
- [`convenciones.md`](../convenciones.md) fija la forma de cada tipo de artefacto: PEP 8 en Python,
  la guía de estilo de Protocol Buffers en gRPC, `kebab-case` en ficheros, la unidad como sufijo en
  las magnitudes y los verbos canónicos.

En los términos, se eligen los neutros frente a los de HDFS (`metadata` en vez de `namenode`), para
que el diseño no parezca una copia y para poder citar HDFS sin ambigüedad. En español, «cerrojo»
sustituye a «bloqueo».

## Consecuencias
- El documento de diseño, el código y los diagramas usan las mismas palabras.
- Cada término nuevo exige añadirlo antes al glosario. Es un pequeño coste para mantener la coherencia.
- Los términos marcados **(D)** no presuponen el diseño: se usan solo si el ADR correspondiente
  adopta el mecanismo.
