# 0005 · semantic-release en cada push a `main`, empezando en 0.1.0

- **Estado:** Aceptada
- **Fecha:** 2026-10-21
- **Requisitos relacionados:** §5.3 del enunciado (repositorio reproducible); completa el ADR 0004

## Contexto
El ADR 0004 dejó pendiente la herramienta de release. Se quiere que cada push a `main` publique una
versión de forma automática si los commits lo justifican, que la primera versión sea `0.1.0` y que la
serie se mantenga en `0.y.z` hasta la entrega de la fase II.

## Opciones consideradas
1. **release-please.** Abre un pull request de release que hay que fusionar. No publica en cada push.
2. **semantic-release.** Publica en el mismo push: etiqueta, release de GitHub y `CHANGELOG.md`.

## Decisión
semantic-release, con `.github/workflows/release.yml` y `.releaserc.json`:
- Versiones fijadas: `semantic-release@25.0.9`, `@semantic-release/changelog@7.0.0`,
  `@semantic-release/git@11.0.1` y `conventional-changelog-conventionalcommits@9.3.1`. **No se puede
  subir el preset a la serie 10**: necesita `conventional-changelog-writer@9`, y los plugins de
  semantic-release 25 traen la versión 8. El generador de notas falla con
  `Missing helper: "conventional-changelog-conventionalcommits requires conventional-changelog-writer@9"`
  (comprobado el 2026-10-21).
- **Inicio en 0.1.0.** semantic-release siempre empieza en `1.0.0` si no hay etiquetas. Por eso se puso
  una etiqueta base `v0.0.0` (anotada, sin release) en el commit inicial. Desde ahí, el primer `feat` da `0.1.0`.
- **Cambios incompatibles en 0.y.z.** La regla `{ "breaking": true, "release": "minor" }` hace que suban la
  *minor* en vez de saltar a `1.0.0`.
- Las notas y el changelog tienen las secciones en español (Funcionalidades, Correcciones, Rendimiento).
  Los tipos `refactor`, `docs`, `test`, `build`, `ci` y `chore` no generan versión y no aparecen en las notas.
- Permisos mínimos: `contents: write`. Sin comentarios ni etiquetas en issues o PR.

Verificado el 2026-10-21 con un `--dry-run` sobre un repositorio de prueba, con estas mismas versiones:

| Commit (en orden) | Versión |
|---|---|
| `ci: …`, `docs: …` | ninguna |
| `feat(datanode): …` | 0.1.0 |
| `fix(metadata): …` | 0.1.1 |
| `perf(datanode): …` | 0.1.2 |
| `feat(proto)!: …` | 0.2.0 |
| `fix(client): …` + pie `BREAKING CHANGE:` | 0.3.0 |
| `refactor(metadata): …` / mensaje sin formato | ninguna |
| `feat(client): …` | 0.4.0 |

También se comprobó en GitHub Actions: el workflow detecta `v0.0.0`, tiene permiso de push y, con un
commit `ci:`, no publica.

## Consecuencias
- El primer commit publicable tiene que ser un `feat`. Si fuera un `fix`, la primera versión sería
  `0.0.1` (también comprobado).
- **Para publicar `1.0.0` en la fase II:** quitar la regla `breaking → minor` de `.releaserc.json` en un
  commit y después hacer un commit con `BREAKING CHANGE:` que justifique la versión estable. Va en un ADR nuevo.
- semantic-release hace un commit en `main` con el `CHANGELOG.md`. Antes de seguir trabajando después de un
  release hay que hacer `git pull`. Si se protege `main` contra pushes directos, el workflow necesita una excepción.
- Un commit con un tipo fuera de la lista no genera versión **y no avisa**. Si hiciera falta, se puede añadir
  validación con commitlint.
