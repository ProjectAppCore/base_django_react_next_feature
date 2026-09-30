---
name: "git-sync"
description: "Sync the current branch: inspecciona stashes existentes (marca obsoletos/viejos), detecta PRs abiertos vía gh CLI y elige target PR-aware (protocolo por sesión: una rama pusheada con PR se sincroniza sólo contra su propio upstream — la base movida se absorbe con merge, nunca rebase; N PRs de sesión son estado normal), luego resuelve SHAs remotos exactos + rebase + conflict resolution. Dos ejes ortogonales combinables: --all-repos (todos los repos de ESTE host) y --all-vps (el toolkit en TODOS los VPS). Sin flags: el repo del cwd. --all quedó retirado (error) por ambiguo."
---

# Git Sync

Rebase the current branch onto its parent (`main` / `master`) so it picks up work that teammates have merged. Also pulls the current branch's own remote first, handles dirty working trees, and walks through any rebase conflicts.

> **⚠️ How to invoke** — dos ejes **ortogonales y combinables**: *qué repos* y
> *en qué hosts*.
>
> | Invocación | Repos | Hosts |
> |---|---|---|
> | `$git-sync` | el repo del cwd | este host |
> | `$git-sync --all-repos` | `LOCAL_PROJECTS` + toolkit | este host |
> | `$git-sync --all-vps` | **sólo `vps-ops-toolkit`** | todos los VPS |
> | `$git-sync --all-repos --all-vps` | toolkit + `LOCAL_PROJECTS` de cada host | todos los VPS |
>
> - **Sin argumento**: opera sobre el repo git del **cwd** — el repo desde el que
>   se lanzó Claude Code. Se resuelve con `git rev-parse --show-toplevel`; **NO se
>   asume `vps-ops-toolkit`**. ⚠️ **Ignorá el estado del hook `SessionStart`**
>   (siempre reporta el toolkit) para decidir el target — lo manda el cwd.
> - **`--all-repos`**: en un VPS son los proyectos cuyo `server:` matchea el
>   hostname; en dev, todos los `status: active`.
> - **`--all-vps`** solo, en cada VPS remoto opera sobre `vps-ops-toolkit`: es el
>   único repo con el mismo path en todos los hosts.
> - **`--all` quedó retirado** (error con guía): era ambiguo entre los dos ejes.
>
> No acepta nombres de proyecto individuales — para operar en un repo
> específico, lanzá Claude Code desde ese repo (o `cd` a él antes de invocar).

> **⚠️ Qué reciben los hosts REMOTOS (`--all-vps`)**: el toolkit recibe el core
> no-interactivo de propagación. Los repos de proyecto son árboles desplegados:
> aun con `--all-repos` se inspeccionan por SHA exacto + behind, pero **no se
> rebasean ni despliegan**. Actualizarlos requiere el flujo
> explícito del proyecto y su transacción de Integrity.
>
> El toolkit va contra `origin/master`. Para cada proyecto se informa su propio
> upstream y el número de commits pendientes; nunca se toca su branch o tree.

## Cómo invocar este skill

Gating ($output-protocol §4): (1) flags explícitos → ejecutar directo, sin
menú; (2) intención clara por la sesión (p.ej. "sincronizá todo el fleet") →
proponer el comando en una línea y esperar confirmación; (3) sin argumentos /
intención difusa → UNA sola AskUserQuestion con Q1; (4) nunca dentro de un
barrido `--all-repos`/`--all-vps` ni en headless/cron — sólo en sesión
interactiva single-target.

**Q1 — Alcance** (`multiSelect: false` — los dos ejes combinados forman 4 modos excluyentes):

| label | description | preview |
|---|---|---|
| Repo actual (Recommended) | el repo del cwd contra su upstream + target PR-aware, sólo este host | `$git-sync` |
| --all-repos (este host) | LOCAL_PROJECTS + toolkit de ESTE host, flujo interactivo completo | `$git-sync --all-repos` |
| --all-vps (fleet) | sólo `vps-ops-toolkit` en TODOS los VPS; el remoto recibe el core no-interactivo (conflicto ⇒ abort + reporte, sin stash inspection ni retargeting PR-aware) | `$git-sync --all-vps` |
| Ambos ejes | toolkit + LOCAL_PROJECTS de cada host del fleet; en los remotos siempre el core no-interactivo | `$git-sync --all-repos --all-vps` |

