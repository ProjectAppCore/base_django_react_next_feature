---
name: git-commit
description: "Inspect git changes, generate a professional commit message with FEAT/FIX/DOCS prefix, and execute git add + commit + push. Defaults to the current repo (cwd). Cuando el repo del cwd es vps-ops-toolkit, tras un push exitoso propaga el commit al resto del fleet (otros VPS + dev si está prendida) vía Tailscale (ON por defecto, --no-propagate para saltar); un repo de proyecto nunca se propaga. Pass --all-repos to iterate over LOCAL_PROJECTS + toolkit on this host. git-commit NO tiene modo fleet: --all-vps y --all son error (no se commitea a ciegas en clones de otros VPS); para el eje fleet usar /git-sync --all-vps."
disable-model-invocation: true
allowed-tools: Bash, AskUserQuestion
argument-hint: "[--all-repos (todos los repos de este host)] [--no-propagate (no sincroniza el toolkit al fleet)]"
---

> **⚠️ How to invoke**:
> - Sin argumento: `/git-commit` → opera sobre el repo git del **directorio
>   actual (cwd)** — el repo desde el que se lanzó Claude Code. Se resuelve
>   con `git rev-parse --show-toplevel`; **NO se asume `vps-ops-toolkit`**.
>   ⚠️ **Ignorá el estado del hook `SessionStart`** (siempre reporta el
>   toolkit) para decidir el target — el target lo manda el cwd, no ese reporte.
> - Con `--all-repos`: `/git-commit --all-repos` → itera sobre `LOCAL_PROJECTS`
>   del host + `vps-ops-toolkit`. **Commitea el toolkit y los scaffolds `base_*`**
>   (los tres van directo a `master`); de los **clones principales de proyecto sólo
>   REPORTA** el `dirty` — el trabajo de sesión vive en `~/webapps/.wt/` y lo
>   entrega su propia sesión con `/pr-green`. En los repos commiteables: si está
>   clean, SKIP; si tiene cambios, generar mensaje propio y commit+push
>   independiente. **Convención del
>   fleet: `--all` = todos los VPS** (full-audit/git-status-report); git-commit
>   NO tiene modo fleet (no se commitea a ciegas en clones de otros VPS), por eso
>   el multi-repo-local es `--all-repos`. `--all` sigue funcionando como **alias
>   deprecado** de `--all-repos` (con warning).
> - Con `--no-propagate`: salta la propagación del toolkit al fleet (útil
>   offline / sin Tailscale). Combinable con `--all-repos`.
>
> **Dónde aterriza el commit (repos de proyecto del fleet):** SIEMPRE en el
> **worktree de sesión** (`~/webapps/.wt/<repo>/<slug>`), sobre TU rama, y el
> **primer push abre el PR** (git-branch-protocol §9 — `Sesión:`/`Intención:` en el
> body). En el **clon principal** de un repo de proyecto esta skill **se niega** en
> cualquier rama: es el checkout del servicio/deploy y el hook `PreToolUse` lo
> bloquea igual. Excepciones documentadas: `vps-ops-toolkit` (flujo trunk, commit
> directo a `master`) y los scaffolds `base_*`.
>
> No acepta nombres de proyecto individuales — para operar en un repo
> específico, lanzá Claude Code desde ese repo (o `cd` a él antes de invocar).
>
> **Propagación al fleet (ON por defecto, sólo cuando el repo es
> `vps-ops-toolkit`):** tras commit+push exitoso del toolkit, este skill corre
> la **Phase 2** que sincroniza la copia del repo en los otros entornos (otros
> VPS del fleet + dev machine si está prendida) vía Tailscale SSH. Si el repo
> del cwd es un proyecto (no el toolkit), o los repos de proyecto del modo
> `--all`, **NO se propagan** (viven en un solo VPS cada uno).

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): (1) flags explícitos → directo, sin menú;
(2) intención clara en la sesión ("commiteá esto", "guardá lo que hicimos") →
proponer el comando en una línea y esperar confirmación; (3) invocación
ambigua (¿este repo o todos los del host?) → UNA sola AskUserQuestion; (4)
nunca en fleet/headless/cron.

**Q1 — Alcance** (`multiSelect: false`):

| label | description | preview |
|---|---|---|
| Repo actual (Recommended) | commit + push del repo del cwd; si es el toolkit, propaga al fleet al final | `/git-commit` |
| Todos los repos de este host | un commit por repo dirty (LOCAL_PROJECTS + toolkit), mensaje propio por repo | `/git-commit --all-repos` |
| Repo actual sin propagar | commit + push sin sincronizar el toolkit al fleet (offline / sin Tailscale) | `/git-commit --no-propagate` |

