# DFSha — instrucciones para Claude Code

Sistema de archivos distribuido con alta disponibilidad. Proyecto 1 de Arquitectura de Nube y
Sistemas Distribuidos (UPB, 2026-2). Arquitectura asignada: **opción 1, cliente/servidor con
servicio distribuido entre servidores (S2S)**. Proyecto individual, aprobado por el profesor.

## Antes de escribir código o documentación
Lee y aplica:
- [`CONTRIBUTING.md`](CONTRIBUTING.md): reglas de commits, autoría, ramas y release.
- [`docs/enunciado.md`](docs/enunciado.md): el enunciado oficial transcrito. Es la referencia de requisitos (RF, RNF), entregables y rúbrica.
- [`docs/consejos-diseno.md`](docs/consejos-diseno.md): condicionantes de diseño (C1–C30) sacados de clase, labs y AWS. Tenlos en cuenta al diseñar y cítalos por su identificador.
- [`docs/convenciones.md`](docs/convenciones.md): idioma, nombres por tipo de artefacto, hosts, Git y versiones.
- [`docs/glosario.md`](docs/glosario.md): la palabra exacta para cada concepto. No uses los sinónimos de la columna «No usar».
- [`docs/decisiones/`](docs/decisiones/): decisiones ya tomadas. No las contradigas; si algo debe cambiar, propón un ADR nuevo.

## Skills y plugins del repositorio
Skills propias (`.claude/skills/`), que **solo se ejecutan cuando el usuario las invoca**:
- `/adr <decisión>`: redacta un ADR con la plantilla del repo y lo guarda al aprobarlo.
- `/commit [push]`: agrupa y redacta los commits según `CONTRIBUTING.md`, y sube solo si se pide.

Plugins con ámbito de proyecto (`.claude/settings.json`):
- `pyright-lsp`: comprobación de tipos de Python. Necesita `pyright-langserver` en el PATH.
- `context7`: documentación actualizada de librerías (grpcio, FastAPI…). Consúltala antes de usar una
  API de una librería en vez de fiarte de la memoria. Es un servicio externo: no le envíes secretos
  ni código privado, solo nombres de librerías y preguntas.

## Reglas que no se negocian
- **Código en inglés, documentación en español** (ADR 0001). Identificadores en ASCII.
- Término nuevo → primero al glosario, después al código o a los documentos.
- **Commits según [`CONTRIBUTING.md`](CONTRIBUTING.md)**: Conventional Commits con los tipos y ámbitos de
  su lista, cabecera de 72 caracteres como máximo. Las versiones las calcula semantic-release a partir de
  ellos: un commit mal formado se pierde. No crees etiquetas `vX.Y.Z` ni edites `CHANGELOG.md` a mano.
- **Autoría:** autor y committer `pedroj1229@gmail.com`. **Nunca** añadas `Co-Authored-By:` (tampoco el de
  Claude) ni el texto o el enlace de la sesión de Claude Code («Generated with Claude Code», `claude.ai/code/...`)
  en commits, etiquetas ni pull requests.
- **Nunca** versiones secretos: credenciales de AWS, `*.pem`, claves privadas, `.env` con valores reales
  ni IP en la configuración.
- Hosts con el patrón `<rol>-<n>` (`metadata-1`, `datanode-2`); nada de IP literales en el código (RNF7).