**Qué NO se pregunta:** `--all` (retirado, error-by-design con guía) jamás se
ofrece; los drops de stash no son picker pre-run — se ofrecen post-run,
per-stash y con la evidencia OBSOLETO/VIEJO de esta corrida (ya están en
`## Acciones disponibles`).

---

## Phase 0 — Resolución de la lista de repos

> **Post-`EnterWorktree`: UN comando simple por llamada.** En un worktree nativo,
> Claude rechaza el comando con `$(...)`, `{a,b}`, `for`/`while` o heredoc con
> sustitución, y el que apunta al clon compartido (`git -C <clon principal>`,
> `cd <clon principal>`) — se cae el bloque entero. Por eso el flujo single-repo de
> esta skill **no computa nada en bash**: los valores salen de `session-worktree.sh
> status` y se escriben **literales**. Convención completa: `git-branch-protocol` §1
> del CLAUDE.md del repo. (Los ejes `--all-repos` / `--all-vps` corren desde el clon
> del toolkit, donde esos gates no existen.)

**Flags** — los parseás vos leyendo `$ARGUMENTS`; un bucle de parseo sería rechazado.
Los dos ejes son ortogonales y combinables:

| Token | Efecto |
|---|---|
| (ninguno) | el repo del cwd, en este host |
| `--all-repos` | `LOCAL_PROJECTS` + toolkit de ESTE host |
| `--all-vps` | sólo `vps-ops-toolkit`, en TODOS los VPS (Phase 8) |
| `--all` | **ERROR**: ambiguo y retirado. ¿Todos los repos de ESTE host? → `--all-repos` · ¿El toolkit en TODOS los VPS? → `--all-vps` · ¿Ambos ejes? → los dos flags |
| cualquier otro | **ERROR**: argumento desconocido |

**Modo default** — hay un solo repo, el del cwd, y **no hay `cd`**: el cwd ya es el
repo (o tu worktree). No hay loop real: las Phases 1-7 corren una vez.

**Modo `--all-repos` / `--all-vps`** — desde el clon del toolkit:

```bash
# pre-entry: corre en el clon principal, antes de EnterWorktree
OPS_ROOT="$HOME/webapps/vps-ops-toolkit"
source "$OPS_ROOT/scripts/lib/bootstrap-common.sh"
PROJECT_DEFS_QUIET=1 source "$OPS_ROOT/scripts/lib/project-definitions.sh"
REPOS=("${LOCAL_PROJECTS[@]}" "vps-ops-toolkit")   # con --all-vps solo: sólo el toolkit
VALID_REPOS=()
for r in "${REPOS[@]}"; do
    if [ -d "$HOME/webapps/$r/.git" ]; then VALID_REPOS+=("$r"); else echo "⏭️  $r — skip"; fi
done
echo "🔧 repos a procesar: ${#VALID_REPOS[@]}"
printf '   - %s\n' "${VALID_REPOS[@]}"
```

Las Phases 1-7 corren **una vez por repo** de `VALID_REPOS`, con `git -C
"$HOME/webapps/$REPO"` en cada comando — **nunca** con `cd` a un worktree ajeno.

**Política de errores**: si una iteración termina en conflicto, error de fetch o de
rebase, reportá el error con el comando exacto para resolverlo
(`git -C <repo> rebase --abort` o similar), marcá el repo como FALLO en el summary y
**continuá con el siguiente**. No abortes el loop completo. Un rebase a medio resolver
se registra como "⚠️ con conflictos pendientes" y se notifica al cierre.

---

## Phase 0.1 — ¿Dónde estás parado? (guard del clon principal)

Antes de tocar nada, clasificá el tree de ESTE repo. Se aplica **por repo**, también
dentro de `--all-repos`.

```bash
bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh status
```