**Qué NO se pregunta:** `--all-vps` y `--all` (error-by-design: no se commitea
a ciegas en clones de otros VPS — el eje fleet es `/git-sync --all-vps`).

## Phase 0 — Resolución de la lista de repos

> **Post-`EnterWorktree`: UN comando simple por llamada.** En un worktree nativo,
> Claude rechaza el comando con `$(...)`, `{a,b}`, `for`/`while` o heredoc con
> sustitución, y el que apunta al clon compartido (`git -C <clon principal>`,
> `cd <clon principal>`) — se cae el bloque entero. Por eso el modo default de esta
> skill **no computa nada en bash**: los valores salen de `session-worktree.sh
> status` y se escriben **literales**. Convención completa: `git-branch-protocol` §1
> del CLAUDE.md del repo. (El modo `--all-repos` corre desde el clon del toolkit,
> donde esos gates no existen.)

**Flags** — los parseás vos leyendo `$ARGUMENTS`; un bucle de parseo sería rechazado:

| Token | Efecto |
|---|---|
| (ninguno) | el repo del cwd; propagación al fleet ON si es `vps-ops-toolkit` |
| `--all-repos` | itera `LOCAL_PROJECTS` + toolkit de ESTE host (sólo desde el toolkit) |
| `--no-propagate` | no sincroniza el toolkit al fleet (offline / sin Tailscale). Combinable |
| `--all-vps` | **ERROR**: git-commit NO tiene modo fleet — no se commitea a ciegas en clones de otros VPS (pueden estar dirty o en una release, y el mensaje se redactaría sobre diffs que nunca viste). ¿Los repos de ESTE host? → `--all-repos` · ¿Sincronizar el toolkit en el fleet? → ya ocurre solo tras el push (o `/git-sync --all-vps`) · ¿Rebasar todo el fleet? → `/git-sync --all-repos --all-vps` |
| `--all` | **ERROR**: ambiguo y retirado. ¿Todos los repos de ESTE host? → `--all-repos` |
| cualquier otro | **ERROR**: argumento desconocido |

### Modo default (sin `--all-repos`) — dónde estás parado

**Primero el repo, después el tree.** El repo se decide con un comando simple y su
basename, nunca leyendo el texto de un mensaje de error:

```bash
git rev-parse --show-toplevel
```

- Basename **`vps-ops-toolkit`** (o el toplevel cae bajo `~/webapps/vps-ops-toolkit`)
  → **flujo trunk**: commit directo a `master`, sin PR, con la propagación de Phase 2.
  **No corras `status`**: el toolkit no usa worktrees de sesión. Saltá al flujo de
  abajo.
- Basename que empieza con **`base_`** (scaffold colgado del root de proyectos) →
  permitido: commitea directo a `master` y sigue el flujo normal de abajo.
- Cualquier otro repo → es un repo de proyecto del fleet; resolvé el tree:

  ```bash
  bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh status
  ```

  - **rc 0** → estás en TU worktree de sesión. El guard del clon principal ya está
    satisfecho por construcción. Del registro salen `repo` `branch` `base` `pr_number`
    `pr_state` `pr_url` `host_status`; se escriben **literales** más abajo.
    `host_status=wrong-host` ⇒ ⏭️ el trabajo vive en otro VPS: terminá y reportá el
    `vps_work=` de
    `bash ~/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh --check <project literal>`.
  - **rc 2** → estás en el **clon principal** de ese repo (o el cwd no es un repo git,
    y entonces ❌ abortá: lanzá Claude Code desde el repo a commitear, o usá
    `--all-repos`). ❌ guard — misma regla que el hook `PreToolUse`, función
    `guarded_clone` en `config/codex/pre-tool-use-policy.py`: guardado = CUALQUIER clon
    principal colgando DIRECTO del root de proyectos, esté o no en `projects.yml`,
    salvo `vps-ops-toolkit` y los `base_*` (que ya se resolvieron arriba). El clon
    principal es el checkout del servicio: no se commitea en NINGUNA rama.

    ```
    ❌ Clon principal de <repo>: acá no se commitea (git-branch-protocol §1).
       bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh create <prefijo> <slug>
       Claude: EnterWorktree path=<worktree=>  ·  Codex: cd <worktree=>   → re-invocá desde ahí.
    ```

Reportá `🔧 Modo: default (repo actual: <repo>) | propagación: ON|OFF`.

### Modo `--all-repos` — desde el clon del toolkit

Corre en el clon principal de `vps-ops-toolkit`, donde no hay aislamiento de worktree
que aplique. **Nunca entra a un worktree con `cd`**: los repos se tocan con `git -C`.

