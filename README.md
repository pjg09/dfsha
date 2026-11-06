# dfsha
DFSha: Sistema de archivos distribuido con alta disponibilidad, arquitectura cliente/servidor con servicio distribuido entre servidores (S2S), particionamiento en bloques, replicación, consistencia y seguridad. Proyecto 1, Arquitectura de Nube y Sistemas Distribuidos (UPB, 2026-2).

**Estado:** fase II (implementación). El diseño de la fase I está cerrado desde la versión 0.1.0; ahora se implementa el sistema, con código ejecutable, pruebas reproducibles y evidencias.

## Diseño (fase I)

- [Documento de diseño](docs/fase-1.md): arquitectura, distribución de datos, APIs, consistencia, tolerancia a fallos, seguridad, escenarios y experimentos.
- [Referencias](docs/referencias.md): fuentes del documento en formato IEEE, con la misma numeración y cómo se comprobó cada una.
- [Diagramas](docs/diagramas/): las figuras del documento, sus fuentes y cómo regenerarlas.
- [Registro de decisiones](docs/decisiones/): cada decisión de arquitectura y de proceso (ADR), con sus alternativas y consecuencias.

## Requisitos y contexto

- [Enunciado](docs/enunciado.md): transcripción del enunciado oficial, con la arquitectura asignada.
- [Aclaraciones del profesor](docs/aclaraciones.md): respuestas a las dudas sobre el enunciado (A1–A8).
- [Consejos de diseño](docs/consejos-diseno.md): condicionantes extraídos de clase, labs y AWS (C1–C30).

## Instalación y pruebas

Hace falta [uv](https://docs.astral.sh/uv/) 0.12.5, que instala Python 3.12 si no está (ADR 0038).

```bash
uv sync --locked                   # entorno con las versiones exactas de uv.lock
uv run pytest                      # pruebas automáticas
uv run pyright                     # comprobación de tipos
uv run scripts/generate-proto.sh   # regenera dfsha/v1/ después de cambiar proto/
```

## Entorno local

El clúster en una sola máquina con Docker Compose y las mismas imágenes que en AWS (ADR 0030). Solo sirve
para desarrollar: las evidencias se obtienen en AWS (ADR 0036). Por ahora levanta los cinco nodos de datos.

```bash
export DFSHA_VERSION=$(scripts/get-version.sh) DFSHA_IMAGE_TAG=$(scripts/get-version.sh --image)
docker compose -f deploy/local/compose.yaml up -d --build   # construye las imágenes y arranca el clúster
docker compose -f deploy/local/compose.yaml logs -f          # logs de todos los nodos
docker compose -f deploy/local/compose.yaml down -v          # para el clúster y borra sus volúmenes
```

## Cómo trabajar en el repositorio

- [Convenciones](docs/convenciones.md): idioma, nombres, hosts, puertos, Git y versiones.
- [Glosario](docs/glosario.md): términos del proyecto y sus identificadores.
- [Cómo contribuir](CONTRIBUTING.md): reglas de commits, autoría y release automático.