- **rc 0** → **worktree de sesión**. Flujo normal (Phases 0.3 → 7) sobre TU rama; es
  el caso esperado en un repo de proyecto. Del registro salen `repo` `branch` `base`
  `default_branch` `resolved_branch` `deploy_branch` `open_pr` `pr_state`
  `pr_number` `release_merge` `host_status` `dirty` `unpushed` `upstream` — **no los
  recalcules**.
  `host_status=wrong-host` ⇒ ⏭️ terminá para ese repo; el VPS correcto (`vps_work=`)
  sale de
  `bash ~/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh --check <project literal>`.
- **rc 2** → no hay worktree: estás en un clon principal (o fuera de un repo git).
  Identificá cuál y en qué rama:

  ```bash
  git rev-parse --show-toplevel
  ```
  ```bash
  git status -sb
  ```

  - **`vps-ops-toolkit` y los scaffolds `base_*`** → flujo normal: commitean directo a
    `master` y se sincronizan como siempre.
  - **Clon principal guardado** (cualquier otro clon colgado del root de proyectos) →
    **nunca se stashea y nunca se rebasea un tree sucio**; es el checkout del servicio
    corriendo:
    - **sucio** → **⚠️ anomalía: trabajo de otra sesión o del operador — no se toca.**
      Reportá el conteo y **terminá para ese repo** (sin fetch destructivo, sin stash,
      sin rebase, sin checkout).
    - limpio y en la rama de deploy (el `deploy_branch=` del resolver:
      `bash ~/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh --check <repo>`)
      → consultar `refs/heads/<deploy_branch>` con `ls-remote`; si el objeto
      falta, traer sólo su SHA con `--no-auto-gc --no-tags
      --no-write-fetch-head`; reportar `deploy pendiente` y delegar a
      `scripts/deployment/deploy-project.sh --apply`. **Nunca avanzar el clon
      desplegado desde git-sync.**
    - limpio y en OTRA rama → **reportá y no hagas checkout**: mover la rama del clon
      de deploy es del operador (o de `migrate-project`), no de un sync.

  Para el caso limpio/en-rama-deploy, resolvé el SHA sin variables de shell:
  sustituí primero `<deploy_branch literal>` por el valor del registro y corré
  un comando por llamada.

  ```bash
  GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin 'refs/heads/<deploy_branch literal>'
  ```

  La salida debe ser una única línea `<SHA> refs/heads/<deploy_branch>`. Copiá su
  primera columna y escribila literalmente en cada comando siguiente:

  ```bash
  printf '%s\n' '<DEPLOY_SHA literal>' | grep -Eq '^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$'
  ```
  ```bash
  git cat-file -e '<DEPLOY_SHA literal>^{commit}'
  ```

  Si `cat-file` retorna no cero, materializá sólo ese objeto y repetí `cat-file`:

  ```bash
  GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin '<DEPLOY_SHA literal>'
  ```
  ```bash
  git cat-file -e '<DEPLOY_SHA literal>^{commit}'
  ```
  ```bash
  git rev-list --count 'HEAD..<DEPLOY_SHA literal>'
  ```

  Reportá el número impreso como `deploy pendiente=<N>` y este comando manual,
  reemplazando ambos placeholders por sus valores literales:

  ```text
  bash $HOME/webapps/vps-ops-toolkit/scripts/deployment/deploy-project.sh --apply --project=<repo literal> <deploy_branch literal>
  ```

En los casos de clon principal **guardado**, esta skill **no corre** las Phases 0.5-6
(stash inspection, rebase, absorción de la base, resolución de conflictos): pasa
directo al Output final con su fila por repo.

---

## Phase 0.3 — Verificar `gh` CLI (dependencia obligatoria)

```bash
gh auth status
```

Falla ⇒ **ERROR** y salida: `gh` es dependencia obligatoria para la detección de PRs.
Sin la CLI: `sudo bash ~/webapps/vps-ops-toolkit/scripts/bootstrap/install-github-cli.sh --apply`.
Sin auth: `gh auth login` (GitHub.com → HTTPS → Login with web browser).

```bash
gh --version
```

---

## Phase 0.5 — Stash inspection (visibilidad + obsoletos + viejos)

