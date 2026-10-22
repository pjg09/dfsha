# 0004 · Conventional Commits y versionado semántico con release automático

- **Estado:** Aceptada
- **Fecha:** 2026-10-21
- **Requisitos relacionados:** §5.3 del enunciado (repositorio con contribuciones identificables e instrucciones reproducibles)

## Contexto
Las versiones se van a gestionar con una herramienta de release automático, que calcula la siguiente
versión y el changelog a partir de los mensajes de commit. Para eso los mensajes tienen que seguir un
formato que la herramienta sepa interpretar. Además, el historial forma parte de la evidencia del
trabajo y hay que poder señalar exactamente qué se entregó en cada fase.

## Opciones consideradas
1. Mensajes libres y versiones manuales.
2. Conventional Commits, SemVer y etiquetas `vX.Y.Z` creadas por la herramienta.

## Decisión
Opción 2, con el detalle de [`convenciones.md` §6](../convenciones.md#6-git-y-versiones):
- Formato `<tipo>(<ámbito>): <descripción en español>`, con una lista cerrada de tipos y ámbitos.
  Los cambios incompatibles se marcan con `!` o con `BREAKING CHANGE:`.
- Las etiquetas `vX.Y.Z` y el `CHANGELOG.md` los produce solo la herramienta.
- Serie `0.y.z` durante el desarrollo; `1.0.0` en la entrega de la fase II.
- Las entregas se marcan con etiquetas fuera de SemVer: `entrega-fase-1` y `entrega-fase-2`.

## Consecuencias
- Un commit mal formado no cuenta para la versión. La herramienta lo ignora sin avisar, así que el
  formato hay que cuidarlo desde el primer commit.
- El commit inicial (`Initial commit`) queda fuera del formato y la herramienta lo ignora.
- **Pendiente:** elegir y configurar la herramienta, y confirmar con ella el formato exacto de las
  etiquetas y cómo trata la serie `0.y.z`.