```bash
# pre-entry: corre en el clon principal, antes de EnterWorktree
OPS_ROOT="$HOME/webapps/vps-ops-toolkit"
source "$OPS_ROOT/scripts/lib/bootstrap-common.sh"
PROJECT_DEFS_QUIET=1 source "$OPS_ROOT/scripts/lib/project-definitions.sh"
REPOS=("${LOCAL_PROJECTS[@]}" "vps-ops-toolkit")
VALID_REPOS=()
for r in "${REPOS[@]}"; do
    if [ -d "$HOME/webapps/$r/.git" ]; then
        VALID_REPOS+=("$r")
    else
        echo "⏭️  $r — dir no existe o no es repo git (skip)"
    fi
done
echo "🔧 Modo: --all-repos (${#VALID_REPOS[@]} repos)"
printf '   - %s\n' "${VALID_REPOS[@]}"
```

Por cada repo de `VALID_REPOS`, el mismo guard en modo **REPORTE** (el barrido no
aborta, salta el repo):

```bash
# pre-entry: corre en el clon principal, antes de EnterWorktree
REPO_DIR="$HOME/webapps/$REPO"
echo "═══ 🎯 Repo objetivo: $REPO_DIR ($(git -C "$REPO_DIR" branch --show-current)) ═══"
MAIN="$(dirname "$(git -C "$REPO_DIR" rev-parse --path-format=absolute --git-common-dir)")"
ROOT="$(realpath -m "${FLEET_PROJECTS_ROOT:-$HOME/webapps}")"
GUARDED=0
if [ "$(realpath -m "$REPO_DIR")" = "$(realpath -m "$MAIN")" ] \
   && [ "$(dirname "$(realpath -m "$MAIN")")" = "$ROOT" ] \
   && [ "$REPO" != "vps-ops-toolkit" ] && [ "${REPO#base_}" = "$REPO" ]; then
    GUARDED=1
fi
if (( GUARDED == 1 )); then
    D="$(git -C "$REPO_DIR" status --porcelain | wc -l)"
    echo "⏭️  clon principal — dirty=$D se reporta, no se commitea (el trabajo de sesión va en .wt/)"
fi
```

Si ese bloque imprimió el `⏭️ clon principal`, **registrá la fila y pasá al siguiente
repo** sin commitear nada. En los repos commiteables (toolkit + scaffolds `base_*`) el
flujo de abajo corre con `git -C "$REPO_DIR"` en cada comando — nunca con `cd`.

**Política por iteración**:
- Si `git status --porcelain` está vacío → SKIP silencioso (registrar en
  summary como "0 cambios"). No generar mensaje ni intentar commit.
- Si hay cambios → inspeccionar el diff de ESE repo, generar un mensaje
  FEAT/FIX/DOCS propio basado en SUS cambios (no agregado entre repos),
  ejecutar `git add` selectivo + `git commit` + `git push` (con
  `-u origin <rama>` si la rama no tiene upstream).
- **En un worktree de sesión** (repo de proyecto): tras el **primer push**,
  ASEGURÁ el PR (git-branch-protocol §9) y reportá su URL. Primero mirá si ya hay uno:
  ```bash
  gh pr view --json url,state -q '.state + " " + .url'
  ```
  Si no hay PR abierto, crealo con el `base` **literal** que imprimió
  `session-worktree.sh status` (post-entry no hay bash que lo calcule, y `--base ""`
  hace fallar el create):
  ```bash
  gh pr create --base <base literal del registro> --fill --body "Sesión: <tu sesión>
  Intención: <1 línea: qué entrega>

  <resumen>"
  ```
  El body va como texto literal entre comillas dobles con saltos de línea reales —
  **nunca** `--body "$(printf …)"`: la sustitución de comando muere en Gate A y se cae
  el `gh pr create` entero. Nunca se pushea a `main`/`master` ni a la rama release de
  un proyecto: el PR de sesión es lo que entrega el trabajo, y el merge no es de esta
  skill.
- Si `git push` falla (no upstream, conflict remoto, etc.) → marcar el
  repo como "commit OK, push pendiente" y continuar con el siguiente.
  No abortar el loop.

En modo default (sin `--all-repos`) hay un solo repo — el del cwd — y no hay loop
real: el flujo corre una vez, con el cwd ya anclado (en un worktree de sesión el cwd
ES el worktree: no hay `cd` que hacer).

---

Run the following commands to inspect the current Git changes:

1. `git status`
2. `git diff`

Analyze the output of those commands and generate a concise, professional commit message in English.