Antes de tocar el working tree, listar y clasificar los stashes existentes. El
operador debe saber qué hay acumulado **antes** de que la skill cree su propio stash
en Phase 1.

```bash
git stash list --format='%gd|%ci|%cr|%gs'
```

- Salida vacía → ✅ sin stashes: saltá el resto de la fase.
- Con líneas → clasificá **vos** cada una a partir de la fecha (`%ci`) y la relativa
  (`%cr`): **VIEJO** = más de 30 días. Y por cada stash, DOS llamadas con la ref
  literal (`stash@{0}`, `stash@{1}`, … — un comando por stash, nunca un bucle):

```bash
git stash show --stat stash@{0}
```
```bash
git stash apply --check stash@{0}
```

`apply --check` con exit ≠ 0 = todos los hunks chocarían con el árbol actual ⇒
**OBSOLETO probable** (el contenido ya vive en commits).

**Reglas:**
- La skill **nunca** ejecuta `git stash drop` por su cuenta — sólo reporta los
  candidatos (`git stash drop stash@{N}    # OBSOLETO` / `# VIEJO (>30d)`) en
  `## Next steps`, para copy-paste manual cuando el operador apruebe.
- Estados posibles en el Output final:
  - ✅ — sin stashes o todos legítimos (no obsoletos, no >30d)
  - ⚠️ — N candidatos a drop reportados en `## Next steps`
  - ❌ — error leyendo stashes (raro)

---

## Phase 1 — Inspect current state

```bash
git status
git branch -vv
git log --oneline -5
```

**Rules:**
- If `git status` shows uncommitted changes: **warn the user**. La oferta de
  `git stash` + `git stash pop` vale **sólo en TU worktree de sesión o en el
  toolkit**, y aun ahí se prefiere **commitear en tu rama** (el trabajo de una
  sesión vive en commits, no en stashes). En el **clon principal de un repo de
  proyecto NUNCA** se ofrece: Phase 0.1 ya cortó ahí. Do not proceed without their
  confirmation.
- Note the current branch name and its upstream (if any).

---

## Phase 2 — Detect parent branch + resolve PR-aware rebase target

Esta fase resuelve **dos cosas**: el parent default (`main`/`master`) y el `TARGET`
real contra el que se va a rebasear, que puede ser:

- SHA anunciado de `<parent>` (default)
- SHA anunciado de `<base-de-integración>` para una rama local sin PR (la release en repos que
  participan del flujo release)
- **ninguno** para una rama pusheada con PR: sin rebase de base — Phase 4 (su
  upstream) + merge opcional de la base en Phase 5 Case C

### Sub-fase 2a — Parent y base, del registro (sin recalcular nada)

Ya los tenés del `session-worktree.sh status` de Phase 0.1:

| Clave del registro | Qué es |
|---|---|
| `default_branch` | el **parent** (`main`/`master`), resuelto sin red desde `origin/HEAD` |
| `branch` | la rama actual |
| `base` | la base de integración de ESTA rama: la del PR abierto si tiene, si no la release (`pr_state_coord=single`), si no la default |
| `pr_state` / `pr_number` | si la rama actual ya tiene PR, y cuál |
| `open_pr` | los candidatos a release (PRs abiertos con base=default), separados por comas |

En un clon principal (rc 2 de `status`) el parent sale de un comando simple:

```bash
git symbolic-ref --short refs/remotes/origin/HEAD
```

Sin él, probá `git show-ref --verify --quiet refs/remotes/origin/main` y después
`refs/remotes/origin/master`; si ninguna existe, **ERROR**: no se puede determinar el
parent branch.

### Sub-fase 2b — PRs abiertos (vía gh CLI)

```bash
gh pr list --state open --json number,title,headRefName,baseRefName,isDraft,updatedAt -q '.[] | "#\(.number) [\(if .isDraft then "DRAFT" else "OPEN" end)] \(.headRefName) → \(.baseRefName)  — \(.title)"'
```

