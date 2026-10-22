# Registro de decisiones (ADR)

Cumple el §2 del enunciado: «debe registrar qué decisiones cambian y por qué». Cada decisión de
arquitectura o de proceso que no sea trivial tiene aquí un registro.

Reglas:
- Un fichero por decisión: `NNNN-titulo-en-kebab.md`, con numeración correlativa que nunca se reutiliza.
- Una decisión aceptada **no se edita**. Si cambia, se escribe un ADR nuevo que la sustituye, y la
  antigua pasa a `Sustituida por NNNN`. Así queda la historia de lo que cambió y por qué, que es
  justo lo que pide el enunciado.
- Estados posibles: `Propuesta`, `Aceptada`, `Sustituida por NNNN`, `Descartada`.

## Índice

| N.º | Decisión | Estado | Fecha |
|---|---|---|---|
| [0001](0001-idioma-del-proyecto.md) | Código en inglés, documentación en español | Aceptada | 2026-10-21 |
| [0002](0002-glosario-y-convencion-de-nombres.md) | Glosario fijo y convención de nombres por tipo de artefacto | Aceptada | 2026-10-21 |
| [0003](0003-nombres-de-hosts-y-recursos.md) | Nombres de hosts y de recursos de red y de AWS | Aceptada | 2026-10-21 |
| [0004](0004-commits-convencionales-y-versionado.md) | Conventional Commits y versionado semántico con release automático | Aceptada | 2026-10-21 |
| [0005](0005-semantic-release-en-cada-push.md) | semantic-release en cada push a `main`, empezando en 0.1.0 | Aceptada | 2026-10-21 |

## Plantilla

```markdown
# NNNN · Título

- **Estado:** Propuesta
- **Fecha:** AAAA-MM-DD
- **Requisitos relacionados:** RF…, RNF…

## Contexto
Qué problema o qué fuerza obliga a decidir.

## Opciones consideradas
1. …
2. …

## Decisión
Qué se decide, en una o dos frases.

## Consecuencias
Qué se gana, qué se pierde y qué queda pendiente.
```
