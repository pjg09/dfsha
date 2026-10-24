# Aclaraciones del profesor

Respuestas del profesor a las dudas sobre el [enunciado](enunciado.md). Completan el enunciado sin
modificarlo: `enunciado.md` sigue siendo la transcripción fiel del PDF oficial.

- **Registradas:** 2026-10-22. Las comunicó Pedro en la sesión de trabajo de ese día.
- **Autoridad:** junto con el enunciado, son la fuente de mayor rango del proyecto (ver el orden en
  `CLAUDE.local.md`). Si una aclaración contradice al enunciado, manda la aclaración porque es posterior.
- **Evidencia:** si alguna respuesta llegó por escrito (correo, Teams…), conviene guardar aquí la
  referencia. Las que se dieron de palabra quedan registradas solo en este documento.

Cada aclaración tiene un identificador (`A1`, `A2`…) para citarla en los ADR y en los documentos.

## Resumen y mapa

| Id. | Tema | Enunciado | Consejos | Decisiones |
|---|---|---|---|---|
| A1 | Proyecto individual | §2, §5, §6 | §9 (trampas) | [0006](decisiones/0006-registro-de-cambios-entre-fases.md) |
| A2 | Matriz comparativa | §5.1 | §9 (trampas) | [0006](decisiones/0006-registro-de-cambios-entre-fases.md) |
| A3 | Formato de entrega | §4.3 | — | [0029](decisiones/0029-especificacion-de-apis-en-la-fase-1.md) |
| A4 | Extensión del documento | §4.3 | — | [0029](decisiones/0029-especificacion-de-apis-en-la-fase-1.md) |
| A5 | Cifrado en reposo | RNF6 | C25, C27 | [0024](decisiones/0024-cifrado-en-reposo.md) |
| A6 | Alcance de RNF7 | RNF7, §4.2 (escenario 4) | C6, C7 | [0021](decisiones/0021-descubrimiento-y-resolucion-de-nombres.md) |
| A7 | Simplificaciones | RF3, §7 | C3, C12 | [0009](decisiones/0009-bloques-inmutables-y-versiones-de-archivo.md) y todas las de diseño |
| A8 | Documentación de referencia | — | C12, C16, C17 | [0012](decisiones/0012-replicacion-y-confirmacion-por-mayoria.md), [0014](decisiones/0014-metadatos-replicados-con-raft.md), [0018](decisiones/0018-deteccion-de-fallos-y-re-replicacion.md) |

## A1 · El proyecto es individual

**Pregunta.** El enunciado plantea la fase II como grupal (§2, §5): ¿cómo aplica a un proyecto individual?

**Respuesta.** El profesor autorizó hacer el proyecto de forma individual, y Pedro lo confirma. Las dos
fases las hace la misma persona.

**Consecuencias.**
- Los criterios grupales de §6 se aplican igual, pero sobre el trabajo de una sola persona.
- «Contribuciones identificables» (§5.3) se cumple con la autoría única del repositorio (`CONTRIBUTING.md` §1).

## A2 · La matriz comparativa no es necesaria

**Pregunta.** §5.1 pide una matriz comparativa de las propuestas individuales. Sin equipo no hay propuestas que comparar.

**Respuesta.** No hace falta hacerla. Se puede hacer un artefacto equivalente si aporta algo.

**Consecuencias.** En su lugar, el informe de la fase II incluirá una **tabla de decisiones que cambiaron**
entre el diseño de la fase I y la implementación, con su motivo y su ADR. Así se cumple también lo que
pide §2: «registrar qué decisiones cambian y por qué» ([ADR 0006](decisiones/0006-registro-de-cambios-entre-fases.md)).

## A3 · El documento de la fase I se entrega en PDF

**Pregunta.** §4.3 admite PDF o Word.

**Respuesta.** Se entrega en **PDF**. La fecha de entrega no condiciona el diseño.

## A4 · La extensión no es un límite

**Pregunta.** §4.3 sugiere 6–10 páginas sin anexos. ¿Es un límite? ¿Las APIs pueden ir en anexos?

**Respuesta.** Las 6–10 páginas no son un límite duro: el documento puede extenderse todo lo necesario.
**Todo va dentro del documento**, sin anexos aparte.

