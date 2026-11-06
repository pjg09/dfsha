# 0038 · Entorno de Python con uv, código generado versionado y versión desde Git

- **Estado:** Aceptada
- **Fecha:** 2026-11-06
- **Requisitos relacionados:** §5.3 (instrucciones reproducibles); ADR 0005, 0008 y 0019

## Contexto
La etapa 1 crea el paquete de Python y los contratos gRPC, y tiene tres cosas pendientes:
- **Versiones exactas.** El ADR 0008 las dejó para cuando se creara `pyproject.toml`. Además, el sistema
  de la máquina de desarrollo trae Python 3.14 y el proyecto usa 3.12.
- **Código generado.** `.gitignore` dejó pendiente si los `*_pb2.py` se versionan o se generan al construir.
- **Versión del paquete.** Las versiones las calcula semantic-release y quedan en las etiquetas `vX.Y.Z`
  (ADR 0005), no en ningún archivo.

## Opciones consideradas
**Gestor del entorno**
1. `pip` y `venv` con `requirements.txt`. No fija las dependencias transitivas sin otra herramienta
   (pip-tools) y no instala la versión de Python que hace falta.
2. `uv`. Instala Python 3.12 aunque el sistema tenga otra versión, y su `uv.lock` fija todas las
   dependencias con sus hashes.

**Código generado**
1. Generarlo al construir. Una sola fuente, pero cada entorno (desarrollo, pruebas, imágenes) necesita
   `grpcio-tools` y un paso más, y pyright no ve los tipos hasta generarlo.
2. Versionarlo junto al `.proto` y comprobar en las pruebas automáticas que coincide.

**Versión del paquete**
1. Fija en `pyproject.toml`. semantic-release no la actualiza, así que mentiría desde el primer release.
2. Calculada a partir de la última etiqueta `vX.Y.Z` de Git, con `hatch-vcs`.

## Decisión
- **uv 0.12.5** (`required-version` en `pyproject.toml`) y **Python 3.12** (`.python-version`). Las
  dependencias directas van con versión exacta en `pyproject.toml` y todas, también las transitivas, en
  `uv.lock`, que se versiona. Se instala con `uv sync --locked`.
- **Dependencias de la etapa 1:** `grpcio` 1.85.1, `grpcio-status` 1.85.1 (para `google.rpc.ErrorInfo`,
  fase I §5.4) y `protobuf` 7.36.2. Para desarrollar: `grpcio-tools` 1.85.1, `pytest` 9.2.0 y `pyright`
  1.1.414. `grpcio` y `grpcio-tools` llevan siempre la misma versión, porque el código generado exige un
  `grpcio` al menos tan nuevo como el generador.
- **Código generado versionado** en `dfsha/v1/`, la ruta que corresponde al paquete `dfsha.v1` de los
  `.proto`, de modo que se importa como `from dfsha.v1 import common_pb2`. Incluye los `.pyi` para pyright.
  Lo produce `scripts/generate-proto.sh`, nunca se edita a mano y va en el mismo commit que el `.proto`
  (`CONTRIBUTING.md` §3.2). Las pruebas automáticas fallan si no coincide con `proto/`.
- **Versión desde Git** con `hatch-vcs`, solo a partir de las etiquetas `v*`. Las de entrega
  (`entrega-fase-1`) se excluyen porque, sin ese filtro, el paquete salía con la versión `2.dev12`.
  Entre dos releases la versión es la siguiente con `.devN`, por ejemplo `0.1.1.dev12`.
- **Pruebas automáticas en cada push a `main`** (`.github/workflows/test.yml`): instalación con
  `uv.lock`, comprobación del código generado, pytest y pyright en modo `standard`.

## Consecuencias
- **Se gana:** la instalación es un comando y da las mismas versiones en cualquier máquina. El contrato y
  su código se revisan en el mismo commit, y pyright comprueba los tipos de los mensajes.
- **Se pierde:** los diffs del código generado hacen ruido en los commits de `proto`. Hace falta instalar
  `uv` en la máquina de desarrollo.
- **Límite:** cambiar la versión de `uv` exige cambiar a la vez `pyproject.toml` y el workflow. Los
  módulos `*_pb2_grpc.py` no tienen tipos y pyright no los comprueba.
- **Pendiente:** las imágenes Docker (etapa 3) reciben la versión como argumento de construcción, porque
  no llevan el historial de Git.
