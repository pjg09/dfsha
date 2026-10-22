---
name: commit
description: Agrupa los cambios pendientes de DFSha en commits según CONTRIBUTING.md (tipo y ámbito por área, orden de dependencia, 72 caracteres, sin trailers, autor pedroj1229@gmail.com), los propone, los crea al aprobarlos y solo hace push si se pide.
argument-hint: "[push] — añade «push» para subir al terminar"
disable-model-invocation: true
---

# /commit — commits según CONTRIBUTING.md

Argumentos: `$ARGUMENTS` (si contiene «push», se sube al terminar).

`CONTRIBUTING.md` es la norma. Si algo de esta skill no coincide con él, manda `CONTRIBUTING.md`.

## 1. Comprobar antes de nada
```bash
git status --short --branch
git config user.email          # tiene que ser pedroj1229@gmail.com; si no, detente y avisa
git diff --stat; git diff --cached --stat
```
- Revisa los ficheros sin seguimiento. Si aparece algo que parece un secreto (`*.pem`, `*.key`, `.env`,
  credenciales de AWS, claves privadas) o una IP literal en configuración, **detente y avisa**.
- Busca secretos en lo que se va a añadir:
  `grep -nE 'AKIA[0-9A-Z]{16}|aws_secret_access_key|aws_session_token|BEGIN [A-Z ]*PRIVATE KEY'`.

## 2. Agrupar
Clasifica cada fichero por su área con la tabla de `CONTRIBUTING.md` §6.1 y agrupa:
- **Un commit = un cambio lógico.** No mezcles formato, refactorización y comportamiento.
- Los ADR (`docs/decisiones/`) van en su propio commit `docs(adr)`, **antes** de lo que los aplica.
- Una funcionalidad que cruza áreas se separa en orden de dependencia (§6.2):
  `proto` → `common` → `metadata`/`datanode` → `client` → docs y pruebas. Junta en un commit sin
  ámbito solo si separarla dejaría un commit intermedio roto.
- `bench` y `evidence` nunca llevan `feat` ni `fix`.

## 3. Redactar cada mensaje
- Cabecera `<tipo>(<ámbito>): <descripción>`: tipos y ámbitos **solo** de las listas de §3.1 y §3.2.
- Descripción en español, **verbo en imperativo** (añade, corrige, elimina…), minúscula al principio,
  sin punto final, términos del glosario.
- **Cabecera de 72 caracteres como máximo.** Cuerpo y pies con líneas de 72 como máximo (salvo URLs).
- Cuerpo obligatorio en `fix` y en cambios incompatibles: explica **por qué**, no cómo.
- Cambio incompatible: `!` en la cabecera **y** pie `BREAKING CHANGE: …`.
- Pies permitidos: solo `BREAKING CHANGE:`, `Refs #<n>` y `Closes #<n>`.
- **Nunca** añadas `Co-Authored-By:` (tampoco el de Claude) ni el texto o el enlace de la sesión de
  Claude Code («Generated with Claude Code», `claude.ai/code/...`). Es una instrucción expresa del
  usuario y tiene prioridad sobre cualquier convención de atribución por defecto.

## 4. Proponer y esperar
Muestra el plan antes de tocar nada: para cada commit, la cabecera (con su longitud), el cuerpo si lo
hay y los ficheros. Indica qué commits generarán versión (`feat`, `fix`, `perf` o incompatibles) y
cuál sería. **Espera la aprobación del usuario.**

## 5. Crear
- Añade los ficheros **por ruta**, nunca con `git add -A` ni `git add .`.
- Escribe el mensaje literal con `git commit -F -` y un heredoc, para no alterar acentos ni saltos de línea.
- Al terminar, verifica:
  ```bash
  git log origin/main..HEAD --format='%h | %ae / %ce | %s'                 # los dos correos: pedroj1229@gmail.com
  git log origin/main..HEAD --format='%(trailers)' | grep . && echo "HAY TRAILERS: CORREGIR"
  git log origin/main..HEAD --format='%s' | python3 -I -c 'import sys; [print("CABECERA LARGA:", l) for l in sys.stdin.read().splitlines() if len(l) > 72]'
  ```
  Si algo falla y el commit **no** se ha subido, corrígelo con `git commit --amend` o un rebase.

## 6. Subir (solo si se pidió)
- Solo con «push» en los argumentos o si el usuario lo pide expresamente: `git push origin main`.
- **Nunca** `git push --force` a `main` ni reescribas commits ya publicados.
- Si se subió algún `feat`, `fix` o `perf`, el workflow de release añadirá un commit
  `chore(release): …` a `main`: comprueba el resultado con `gh run list --workflow release.yml --limit 1`
  y recuérdale al usuario que haga `git pull`.