**Política del operador (protocolo por sesión, 2026-08-17):** N PRs de sesión abiertos
son **estado normal** (1 sesión = 1 rama = 1 PR); el conteo total ya no dispara
warnings. Lo que sí se vigila, contando **vos** sobre esa salida (y contra el
`open_pr=` del registro):

- **Candidatos a release** = los PRs con `→ <default_branch>`. Más de 1 ⇒
  ⚠️ release ambigua: en repos con release activa los PRs de sesión van con
  `base=<release>` (stacked); re-basar los mal abiertos con
  `gh pr edit <n> --base <release>`.
- **PRs de sesión fríos** = los que NO apuntan a la default y llevan >48 h sin
  actividad (`updatedAt`) ⇒ deuda de drenaje: sugerí `$merge-queue`. Un candidato a
  release viejo NO es un PR de sesión frío, por eso el filtro excluye la default. Si
  querés el filtro hecho por gh (con la default **literal**):

```bash
gh pr list --state open --json number,headRefName,baseRefName,updatedAt -q '.[] | select(.baseRefName != "<default_branch literal>") | select((now - (.updatedAt|fromdateiso8601)) > 172800) | "⚠️  frío >48h: #\(.number) \(.headRefName) → \(.baseRefName)"'
```

### Sub-fase 2c — Resolver el `TARGET` del rebase

Regla del protocolo por sesión: **una rama pusheada con PR jamás se rebasea sobre su
base** (el force push está denegado en el fleet — el rebase la dejaría imposible de
pushear). Su sync es contra su **propio upstream** (Phase 4), y una base movida se
absorbe con **merge** (Phase 5, Case C). El "rebase apilado sobre el PR abierto" del
protocolo viejo (todas las sesiones sobre una rama) quedó retirado: parado en
`main`/`master` ya no se adopta la rama de ningún PR.

Se decide leyendo el registro, sin bash:

| Situación | `TARGET` | Razón |
|---|---|---|
| `branch` = `default_branch` | SHA de `refs/heads/<default_branch>` | **Case A** — parado en el parent: rebase sobre el tip anunciado |
| `pr_state` = `OPEN` (rama pusheada con PR, de sesión o release) | **ninguno** | **Case C** — sync sólo contra su upstream; la base (`base` del registro) se absorbe con merge, nunca con rebase |
| resto (rama local sin PR) | SHA de `refs/heads/<base>` | **Case B** — rebase contra su base de integración (la release en repos participantes, el parent en prod-directos) |

Asegurá que el commit anunciado existe localmente antes de usarlo (sólo
Cases A y B). `<TARGET_BRANCH literal>` sale de la tabla. Reemplazá ese
placeholder antes de ejecutar la sonda:

```bash
GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin 'refs/heads/<TARGET_BRANCH literal>'
```

La salida debe ser una única línea para esa ref. Copiá la primera columna y
escribí ese mismo `<TARGET_SHA literal>` en cada llamada posterior:

```bash
printf '%s\n' '<TARGET_SHA literal>' | grep -Eq '^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$'
```
```bash
git cat-file -e '<TARGET_SHA literal>^{commit}'
```

Si `cat-file` retorna no cero, traé únicamente el objeto anunciado y verificá
de nuevo el mismo literal:

```bash
GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin '<TARGET_SHA literal>'
```
```bash
git cat-file -e '<TARGET_SHA literal>^{commit}'
```

Conservá en tu registro de la corrida ese SHA literal como `TARGET_SHA`; no hay
una variable de shell que sobreviva entre bloques.

Escribí `TARGET_SHA`, `TARGET_BRANCH` y la razón **literales** en las Phases 4,
5 y 7 — no hay variables que sobrevivan entre bloques, y post-entry tampoco hay
`$(...)` que las reconstruya.

---

## Phase 3 — Resolver el SHA exacto del upstream propio

Corré este bloque sólo cuando el registro de Phase 0.1 indica un upstream
configurado para la rama actual. Si existe upstream pero la sonda no devuelve
un SHA válido, abortá el sync: continuar con una ref local stale inventaría un
verde. Una rama local todavía sin upstream salta directamente a Phase 5.

Reemplazá `<rama literal>` por `branch` del registro antes de la llamada:

