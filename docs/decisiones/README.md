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
| [0006](0006-registro-de-cambios-entre-fases.md) | Tabla de cambios entre fases en lugar de la matriz comparativa | Aceptada | 2026-10-23 |
| [0007](0007-diagramas-como-codigo.md) | Diagramas como código, con Mermaid por defecto | Sustituida por 0034 | 2026-10-23 |
| [0008](0008-stack-tecnologico.md) | Python 3.12, gRPC y Docker sobre varias instancias EC2 | Aceptada | 2026-10-23 |
| [0009](0009-bloques-inmutables-y-versiones-de-archivo.md) | Bloques inmutables y versiones de archivo: semántica de `write()` | Aceptada | 2026-10-23 |
| [0010](0010-consistencia-de-apertura-cierre.md) | Consistencia de apertura-cierre para `read()` y `write()` | Aceptada | 2026-10-23 |
| [0011](0011-arrendamientos-por-rango-de-bloques.md) | Cerrojos: arrendamientos exclusivos por rango de bloques | Aceptada | 2026-10-23 |
| [0012](0012-replicacion-y-confirmacion-por-mayoria.md) | Replicación: factor 3, confirmación por mayoría y reenvío desde la réplica primaria | Aceptada | 2026-10-23 |
| [0013](0013-confirmacion-atomica-de-archivos.md) | Confirmación atómica de archivos y escrituras interrumpidas | Aceptada | 2026-10-23 |
| [0014](0014-metadatos-replicados-con-raft.md) | Servidor de metadatos replicado con Raft en tres nodos | Aceptada | 2026-10-23 |
| [0015](0015-topologia-del-cluster.md) | Topología del clúster: 3 servidores de metadatos, 5 nodos de datos y 1 cliente | Aceptada | 2026-10-23 |
| [0016](0016-tamano-de-bloque.md) | Tamaño de bloque de 16 MiB, configurable | Aceptada | 2026-10-23 |
| [0017](0017-ubicacion-de-replicas.md) | Ubicación de réplicas y reparto de bloques | Aceptada | 2026-10-23 |
| [0018](0018-deteccion-de-fallos-y-re-replicacion.md) | Detección de fallos, re-replicación y recolección de basura | Aceptada | 2026-10-23 |
| [0019](0019-grpc-sin-mom-ni-rest.md) | gRPC en todas las interfaces, sin MOM ni API REST | Aceptada | 2026-10-23 |
| [0020](0020-reintentos-idempotentes.md) | Reintentos: al menos una vez, con operaciones idempotentes | Aceptada | 2026-10-23 |
| [0021](0021-descubrimiento-y-resolucion-de-nombres.md) | Descubrimiento: el cliente solo conoce los servidores de metadatos; nombres por `/etc/hosts` | Aceptada | 2026-10-23 |
| [0022](0022-autenticacion-autorizacion-y-tokens-de-bloque.md) | Autenticación de usuarios, autorización por propietario y tokens de bloque | Aceptada | 2026-10-23 |
| [0023](0023-cifrado-en-transito.md) | Cifrado en tránsito: TLS con el cliente y TLS mutuo entre nodos | Aceptada | 2026-10-23 |
| [0024](0024-cifrado-en-reposo.md) | Cifrado en reposo: cifrado de sobre en el cliente con AES-256-GCM | Aceptada | 2026-10-23 |
| [0025](0025-espacio-de-nombres-y-operaciones-rf1.md) | Espacio de nombres por usuario y operaciones de RF1 | Aceptada | 2026-10-23 |
| [0026](0026-almacenamiento-en-volumen-ebs.md) | Almacenamiento de bloques en un volumen EBS por nodo de datos | Aceptada | 2026-10-23 |
| [0027](0027-despliegue-en-aws-con-docker.md) | Despliegue en AWS: una imagen por rol y un contenedor por instancia | Sustituida por 0040 | 2026-10-23 |
| [0028](0028-metricas-y-experimentos.md) | Métricas y experimentos | Aceptada | 2026-10-23 |
| [0029](0029-especificacion-de-apis-en-la-fase-1.md) | Especificación de las APIs en el documento de la fase I | Aceptada | 2026-10-23 |
| [0030](0030-entorno-local-de-desarrollo.md) | Entorno local de desarrollo con las mismas imágenes que AWS | Aceptada | 2026-10-23 |
| [0031](0031-modo-seguro-tras-la-eleccion-de-lider.md) | Modo seguro tras cada elección de líder | Aceptada | 2026-10-23 |
| [0032](0032-replicas-corruptas-y-verificacion-periodica.md) | Réplicas corruptas y verificación periódica de bloques | Aceptada | 2026-10-23 |
| [0033](0033-sincronizacion-de-relojes.md) | Sincronización de relojes entre nodos | Aceptada | 2026-10-23 |
| [0034](0034-documento-de-la-fase-1-y-figuras.md) | Documento de la fase I en Markdown y figuras exportadas a PNG | Aceptada | 2026-10-23 |
| [0035](0035-persistencia-de-los-metadatos.md) | Persistencia de los metadatos en un volumen EBS por servidor de metadatos | Aceptada | 2026-10-24 |
| [0036](0036-evidencias-y-material-del-informe.md) | Evidencias y material del informe durante la fase II | Aceptada | 2026-11-06 |
| [0037](0037-imagenes-en-ecr.md) | Imágenes Docker en ECR, construidas una vez por versión | Aceptada | 2026-11-06 |
| [0038](0038-entorno-de-python-y-codigo-generado.md) | Entorno de Python con uv, código generado versionado y versión desde Git | Aceptada | 2026-11-06 |
| [0039](0039-raft-con-etcd.md) | Raft con etcd en los servidores de metadatos | Aceptada | 2026-11-06 |
| [0040](0040-despliegue-en-aws-con-etcd.md) | Despliegue en AWS: una imagen por rol, con etcd junto a cada servidor de metadatos | Aceptada | 2026-11-06 |

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
