# Cómo contribuir a DFSha

Reglas para **todos** los commits del repositorio, los haga una persona, una sesión de Claude Code o
cualquier otra herramienta. Las versiones se publican automáticamente a partir de los mensajes de
commit, así que estas reglas no son de estilo: **un commit mal formado no cuenta para la versión y la
herramienta no avisa**.

Las convenciones de nombres del código y de los documentos están en
[`docs/convenciones.md`](docs/convenciones.md), y los términos en [`docs/glosario.md`](docs/glosario.md).

## 1. Identidad y autoría

| Regla | Detalle |
|---|---|
| **Correo único** | Autor **y** committer de todos los commits: `pedroj1229@gmail.com`. |
| **Sin coautores** | Prohibido el trailer `Co-Authored-By:`, incluido `Co-Authored-By: Claude <noreply@anthropic.com>`. |
| **Sin marcas de herramientas** | Prohibido cualquier enlace o texto de sesión de Claude Code (`Generated with Claude Code`, `https://claude.ai/code/...`) o de otra herramienta, en el mensaje o en el cuerpo. |
| **Trailers permitidos** | Solo `BREAKING CHANGE:`, `Refs #<n>` y `Closes #<n>` (§4.3). |

Configuración del repositorio local (una vez por clon):

```bash
git config --local user.email pedroj1229@gmail.com
git config --local user.name "<tu nombre>"
```

Comprobación antes de hacer push:

```bash
git log origin/main..HEAD --format='%h %ae %ce %s'                    # los dos correos deben ser pedroj1229@gmail.com
git log origin/main..HEAD --format='%(trailers)' | grep -iE 'co-authored|claude' && echo "QUITAR TRAILERS"
```

Si un commit local incumple alguna de estas reglas y todavía **no** se ha subido, se corrige con
`git commit --amend --reset-author` (último commit) o con un rebase. Lo que ya está en `main` no se reescribe
(§7.4).

Los commits de release que crea el workflow usan la misma identidad (`.github/workflows/release.yml`).

## 2. Estructura del mensaje

```
<tipo>(<ámbito>)<!>: <descripción>
                                              ← línea en blanco
<cuerpo opcional>
                                              ← línea en blanco
<pies opcionales>
```

Ejemplo completo:

```
feat(datanode): verifica el hash SHA-256 antes de confirmar un bloque

El nodo de datos recalcula el hash de cada bloque recibido y lo compara
con el que envía el cliente. Si no coinciden, responde ABORTED con el
motivo BLOCK_CORRUPTED y descarta el bloque del área temporal.

Refs #12
```

## 3. Cabecera

### 3.1 Tipos

Lista cerrada. El tipo decide si hay versión nueva:

| Tipo | Cuándo | Versión |
|---|---|---|
| `feat` | Funcionalidad nueva visible para el usuario o para otro componente | *minor* (0.1.0 → 0.2.0) |
| `fix` | Corrección de un error | *patch* (0.1.0 → 0.1.1) |
| `perf` | Mejora de rendimiento sin cambiar el comportamiento | *patch* |
| `refactor` | Cambio interno sin efecto visible ni corrección | ninguna |
| `docs` | Solo documentación | ninguna |
| `test` | Solo pruebas | ninguna |
| `build` | Dependencias, Dockerfiles, empaquetado | ninguna |
| `ci` | Workflows y automatización del repositorio | ninguna |
| `chore` | Mantenimiento que no encaja en ningún otro tipo | ninguna |

Si un commit encaja en dos tipos, probablemente son dos commits (§6).

### 3.2 Ámbitos

Opcionales. Lista cerrada, en minúsculas. Corresponden a las áreas del repositorio; la tabla de §6.1
dice qué tipo y qué ámbito lleva cada área.

**Áreas de código**

| Ámbito | Abarca |
|---|---|
| `metadata` | Servidor de metadatos (`dfsha/metadata/`) |
| `datanode` | Nodos de datos (`dfsha/datanode/`) |
| `client` | Cliente: CLI y biblioteca (`dfsha/client/`) |
| `common` | Código compartido por varios roles: configuración, logging, utilidades (`dfsha/common/`) |
| `proto` | Contratos gRPC (`proto/`) y su código generado |
| `security` | Autenticación, autorización y cifrado **transversales**: TLS, módulo `auth`, gestión de claves |
| `deploy` | Docker, Docker Compose, AWS y scripts de despliegue (`deploy/`, `scripts/`) |
| `bench` | Experimentos de rendimiento y sus resultados (`bench/`) |