```bash
GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin 'refs/heads/<rama literal>'
```

Exigí una única línea para esa ref, copiá su primera columna y usá exactamente
el mismo SHA literal en cada comando:

```bash
printf '%s\n' '<CURRENT_REMOTE_SHA literal>' | grep -Eq '^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$'
```
```bash
git cat-file -e '<CURRENT_REMOTE_SHA literal>^{commit}'
```

Si `cat-file` retorna no cero, traé sólo ese objeto y repetí la verificación:

```bash
GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin '<CURRENT_REMOTE_SHA literal>'
```
```bash
git cat-file -e '<CURRENT_REMOTE_SHA literal>^{commit}'
```

Si cualquier sonda falla o no devuelve el formato exacto, abortá con
`ERROR: upstream remoto no evaluable`. Conservá el SHA copiado como el
`CURRENT_REMOTE_SHA` literal de las fases siguientes.

`ls-remote` no escribe el repo. El fetch opcional materializa sólo el objeto
inmutable; no mueve `FETCH_HEAD`, refs/remotes, tags ni packed-refs.

---

## Phase 4 — Sync the current branch with its own remote

> **Las Phases 4-6 (rebase, merge de la base, `git add` de conflictos, stash) sólo
> corren en un worktree de sesión o en `vps-ops-toolkit`.** El clon principal de un
> repo de proyecto nunca llega hasta acá: Phase 0.1 lo reportó como current o
> `deploy pendiente` y delegó cualquier avance al deploy tipado.

**Skip this phase** if the current branch **is** the parent (handled in Phase 5) or if there is no upstream configured.

Otherwise, preview incoming commits from the current branch's own remote usando
el `<CURRENT_REMOTE_SHA literal>` impreso por Phase 3:

```bash
git log --oneline HEAD..<CURRENT_REMOTE_SHA literal> --
```

- If empty: nothing to pull from own remote — continue to Phase 5.
- If there are commits: rebase onto that immutable remote tip:
  ```bash
  git rebase <CURRENT_REMOTE_SHA literal>
  ```

If this rebase stops with conflicts → Phase 6. When it finishes cleanly, continue to Phase 5.

---

## Phase 5 — Rebase (o merge) against the resolved `TARGET`

Usa los literales de Phase 2: `TARGET_SHA` (tip del parent, o de la base de
integración para ramas locales sin PR, o **vacío** para ramas pusheadas con PR).

Todos los nombres de rama van **literales**, tomados del registro de Phase 0.1.

**Case A — current branch IS the parent (`main`/`master`):**

```bash
git rebase <TARGET_SHA literal>
```

Then skip to Phase 7. (En este caso `TARGET_SHA` es el tip anunciado del parent.)

**Case B — rama local SIN PR (aún no pusheada):**

Preview qué tiene `TARGET` que current no tiene:

```bash
git log --oneline HEAD..<TARGET_SHA literal> --
```

- If empty: already up to date with `TARGET` — skip to Phase 7.
- If there are commits: rebase onto `TARGET`:
  ```bash
  git rebase <TARGET_SHA literal>
  ```

If the rebase stops with conflicts → Phase 6.

**Case C — rama pusheada con PR (sin `TARGET`):**

El sync real ya ocurrió en Phase 4 (su propio upstream). Acá sólo se decide si hace
falta **absorber la base** (el `base` del registro — la base del PR — se movió por
merges de otras sesiones):

Reemplazá `<base literal>` por `base` del registro y ejecutá:

```bash
GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin 'refs/heads/<base literal>'
```

La salida debe ser una única línea para esa ref. Copiá su primera columna y
reutilizá exactamente ese SHA literal:

```bash
printf '%s\n' '<BASE_SHA literal>' | grep -Eq '^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$'
```
```bash
git cat-file -e '<BASE_SHA literal>^{commit}'
```

Si `cat-file` retorna no cero, traé sólo el objeto anunciado y repetí la
verificación:

```bash
GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin '<BASE_SHA literal>'
```
```bash
git cat-file -e '<BASE_SHA literal>^{commit}'
```