Format rules:
- Use `FEAT: [description]` if I added new tests, features, or enhancements.
- Use `FIX: [description]` if I fixed a bug or a failing test.
- Use `DOCS: [description]` if I only updated documentation (for example README, comments, or docstrings).

Then execute the necessary Git commands to stage, commit, and push the changes.

Execution rules:
- First, run the exact `git add` command(s) needed to stage only the relevant files.
- Then run: `git commit -m "[message]"`
- Finally, run: `git push`

Output rules:
1. Show the exact `git add` command(s) you will run.
2. Show the exact `git commit -m "[message]"` command before running it.
3. Show the exact `git push` command before running it.
4. Then execute all commands.
5. If there is nothing to commit, clearly say so and do not run commit or push.
6. If `git push` requires a specific remote or branch, detect it and use the correct command.
7. En un repo de proyecto, cerrá con `PR URL: <url>` — el del PR recién creado o el
   ya existente (`gh pr view --json url -q .url`). En `vps-ops-toolkit`:
   `PR URL: n/a (trunk flow, push directo a master)`.

---

## Phase 2 — Propagación del toolkit al fleet (ON por defecto)

Esta fase sincroniza la copia de **`vps-ops-toolkit`** en los otros entornos del
fleet (los otros VPS + la dev machine **si está prendida**) con el SHA exacto
que acabás de pushear, vía Tailscale SSH. Un host sólo avanza si está en
`master`, limpio y su HEAD es ancestro del target; el cambio es `--ff-only`,
sin `checkout`, `rebase`, `autostash` ni hooks Git. El resultado `SYNCED` se
publica únicamente después de reconciliar además el user-level completo
(incluidos `permissions+hooks`, preservando las keys runtime de Claude) y el
runtime Codex/MCP ligado al lockfile exacto. El host desde el que corre también
reconcilia esa generación, incluso si no hay peers online. Durante la migración
one-shot de los runtimes MCP, `SYNCED` puede venir acompañado de
`LEGACY_CLEANUP_PENDING strict=false quiet_week_ready=false`: Git y el runtime
externo sí quedaron entregados, pero el exec-set todavía no es estricto y esa
salida suma warning/exit 1. El propagador nunca borra los roots legacy desde una
sesión activa.

**Cuándo corre** — sólo si TODAS se cumplen:
- El repo commiteado es **`vps-ops-toolkit`** (default con cwd en el toolkit, o
  la iteración `--all` del toolkit). Un repo de proyecto — sea el del cwd en
  modo default, o los de `--all` — **NUNCA** se propaga (viven en un solo VPS
  cada uno). El script `propagate-toolkit-commit.sh` siempre propaga el toolkit
  sin importar el cwd, así que este gate es responsabilidad de la skill.
- Se hizo un commit real **y** `git push` tuvo éxito en esta corrida.
- `PROPAGATE == 1` (es decir, NO se pasó `--no-propagate`).

Si el push falló (no upstream, conflicto remoto) o no hubo cambios → **saltar**
esta fase (no hay nada nuevo en el remoto que jalar). El commit ya hecho nunca
se revierte por una falla de propagación.

**Ejecución (mediada por vos, igual que la generación del mensaje):**

1. **Guard obligatorio** — confirmar que el repo commiteado ES el toolkit antes
   de propagar (en modo default el cwd puede ser un proyecto). Dos comandos simples,
   no un `if` con sustitución: el primero te dice dónde estás, el segundo sólo corre
   si el toplevel ES `~/webapps/vps-ops-toolkit`:
   ```bash
   git rev-parse --show-toplevel
   ```
   ```bash
   git rev-parse HEAD
   ```
   Copiá ese SHA completo como literal en el comando siguiente (sin
   sustitución de shell):
   ```bash
   bash ~/webapps/vps-ops-toolkit/scripts/maintenance/propagate-toolkit-commit.sh --apply --target=<sha-completo>
   ```
   Si el toplevel es otro repo: `⏭️ Repo no-toolkit (<repo>) — sin propagación al
   fleet.` y **no corras** los comandos de SHA/propagación.
2. **Si el exit code es `75`** (Tailscale pide autorización interactiva): el
   script ya imprimió un link `https://login.tailscale.com/...`. **Mostrale el
   link tal cual al operador**, pedile que lo abra y autorice con la cuenta del
   fleet, y **esperá su confirmación**. Luego **re-ejecutá el mismo comando**
   (es idempotente; los hosts ya sincronizados reportan al instante). Repetí
   hasta que el exit code deje de ser `75`. Una sola autorización habilita TODOS
   los VPS de la ventana de re-auth.
   - **NO** caigas a `ssh` directo, **NO** abortes, **NO** asumas que un VPS
     está caído. Es el flujo normal de auth de Tailscale (ver CLAUDE.md
     "Flujo de auth de Tailscale SSH").