**Áreas de documentación** (solo con el tipo `docs`)

| Ámbito | Abarca |
|---|---|
| `design` | Documento de diseño de la fase I (`docs/fase-1/`) y sus diagramas |
| `report` | Informe técnico final de la fase II (`docs/fase-2/`) |
| `adr` | Registro de decisiones (`docs/decisiones/`) |
| `evidence` | Evidencias de las pruebas mínimas (`evidencias/`) |

- Un solo ámbito por commit. Si el cambio toca varias áreas y no se puede separar (§6.2), va sin
  ámbito: `feat: …`.
- La documentación general del repositorio (README, `CONTRIBUTING.md`, `CLAUDE.md`, convenciones,
  glosario, enunciado) va como `docs:` sin ámbito.
- La seguridad **dentro** de un componente lleva el ámbito del componente
  (`fix(datanode): rechaza bloques de otro propietario`). `security` es solo para lo transversal.
- Un ámbito nuevo exige añadirlo a esta tabla antes de usarlo.

### 3.3 Descripción

- En **español**, empezando por un **verbo en imperativo** (forma tú): *añade*, *corrige*, *elimina*,
  *separa*, *documenta*. No vale el infinitivo (*añadir*), el pasado (*añadido*) ni un sustantivo
  (*añadido de…*, *corrección de…*).
- En **minúscula** al principio y **sin punto final**.
- Dice **qué cambia**, no qué se hizo para cambiarlo: `corrige la ubicación de réplicas tras una caída`,
  no `cambios en metadata.py`.
- Los términos salen del [glosario](docs/glosario.md): *bloque*, no *chunk*; *cerrojo*, no *bloqueo*.
- Los identificadores de código se escriben tal cual: `renombra GetBlocks a GetBlockLocations`.

### 3.4 Longitud

| Parte | Límite |
|---|---|
| Cabecera completa (`tipo(ámbito): descripción`) | **72 caracteres como máximo**; 50 es lo ideal |
| Descripción | Al menos 3 palabras |
| Cuerpo y pies | Líneas de **72 caracteres como máximo**. Solo las URL pueden pasarse |

Si la cabecera no cabe en 72 caracteres, el detalle va al cuerpo.

## 4. Cuerpo y pies

### 4.1 Cuando hace falta cuerpo
Es obligatorio en `fix` (qué fallaba y por qué), en todo cambio incompatible y cuando el *porqué* no se
deduce de la cabecera. Explica **por qué** se hizo el cambio y qué efecto tiene; el *cómo* ya está en el diff.

### 4.2 Cambios incompatibles
Un cambio que rompe un contrato (API, `.proto`, formato en disco, configuración) se marca **de las dos
formas**:

```
feat(proto)!: renombra GetBlocks a GetBlockLocations

BREAKING CHANGE: los clientes deben llamar a GetBlockLocations;
GetBlocks deja de existir.
```

`BREAKING CHANGE` va **literal, en inglés y en mayúsculas**, porque la herramienta lo busca así.
Mientras la serie sea `0.y.z`, un cambio incompatible sube la *minor* (§7.2).

### 4.3 Pies permitidos
| Pie | Uso |
|---|---|
| `BREAKING CHANGE: <explicación>` | Cambio incompatible |
| `Refs #<n>` | Relación con un issue |
| `Closes #<n>` | El commit cierra un issue al llegar a `main` |

Cualquier otro pie está prohibido, en particular `Co-Authored-By:` y las marcas de herramientas (§1).

## 5. Ejemplos