Si cualquier sonda falla o el formato no es exacto, abortá con
`ERROR: base remota no evaluable`. El SHA copiado es el `<BASE_SHA literal>` de
las llamadas siguientes.

Con el `<BASE_SHA literal>` impreso:

```bash
git rev-list --count HEAD..<BASE_SHA literal>
```

Este probe es independiente de `TARGET`: Case C no rebasea contra la base, pero
sí necesita observar su tip exacto para decidir el merge.

- Imprime `0` → nada que absorber — skip to Phase 7.
- Imprime >0 → **merge, nunca rebase** (la rama ya está pusheada y el force push está
  denegado en el fleet):
  ```bash
  git merge --no-edit <BASE_SHA literal>
  ```
  Conflictos → Phase 6 (resolverlos acá es exactamente "ir resolviendo a medida
  que las otras ramas avanzan"; el squash final del PR se come el merge commit).
  Absorber la base es **opcional** si no hay solapamiento con lo mergeado — ante
  la duda, absorbela: mejor conflicto chico hoy que grande en el drenaje.

---

## Phase 6 — Conflict resolution (only if a rebase stops with conflicts)

1. Run `git status` to identify all conflicted files.
2. For each conflicted file:
   - Read the file and show the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
   - Explain what **our side** (the branch being rebased) contains vs what **their side** (the incoming commit) contains.
   - Resolve the conflict by editing the file to keep the correct code (remove markers).
3. Stage resolved files:
   ```bash
   git add <resolved-file>
   ```
4. Continue the rebase:
   ```bash
   git rebase --continue
   ```
5. Repeat until the rebase completes.

**If the conflict is too complex to auto-resolve:** stop, show the conflict in full, and ask the user how to proceed. Never guess on conflict resolution.

---

## Phase 7 — Confirmation

```bash
git log --oneline -8
git status
git stash list
```

Report:
- Current branch and the rebase target used (el `TARGET` + la razón de Phase 2c)
- PRs abiertos detectados (cantidad + lista breve)
- Stashes pre-existentes (cantidad + candidatos a drop)
- Commits pulled from the current branch's own remote (if any)
- Commits brought in from `TARGET` (if any)
- Number of conflicts resolved (if any)
- Whether the skill's own stash was restored (if Phase 1 stashed)
- Current working tree status

---

---

## Phase 8 — Fleet (`--all-vps`)

**Skip esta fase** si `ALL_VPS=0`. Corre **después** de que el/los repo(s)
local(es) quedaron sincronizados (Phases 1-7): así el fleet se alinea contra un
local ya sano.

Delega en el orquestador multi-host, que conecta por Tailscale y corre el core
no-interactivo en cada VPS remoto (+ la dev si está online):

El flag de repos es literal: `--repos=toolkit` sin `--all-repos`, `--repos=all` con
él. Un comando por llamada (dry-run primero):

```bash
bash ~/webapps/vps-ops-toolkit/scripts/maintenance/propagate-toolkit-commit.sh --check --repos=toolkit
```
```bash
bash ~/webapps/vps-ops-toolkit/scripts/maintenance/propagate-toolkit-commit.sh --apply --repos=toolkit
```

**Sentinel `exit 75` = pausa de auth de Tailscale**, NO es un fallo: el script
imprime el link de login. Mostráselo al operador tal cual, esperá a que autorice
(una sola autorización habilita todos los VPS) y **re-corré el mismo comando** —
es idempotente.

**Precondición**: para que el fleet reciba tus commits, el local debe estar
**pusheado**. Si `git status -sb` muestra `ahead`, avisá: los hosts remotos se
rebasan contra el remoto, no contra tu working copy.

Resultados por host: `SYNCED` · `CONFLICT_NEEDS_MANUAL_SYNC` (sólo toolkit,
working tree intacto) · `UNREACHABLE`. Por repo de proyecto: `REPO_CURRENT` ·
`REPO_DEPLOY_REQUIRED` · `REPO_SKIP` · `REPO_FAIL`; son siempre informativos.

---

## Safety rules

- **Never** run `git reset --hard` or `git push --force` without explicit user confirmation.
- **Never** resolve a conflict by blindly keeping one side — always inspect both sides.
- **Never** commit during this workflow — this skill only syncs, not commits.
- **Never** ejecutar `git stash drop` automáticamente. Solo sugerir en Next steps.
- If the parent branch cannot be detected, stop and ask the user.
- If in doubt about a conflict, stop and ask the user.
- **Política de PRs (protocolo por sesión):** N PRs de sesión abiertos son
  estado normal. Warnings sólo por: >1 candidato a release (base=default) o
  PRs de sesión fríos (>48h) sin drenar. Nunca bloquear el sync por conteo.
- **Nunca** rebasear una rama pusheada con PR sobre su base — la base se
  absorbe con `git merge <BASE_SHA literal>` (Case C).

---

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos
(reglas de gating de $output-protocol §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| --all-repos (este host) | rebasa LOCAL_PROJECTS + toolkit de ESTE host | `$git-sync --all-repos` |
| --all-vps (toolkit en el fleet) | core no-interactivo en cada VPS vía Tailscale; conflicto ⇒ abort + reporte | `$git-sync --all-vps` |
| Ambos ejes | toolkit + LOCAL_PROJECTS de cada host del fleet | `$git-sync --all-repos --all-vps` |
| Drop de stash OBSOLETO/VIEJO | SÓLO los que ESTE run clasificó así, uno por uno y con su evidencia | `git stash drop stash@{N}` |

Blocklist ($output-protocol §4): nunca ofrecer drops masivos de stashes ni
`git reset --hard` — el drop es per-stash, sólo con la clasificación
OBSOLETO/VIEJO de esta corrida como evidencia visible.

## Output final

Reportar siguiendo $output-protocol. Plantilla específica de `$git-sync`:

```markdown
🟢 git-sync OK — <repo> @ <SHA>
✨ Todo en orden — no hay acciones pendientes.

| Dimensión | Estado | Detalle |
|---|---|---|
| gh CLI + auth | ✅ | gh <version>, autenticado |
| Phase 0.5 — Stash inspection | ✅ | 0 stashes existentes |
| Phase 1 — Inspect | ✅ | working tree clean |
| Phase 2 — Parent + PR target | ✅ | <N> PRs abiertos → target=<TARGET literal> |
| Phase 3 — Sonda SHA | ✅ | tip exacto; refs/FETCH_HEAD/tags intactos |
| Phase 4 — Own remote sync | ⏭️ | current es parent (n/a) o sin upstream |
| Phase 5 — Rebase | ✅ | fast-forward o N commits rebased |
| Phase 6 — Conflictos | ⏭️ | sin conflictos |
| Phase 7 — Estado final | ✅ | branch up to date con TARGET |
```

Casos con acción pendiente (omitir línea ✨, agregar `## Next steps`):

- **Stashes obsoletos/viejos detectados** (⚠️ en Phase 0.5):
  ```markdown
  ## Next steps
  - `git stash drop stash@{0}` — OBSOLETO (apply --check falla)
  - `git stash drop stash@{1}` — VIEJO (>30 días, mensaje: <msg>)
  ```

- **>1 candidato a release** (⚠️ en Phase 2 PR target):
  ```markdown
  ## Next steps
  - (operador) release ambigua: PRs con base=<default>: #X, #Y. Re-basar los de
    sesión mal abiertos: `gh pr edit <n> --base <release>`.
  ```

- **PRs de sesión fríos (>48h)** (⚠️ en Phase 2 PR target):
  ```markdown
  ## Next steps
  - `$merge-queue` — drenar los PRs de sesión pendientes: #X (<rama>), #Y (<rama>).
  ```

- **Conflictos durante rebase** (❌ Phase 6):
  ```markdown
  ## Next steps
  - (manual, operador) Resolver conflictos en: <archivos>
  - `git add <archivos resueltos> && git rebase --continue`
  - O abortar: `git rebase --abort`
  ```

En modo `--all` (loop sobre repos), el reporte agrega columna `Repo` antes
de `Dimensión` y se considera tabla grande (>15 filas) — agregar
`### Resumen ejecutivo` con conteo y `### Top 3 acciones prioritarias`.