3. Reportá el resumen por host del script:
   - `SYNCED <sha-completo>` + `TOOLKIT_EXECSET_STRICT_CURRENT` → **generación
     integral y exec-set estricto**: Git exacto, user-level y Codex/MCP listos.
     Nunca significa solamente “HEAD avanzó”.
   - `SYNCED <sha-completo>` + `LEGACY_CLEANUP_PENDING strict=false
     quiet_week_ready=false` → Git/user-level/runtime externo entregados, pero
     quedan los dos roots legacy físicos para no romper sesiones anteriores.
     Clasificar como 🟡 `SYNCED_CLEANUP_PENDING`; el exit 1 es deliberado. No
     iniciar quiet week ni instalar la generación root-owned hasta cerrar todas
     las sesiones antiguas, ejecutar el cleanup explícito documentado por
     `setup-runtime.sh` y repetir el check estricto.
   - `SYNC_BLOCKED <causa>` → el host rechazó el avance (rama incorrecta,
     tree sucio, target distinto o no-fast-forward); no hace checkout, rebase
     ni autostash. Revisá el estado y corregí la causa explícitamente.
   - `SYNC_ERROR <causa>` → una postcondición o la reconciliación
     user-level/runtime falló. Puede que Git ya haya llegado al target, pero el
     host **no** cuenta como sincronizado; corregí la causa y reintentá el mismo
     comando exacto (el retry es idempotente y vuelve a validar todo).
   - `UNREACHABLE` → host inalcanzable (dev apagada, VPS caído); warning, seguí.

En modo `--no-propagate`, omití esta fase por completo y decílo en el resumen.

---

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos
(reglas de gating de [[_output-protocol]] §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| --all-repos | un commit por cada repo dirty de ESTE host (mensaje propio por repo) | `/git-commit --all-repos` |
| Re-run sin propagar | commit+push sin sincronizar el toolkit al fleet (offline / sin Tailscale) | `/git-commit --no-propagate` |
| Dejar el PR en verde (sin merge) | *repo de proyecto*: espera el CI del PR de TU rama y corre el fix loop; no mergea | `/pr-green` |
| Green gate + propagación | *toolkit*: Path B (green gate local + push a master + fleet) — **operador** | `/merge-when-green` |

NO ofrecer `--all-vps` ni `--all`: son error-by-design en git-commit (no se
commitea a ciegas en clones de otros VPS) — el eje fleet es `/git-sync --all-vps`.

## Output final

Reportar siguiendo [[_output-protocol]]. Plantilla específica de esta skill:

🟢 git-commit OK   (🟡 si el push quedó pendiente o un host requiere sync manual; ⏸️ si Tailscale pide auth (exit 75); ⏭️ si no había cambios)

| Dimensión | Estado | Detalle |
|---|---|---|
| Cambios inspeccionados | ✅ | `git status` + `git diff` revisados |
| Commit creado | ✅ | FEAT/FIX/DOCS según el diff — `git commit -m "..."` |
| Push | ✅ | `git push` al upstream OK |
| PR | ✅ | #<n> — <url> (⏭️ `n/a` en el toolkit: trunk flow) |
| Propagación al fleet | ✅ | sólo si el repo es vps-ops-toolkit; ver tabla por host |

En `--all` anteponer una columna `repo` (un bloque de filas por repo). Un repo de
proyecto (no el toolkit) marca "Propagación al fleet" como ⏭️ (no se propaga).

Propagación del toolkit — una fila por host:

| Host | Estado | Detalle |
|---|---|---|
| vps-projectapp-prod | ✅ | `SYNCED <sha-completo>` + `TOOLKIT_EXECSET_STRICT_CURRENT` |
| vps-gym | 🟡 | `SYNCED_CLEANUP_PENDING` — Git/runtime listos; quiet week bloqueada hasta cleanup |
| dev | ⏭️ | `UNREACHABLE` (apagada) |

## Next steps
- (host con `SYNC_BLOCKED`) revisar rama/tree/ancestry; no se corrige con checkout o autostash automático
- (host con `SYNC_ERROR`) corregir la postcondición indicada y reintentar el mismo `--target=<sha>`
- (host con `SYNCED_CLEANUP_PENDING`) cerrar sesiones antiguas, ejecutar el
  cleanup legacy confirmado desde una terminal independiente y repetir
  `propagate-toolkit-commit.sh --check --target=<sha>` hasta obtener strict
- (si el push quedó pendiente) resolver upstream/conflicto y `git push`