| ✅ Correcto | ❌ Incorrecto | Problema |
|---|---|---|
| `feat(datanode): almacena bloques en disco` | `feat(DataNode): Almacena bloques.` | Ámbito con mayúsculas, descripción en mayúscula, punto final |
| `fix(metadata): corrige la ubicación de réplicas` | `fix: arreglado bug` | Pasado, sin contenido |
| `docs(design): describe el escenario de escritura concurrente` | `docs(docs): escenarios` | Ámbito que no existe, sin verbo |
| `test(bench): mide la latencia de lectura con 3 clientes` | `feat(bench): mide la latencia de lectura` | `feat` publicaría una versión sin cambiar el sistema |
| `refactor(client): separa el parser de comandos` | `update client` | Sin tipo: no cuenta para la versión |
| `test(datanode): cubre la caída durante la escritura` | `feat: añade tests` | Tipo equivocado: publicaría una versión falsa |
| `perf(client): lee bloques en paralelo` | `feat(client): mejora rendimiento y corrige timeout` | Dos cambios en un commit |

## 6. Separación de commits

- **Un commit = un cambio lógico**: lo que se revertiría junto.
- Las pruebas de una funcionalidad van en el mismo `feat` o `fix`; un `test:` aparte es solo para pruebas
  de código que ya existía.
- No se mezclan formato, refactorización y cambios de comportamiento.
- Cada commit en `main` deja el repositorio en un estado coherente: compila y pasan las pruebas.

### 6.1 Tipo y ámbito por área

| Área | Qué cambia | Tipo y ámbito |
|---|---|---|
| `dfsha/<rol>/`, `dfsha/common/` | Funcionalidad nueva | `feat(<rol>)` |
| | Corrección | `fix(<rol>)` |
| | Mejora de rendimiento | `perf(<rol>)` |
| | Reorganización interna | `refactor(<rol>)` |
| `proto/` | RPC o mensaje nuevo, compatible | `feat(proto)` |
| | Cambio incompatible (renombrar, quitar, cambiar tipos o números de campo) | `feat(proto)!` + `BREAKING CHANGE:` |
| `tests/` | Pruebas de código que ya existía | `test(<rol>)` |
| `bench/` | Scripts de experimentos | `test(bench)` |
| | Resultados (CSV, gráficas) | `docs(bench)` |
| `deploy/`, `scripts/`, Dockerfiles | Despliegue nuevo o cambiado | `build(deploy)` |
| | Corrección de un despliegue roto | `fix(deploy)` |
| Dependencias (`requirements*.txt`, `pyproject.toml`) | Añadir, quitar o actualizar | `build` |
| `.github/`, `.releaserc.json` | Automatización del repositorio | `ci` |
| `docs/fase-1/` | Documento de diseño | `docs(design)` |
| `docs/fase-2/` | Informe final | `docs(report)` |
| `docs/decisiones/` | ADR nuevo o cambio de estado | `docs(adr)` |
| `evidencias/` | Salida registrada de una prueba | `docs(evidence)` |
| README, convenciones, glosario, `CONTRIBUTING.md`, `CLAUDE.md` | Documentación general | `docs` |
| `.gitignore`, ficheros de editor, limpieza | Mantenimiento | `chore` |

Reglas que se derivan de la tabla:
- **`bench` y `evidence` nunca usan `feat` ni `fix`.** No son funcionalidad del DFS; un `feat(bench)`
  publicaría una versión nueva sin ningún cambio en el sistema.
- **El despliegue no publica versión por sí solo** (`build`). Solo `fix(deploy)` lo hace, porque
  corrige algo que impedía usar el sistema.
- **Un ADR va en su propio commit** `docs(adr)`, antes de los commits que lo implementan. Así el
  historial muestra primero la decisión y después su aplicación (enunciado §2).
- **Un término nuevo del glosario** va en un commit `docs` previo o en el mismo commit que lo introduce
  en el código, nunca después.

### 6.2 Cambios que cruzan varias áreas

Una funcionalidad de DFSha suele tocar contrato, servidores y cliente a la vez. Se separa **por
área y en orden de dependencia**, de manera que cada commit deje `main` coherente:

1. `feat(proto)`: el contrato y su código generado.
2. `feat(common)`: lo compartido, si hace falta.
3. `feat(metadata)` y/o `feat(datanode)`: los servidores implementan el contrato.
4. `feat(client)`: el cliente lo usa. Este suele ser el commit que hace visible la funcionalidad.
5. `docs(...)` o `test(...)`: documentación o pruebas que no encajen en los anteriores.

Ejemplo, para la confirmación atómica de escrituras:

```
feat(proto): añade CommitFile y AbortFile al servicio de metadatos
feat(metadata): confirma archivos solo con todas las réplicas escritas
feat(datanode): guarda los bloques en el área temporal hasta confirmar
feat(client): confirma la escritura al terminar put
```

- Solo se junta en **un commit sin ámbito** cuando separarlo dejaría algún commit intermedio roto
  (por ejemplo, un cambio incompatible del contrato que obliga a tocar todas las áreas a la vez).
- **La versión se calcula por push, no por commit.** Varios `feat` en el mismo push dan **una sola**
  versión *minor*, con todos los cambios en sus notas. Separar en varios commits no infla la versión.
- Un **refactor** que prepara una funcionalidad va en su propio commit, **antes** del `feat`.

## 7. Ramas, integración y release

### 7.1 Ramas
- Se puede trabajar directamente en `main`. Las ramas son opcionales y siguen el patrón
  `<tipo>/<descripcion-en-kebab>`: `feat/replicacion-bloques`, `docs/fase-1-escenarios`.
- **Si se fusiona un pull request, se usa *squash merge*** y el título del PR tiene que cumplir §3, porque
  es el mensaje que queda en `main`. Un *merge commit* (`Merge branch …`) no cuenta para la versión.

### 7.2 Release automático
En cada push a `main`, **semantic-release** (`.github/workflows/release.yml` + `.releaserc.json`, ADR 0005):

1. Lee los commits desde la última etiqueta `vX.Y.Z`.
2. Calcula la versión según §3.1. Si no hay ningún `feat`, `fix` ni `perf`, no publica nada.
3. Actualiza `CHANGELOG.md` y lo sube con un commit `chore(release): X.Y.Z [skip ci]`.
4. Crea la etiqueta `vX.Y.Z` y el release en GitHub con las notas.

Reglas:
- La serie es `0.y.z`; los cambios incompatibles suben la *minor*. La `1.0.0` se reserva para la entrega de
  la fase II y exige cambiar `.releaserc.json` (procedimiento en ADR 0005).
- El primer commit publicable del proyecto tiene que ser un `feat`, para que la primera versión sea `0.1.0`.
- **Después de cada release, `git pull`**, porque el workflow añade un commit a `main`.
- `[skip ci]` está reservado para el commit de release. No se usa a mano.

### 7.3 Etiquetas
- Las etiquetas `vX.Y.Z` las crea **solo** semantic-release. La única excepción es `v0.0.0`, la línea base del commit inicial.
- Las entregas se marcan a mano con etiquetas anotadas que no siguen SemVer y que la herramienta ignora:
  ```bash
  git tag -a entrega-fase-1 -m "Entrega de la fase I"
  git push origin entrega-fase-1
  ```

### 7.4 Historial
- **Prohibido `git push --force` a `main`** y reescribir commits ya publicados. Las etiquetas de versión
  apuntan a ellos.
- Un error en un commit publicado se corrige con un commit nuevo (`fix:`, `docs:`…) o con `git revert`.

## 8. Qué no se commitea
- Secretos: credenciales de AWS, `*.pem`, claves privadas, certificados con su clave, `.env` con valores reales.
  Si alguno llega a un commit, **se rota**: borrarlo después no lo saca del historial.
- IP literales en código o configuración (RNF7). Solo pueden aparecer en `evidencias/`.
- `CLAUDE.local.md` (ignorado en `.gitignore`).
- `CHANGELOG.md` editado a mano.

## 9. Lista de comprobación antes de `git push`
- [ ] Autor y committer `pedroj1229@gmail.com` (§1).
- [ ] Sin `Co-Authored-By` ni marcas de Claude Code u otras herramientas (§1).
- [ ] Cabecera de 72 caracteres como máximo, con tipo y ámbito de las listas (§3).
- [ ] Verbo en imperativo, en minúscula, sin punto final (§3.3).
- [ ] Cuerpo si es un `fix` o un cambio incompatible (§4).
- [ ] Un cambio lógico por commit, con el tipo y el ámbito de su área (§6.1).
- [ ] Si la funcionalidad cruza áreas, commits en orden de dependencia (§6.2).
- [ ] Ningún secreto ni IP literal (§8).