**Consecuencias.** La especificación completa de las APIs, los diagramas y el análisis de escenarios
van en el cuerpo del documento ([ADR 0029](decisiones/0029-especificacion-de-apis-en-la-fase-1.md)). Que no haya límite
no significa que sobre: el consejo C1 (justificar con su límite) sigue mandando sobre la extensión.

## A5 · Cifrado en reposo: a criterio del diseño

**Pregunta.** RNF6 pide cifrado en reposo. ¿Vale el cifrado del volumen EBS o se espera cifrado por
bloque? ¿Hay que cifrar también los metadatos?

**Respuesta.**
- **No es necesario cifrar los metadatos.**
- Elegir entre el cifrado del volumen EBS y el cifrado por bloque **queda a criterio del diseño**. Como
  el resto del proyecto, hay que sustentar la decisión ante el profesor, así que debe ser la que mejor
  se defienda desde el punto de vista del diseño y la arquitectura.

**Consecuencias.** Se elige el cifrado de sobre en el cliente, con AES-256-GCM por bloque
([ADR 0024](decisiones/0024-cifrado-en-reposo.md)).

## A6 · RNF7 permite conocer el servidor de metadatos

**Pregunta.** RNF7 prohíbe direcciones de nodos codificadas de forma estática en el cliente. ¿Puede el
cliente conocer el servidor de metadatos como punto de entrada?

**Respuesta.** Sí, y RNF7 se sigue cumpliendo. Lo que importa es que el cliente **no sepa dónde están
los bloques**: tiene que preguntárselo al servidor de metadatos.

**Consecuencias.** El cliente se configura solo con los nombres de los servidores de metadatos y obtiene
las ubicaciones de los bloques en tiempo de ejecución ([ADR 0021](decisiones/0021-descubrimiento-y-resolucion-de-nombres.md)).
Coincide con el consejo C7 (el servidor de metadatos como *binder*).

## A7 · Objetivo: ninguna simplificación

**Pregunta.** §7 permite simplificar RF3 o las garantías no funcionales si el profesor lo aprueba antes de implementar.

**Respuesta.** La idea es **no necesitar simplificaciones**.

**Consecuencias.**
- `write()` admite creación, reemplazo, anexado y modificación parcial ([ADR 0009](decisiones/0009-bloques-inmutables-y-versiones-de-archivo.md)).
- El servidor de metadatos no es un punto único de fallo ([ADR 0014](decisiones/0014-metadatos-replicados-con-raft.md)).
- Si en la fase II apareciera una simplificación inevitable, se declara y se lleva al profesor antes de
  implementarla (§7 y consejo C3).

## A8 · Documentación de referencia recomendada

El profesor recomienda la guía de arquitectura de HDFS:
<https://hadoop.apache.org/docs/r1.2.1/hdfs_design.html>.

Al usarla hay que tener en cuenta que describe **Hadoop 1.2.1** (2013). Varias cosas que dice han
cambiado en versiones posteriores o DFSha las resuelve de otra forma:

| HDFS 1.2.1, según la guía | En DFSha |
|---|---|
| *Write-once-read-many*; el anexado «no está soportado todavía» | Cuatro modos de escritura sobre bloques inmutables (ADR 0009) |
| El NameNode es un SPOF; reiniciarlo exige intervención manual | Tres servidores de metadatos con Raft (ADR 0014) |
| Bloque típico de 64 MB | 16 MiB, configurable (ADR 0016) |
| Réplicas en cadena (*replication pipelining*) | La réplica primaria reenvía en paralelo (ADR 0012) |
| El NameNode nunca inicia RPC; las órdenes van en la respuesta al latido | Igual (ADR 0018, ADR 0019) |
| Un escritor por archivo | Arrendamientos por rango de bloques (ADR 0011) |

También sirve como fuente oficial de afirmaciones que hasta ahora solo se apoyaban en el lab HDFS, que
no se ha ejecutado: el modelo *write-once-read-many* (C12), los latidos y el informe de bloques (C16) y
la re-replicación (C17). El valor de 10,5 minutos de C16 no aparece en esta guía.
