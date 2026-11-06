# DFSha — instrucciones para Claude Code

Sistema de archivos distribuido con alta disponibilidad. Proyecto 1 de Arquitectura de Nube y
Sistemas Distribuidos (UPB, 2026-2). Arquitectura asignada: **opción 1, cliente/servidor con
servicio distribuido entre servidores (S2S)**. Proyecto individual, aprobado por el profesor.

**Estado:** fase II (implementación). El diseño de la fase I está cerrado en `docs/fase-1.md` (resumen en su §1.2 y §3), y cada decisión en su ADR (índice en `docs/decisiones/README.md`). Ya existen `proto/` y `dfsha/` (etapa 1); aún no `deploy/`. La estructura prevista está en `docs/convenciones.md`. El plan de la fase II, con sus etapas y la etapa en curso, está en `docs/fase-2/plan.md`: léelo al empezar y actualiza su tabla de estado al terminar cada etapa.

## Antes de escribir código o documentación
Lee y aplica:
- [`CONTRIBUTING.md`](CONTRIBUTING.md): reglas de commits, autoría y release.
- [`docs/enunciado.md`](docs/enunciado.md): el enunciado oficial transcrito. Es la referencia de requisitos (RF, RNF), entregables y rúbrica.
- [`docs/aclaraciones.md`](docs/aclaraciones.md): respuestas del profesor que completan el enunciado (A1–A8). Tienen su mismo rango.
- [`docs/consejos-diseno.md`](docs/consejos-diseno.md): condicionantes de diseño (C1–C30) sacados de clase, labs y AWS. Tenlos en cuenta al diseñar y cítalos por su identificador.
- [`docs/convenciones.md`](docs/convenciones.md): idioma, nombres por tipo de artefacto, hosts, Git y versiones.
- [`docs/glosario.md`](docs/glosario.md): la palabra exacta para cada concepto. No uses los sinónimos de la columna «No usar».
- [`docs/decisiones/`](docs/decisiones/): decisiones ya tomadas. No las contradigas; si algo debe cambiar, propón un ADR nuevo.
- [`docs/fase-1.md`](docs/fase-1.md) y [`docs/referencias.md`](docs/referencias.md): documento de diseño de la fase I y sus fuentes IEEE, con la misma numeración.

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
- Antes de dar un texto por terminado, busca con `grep` los términos de la columna «No usar» del glosario (los que más se cuelan: fichero, carpeta, bloqueo o bloquear en el sentido de cerrojo, publicar, checksum, copia por réplica, subir o descargar).
- **Commits según [`CONTRIBUTING.md`](CONTRIBUTING.md)**: Conventional Commits con los tipos y ámbitos de
  su lista, cabecera de 72 caracteres como máximo. Las versiones las calcula semantic-release a partir de
  ellos: un commit mal formado se pierde. No crees etiquetas `vX.Y.Z` ni edites `CHANGELOG.md` a mano.
- **Autoría:** autor y committer `pedroj1229@gmail.com`. **Nunca** añadas `Co-Authored-By:` (tampoco el de
  Claude) ni el texto o el enlace de la sesión de Claude Code («Generated with Claude Code», `claude.ai/code/...`)
  en commits ni etiquetas.
- **Nunca** versiones secretos: credenciales de AWS, `*.pem`, claves privadas, `.env` con valores reales
  ni IP en la configuración.
- Hosts con el patrón `<rol>-<n>` (`metadata-1`, `datanode-2`); nada de IP literales en el código (RNF7).
- Un ADR sin commitear se puede corregir. Una vez commiteado, cualquier cambio va en un ADR nuevo que lo sustituye; del antiguo solo cambia la línea de estado.

## Fase II: evidencias e informe (ADR 0036)
- Cuando una prueba mínima de §5.2 pase en `aws`, se ejecute un experimento (ADR 0028) o se provoque un fallo, **propón registrar la evidencia en ese momento**, antes de que termine la sesión del Learner Lab. Una prueba no está hecha hasta que su evidencia está en `evidencias/` y en su índice.
- Quita tokens, claves y credenciales de la salida antes de commitearla.
- Si hace falta una captura que no puedes tomar tú (la consola de AWS, por ejemplo), pídesela a Pedro en ese momento, con el nombre del archivo y el directorio de `evidencias/` donde va.
- Al terminar cada tarea que haya ejecutado algo en AWS, comprueba que todo lo ejecutado tiene su evidencia y su fila en el índice, y dilo en el resumen final. Si falta algo, dilo antes que nada.
- Una limitación o un problema que el informe deba contar se anota en `docs/fase-2/notas.md` cuando aparece. Un cambio de diseño va en un ADR.
- Cada fuente que se use para decidir algo (documentación, un análisis, el código de una librería) se añade en el momento a `docs/fase-2/fuentes.md`, con cómo se comprobó. Si no se leyó, se dice. Las de la fase I siguen en `docs/referencias.md`.
- El informe técnico se redacta al final, a partir de los ADR, el código, `evidencias/`, `bench/resultados/` y `docs/fase-2/notas.md`.

## Documento de la fase I y figuras
- `docs/fase-1.md` se edita a mano (ya no hay script que lo genere). Citas IEEE `[n]` por orden de primera aparición; tablas y figuras numeradas a mano.
- **No cambies la numeración** de tablas, figuras ni referencias: el documento ya está maquetado fuera del repo. Lo nuevo entra como filas, viñetas o párrafos. Una fuente nueva va al final de la lista y a `referencias.md`, con su verificación.
- Un cambio de diseño: primero el ADR; después `fase-1.md`, el glosario y las convenciones, en la misma tanda. Repasa también §1.4 (limitaciones), §13.2 (parámetros), §14 (pendientes), el Anexo B y las figuras afectadas.
- Figuras (ADR 0034): fuente en `docs/diagramas/` y PNG a escala 2. Cada una debe caber en una página (alto/ancho ≤ 1,38) con la letra legible; revísalas siempre con Read antes de darlas por buenas. Cómo exportarlas, su catálogo y las trampas de Mermaid: [`docs/diagramas/README.md`](docs/diagramas/README.md).
- Desde la etapa 1, la fuente de los contratos es `proto/dfsha/v1/`, no el Anexo A. Tras cambiar un `.proto`, ejecuta `uv run scripts/generate-proto.sh` y commitea el código generado de `dfsha/v1/` con él (ADR 0038). Un cambio de contrato respecto al Anexo A lleva su ADR.
