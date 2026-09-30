---
name: "merge-when-green"
description: "Herramienta del OPERADOR (manual-only desde 2026-08-22): las sesiones de proyecto no la invocan — cierran con $pr-green (PR + CI verde, sin merge). Usar cuando trabajo ya commiteado (o listo para commitear) debe INTEGRARSE: 'mergealo cuando el CI esté verde', 'integrá esta rama', 'cerrá el PR cuando pase'. NO usar para crear commits sueltos ($git-commit), ni en cron/headless. Las ramas release se mergean sólo si projects.yml las autoriza (release_merge: <rama>); sin autorización se integran y se espera el CI, sin merge. En repos de proyecto (Path A): commit + PR + espera del CI + fix loop + merge. En vps-ops-toolkit (Path B): green gate local + push a master + propagación al fleet. --all-repos desde el toolkit (Path C): barrido en dos fases. Si la rama ya está contenida en la base, corta sin PR ni espera (short-circuit ya-en-base)."
---

> **⚠️ How to invoke** — **herramienta del OPERADOR** (`disable-model-invocation:
> true`): ninguna sesión la auto-invoca. Una sesión de proyecto cierra con
> $pr-green (PR abierto + CI verde) y PARA; el merge lo hace $merge-queue o el
> operador con esta skill.
> - Sin argumento: `$merge-when-green` → opera sobre el repo git del **cwd**
>   (resuelto con `git rev-parse --show-toplevel`). El comportamiento se bifurca
>   según el repo:
> - **Repo de proyecto** (con PR + CI) → **Path A**: el caso normal es **mergear el PR
>   de sesión que YA está abierto** — su sesión dueña lo dejó verde y frenó ahí. Las
>   Phases 1-4 (commit, ya-en-base, PR, espera del CI, fix loop) son el **espejo de
>   $pr-green**: la sesión dueña ya las corrió, así que acá suelen ser no-ops de
>   verificación. Lo que esta skill agrega es la **Phase 5 (merge)**. `gh` obligatorio.
> - **`vps-ops-toolkit`** (commit directo a `master`, sin PR — ver "Git en este
>   repo" en su CLAUDE.md) → **Path B (trunk flow)**: valida el verde localmente con
>   los mismos checks del CI (`scripts/ci/*` + `bash -n` + shellcheck si está), y si
>   pasan hace commit + push a `master`, propaga al fleet vía Tailscale, y confirma
>   el run de `validation-coverage` en master. `gh` es **opcional** acá.
>
> **Defaults de proyecto (Path A; override con flags):**
> - Merge con `--squash` + `--delete-branch`. (`--merge-method=merge|rebase`.)
> - Si la rama no tiene PR abierto, lo crea. (`--no-create-pr` para no crearlo.)
> - El fix loop **pausa pidiendo aprobación** si `fix-broken-tests` necesita
>   tocar código de producción. (`--autonomous` para no pausar.)
> - Un check **no-test** rojo (lint / quality-gate / design-tokens / flow-sync)
>   **frena y reporta**; no se intenta arreglar. (`--fix-nontest` para intentarlo.)
> - Máximo **5** iteraciones del fix loop. (`--max-iterations=N`.)
>
> **Defaults del toolkit (Path B; override con flags):**
> - Green gate local ON: si un validador que corre da error, **frena** sin pushear.
>   (`--no-verify` para saltarlo.)
> - Propaga el commit al fleet vía Tailscale. (`--no-propagate` para no propagar.)
> - Confirma el run de CI en master post-push si hay `gh`. (`--no-ci-watch` lo salta.)
> - Los flags de proyecto (`--merge-method`, `--no-create-pr`, `--autonomous`,
>   `--fix-nontest`, `--max-iterations`) son **no-ops** en el toolkit.
>
> **Guards de coordenada de trabajo (Path A y C, siempre ON):** antes de tocar
> nada se resuelve la coordenada del repo con `resolve-work-coordinate.sh`
> (misma fuente que usa $all-projects — projects.yml validado contra los PRs
> abiertos), y la decisión de merge sale de ahí, sin flags:
> - **Rama release** (la actual es head de un PR abierto) **autorizada en
>   projects.yml** (`release_merge: <rama>` nombra exactamente esta rama) → flujo
>   completo **incluido el merge**, sin preguntar. Tras el merge la skill elimina
>   el campo (autorización one-shot).
> - **Rama release SIN autorizar** (campo ausente) → se hace todo el flujo
>   (commit + push + espera del CI + fix loop) pero **NO se mergea**, y se informa
>   cómo autorizar el lanzamiento.
> - **Ambigüedad** (el campo nombra OTRA rama, o la coordenada no se pudo
>   resolver) → se **pregunta** (AskUserQuestion), nunca se asume.
> - **Host equivocado** (`host_status=wrong-host`) → **aborta sin tocar nada**. El
>   trabajo de ese proyecto vive en el clon de otro VPS; commitear en éste deja el
>   fleet inconsistente.
>
> **Short-circuit "el trabajo ya está en la base" (A, B y C, siempre ON):** tras
> commitear lo pendiente, si la rama ya está contenida en `main`/`master` —
> verificado por **contenido**, así que vale también para un **squash merge**, donde
> los commits de la rama no quedan como ancestros — se **verifica y se reporta dónde
> aterrizó** **sin tocar el clon principal**, y se termina: **no se crea PR, no se
> espera el CI, no se mergea**. El verde que habilitó
> ese merge ya es el veredicto. La rama local obsoleta se nombra, **no se borra**. No
> hay flag: el reporte entrega el comando para mirar el CI a mano si querés.
>
> **Modo multi-repo (`--all-repos`, sólo desde `vps-ops-toolkit`) → Path C:**
> recorre `LOCAL_PROJECTS` de este host + el toolkit en **dos fases** — primero
> integra todos (commit + push, sin esperas), después espera los CI y mergea. Los
> runs de GitHub corren en paralelo mientras sigue el barrido, así que el tiempo
> total es ≈ el del CI más lento, no la suma. Invocarlo desde un repo de proyecto
> es **error duro**. No existe eje `--all-vps`: no se mergea a ciegas en clones de
> otros VPS.

## Cómo invocar este skill

Gating ($output-protocol §4): (1) flags explícitos → ejecutar directo, sin
menú; (2) intención clara en la sesión ("mergealo cuando esté verde" tras un
commit reciente de esta conversación) → proponer el comando en una línea y
esperar confirmación; (3) invocación ambigua (no está claro qué rama/repo se
integra) → UNA sola AskUserQuestion; (4) nunca en cron/headless, ni dentro del
barrido Path C, ni cuando el flujo viene ya decidido desde $merge-queue o
$all-in-base (esos llamadores no re-preguntan: entran con defaults).

**Q1 — Método de merge** (`multiSelect: false`; sólo Path A y sólo si el
operador no lo indicó):

| label | description | preview |
|---|---|---|
| Squash (Recommended) | default del fleet: un commit limpio en la base y borra la rama | `$merge-when-green` |
| Merge commit | conserva los commits de la rama como ancestros en la base | `$merge-when-green --merge-method=merge` |
| Rebase | reescribe los commits de la rama sobre la base, sin merge commit | `$merge-when-green --merge-method=rebase` |

**Qué NO se pregunta:** `--autonomous` (quita la pausa de aprobación del fix
loop) y `--no-verify` (salta el green gate del toolkit) son overrides
deliberadamente incómodos y jamás se ofrecen. `--fix-nontest`,
`--max-iterations=N`, `--no-propagate`, `--no-ci-watch`: tuning simétrico al
default, se tipean. El merge de una release no se pregunta ni se tipea: lo
decide `release_merge:` en projects.yml (la única pregunta posible es la de
ambigüedad del guard, arriba).

## Phase 0 — Preflight + ruteo

```bash
ARGS_RAW="${ARGUMENTS:-}"
# Flags de proyecto (Path A: PR/CI):
MERGE_METHOD="squash"; CREATE_PR=1; AUTONOMOUS=0; FIX_NONTEST=0; MAX_ITER=5
# Flags del toolkit (Path B: trunk flow):
VERIFY=1; PROPAGATE=1; CI_WATCH=1
# Multi-repo (Path C):
ALL_REPOS=0
for tok in $ARGS_RAW; do
    case "$tok" in
        --merge-method=squash|--merge-method=merge|--merge-method=rebase) MERGE_METHOD="${tok#--merge-method=}" ;;
        --no-create-pr)     CREATE_PR=0 ;;
        --autonomous)       AUTONOMOUS=1 ;;
        --fix-nontest)      FIX_NONTEST=1 ;;
        --max-iterations=*) MAX_ITER="${tok#--max-iterations=}" ;;
        --no-verify)        VERIFY=0 ;;
        --no-propagate)     PROPAGATE=0 ;;
        --no-ci-watch)      CI_WATCH=0 ;;
        --all-repos)            ALL_REPOS=1 ;;
        --all|--all-vps)
            echo "❌ ERROR: '$tok' no existe en merge-when-green."
            echo "   ¿Todos los repos de ESTE host? → --all-repos (sólo desde vps-ops-toolkit)"
            echo "   No hay eje fleet: no se mergea a ciegas en clones de otros VPS."
            exit 2 ;;
        *) echo "❌ ERROR: argumento desconocido '$tok'."; exit 2 ;;
    esac
done
export ALL_REPOS

# Resolver el repo del cwd (NO asumir el toolkit; ignorar el hook SessionStart).
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "❌ ERROR: el cwd no es un repo git. Lanzá Claude Code desde el repo a integrar."
    exit 2
}
cd "$REPO_ROOT"
REPO_NAME="$(basename "$REPO_ROOT")"

# --all-repos es una acción de operador del fleet: el toolkit es su punto de
# entrada. Desde un repo de proyecto no se permite — barrer los repos vecinos
# desde adentro de uno de ellos es fácil de disparar sin querer.
if (( ALL_REPOS == 1 )) && [ "$REPO_NAME" != "vps-ops-toolkit" ]; then
    echo "❌ ERROR: --all-repos sólo se invoca desde vps-ops-toolkit."
    echo "   Estás en '$REPO_NAME'. Para integrar SÓLO este repo: $merge-when-green (sin flags)."
    exit 2
fi

# RUTEO: --all-repos → Path C. Toolkit sin flag → Path B. Cualquier otro → Path A.
if (( ALL_REPOS == 1 )); then
    echo "🎯 --all-repos desde el toolkit → Path C (multi-repo, dos fases)."
elif [ "$REPO_NAME" = "vps-ops-toolkit" ]; then
    echo "🎯 vps-ops-toolkit → Path B (trunk flow). verify=$VERIFY propagate=$PROPAGATE ci-watch=$CI_WATCH"
    echo "   (flags de proyecto ignorados: este repo no usa PR/merge)"
else
    # Path A: gh es obligatorio (PR detection + checks + merge).
    command -v gh >/dev/null || { echo "❌ ERROR: gh CLI no instalada — obligatoria."; exit 2; }
    gh auth status >/dev/null 2>&1 || { echo "❌ ERROR: gh sin auth — corré 'gh auth login'."; exit 2; }
    DEFAULT_BRANCH="$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo master)"
    CURRENT="$(git rev-parse --abbrev-ref HEAD)"
    echo "🎯 Repo: $REPO_NAME  |  rama: $CURRENT  |  base: $DEFAULT_BRANCH  |  merge: $MERGE_METHOD"
fi
```

**Ruteo:** con `--all-repos` ejecutá **sólo el Path C** (Phases C1–C2). Si no, y el
repo es `vps-ops-toolkit`, ejecutá **sólo el Path B** (Phases T1–T4) y saltá las
Phases 0.5–6. Para cualquier otro repo, ejecutá **Path A** (Phases 0.5–6) y saltá
los Paths B y C.

---

# Path A — repos de proyecto (PR + CI + merge)

**Dónde se para el operador (protocolo por sesión).** Lo normal es operar sobre un
**PR ya abierto por una sesión**: todo se hace vía `gh` (consultar, esperar el CI y
mergear no requieren checkout de nada), así que el cwd puede ser el clon principal
sin tocarlo. Casos que no son ése:

- **Estás en el clon principal, sobre `main`/`master` o la release, con cambios
  sueltos** → **acá no se crea rama ni se commitea** (el hook `PreToolUse` lo deniega,
  y es el checkout del servicio corriendo): creá un worktree con
  `bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh" create <prefijo> <slug>`,
  entrá (Claude: `EnterWorktree path=…` · Codex: `cd …`) y **re-invocá desde ahí**.
- **El fix loop (Phase 4) necesita un tree** donde escribir: el **worktree de la sesión
  dueña** del PR, o se **delega el fix a esa sesión** (el mecanismo de $merge-queue
  § «Delegación a la sesión dueña»). Nunca el clon principal.
- **No se mergea `main`/`master` sobre sí mismo.**

## Phase 0.5 — Coordenada de trabajo (guards)

Antes de tocar el working tree, resolvé dónde y sobre qué rama corresponde
trabajar. La fuente es `resolve-work-coordinate.sh` — la misma que usa
$all-projects — que valida la rama contra los **PRs abiertos**, no contra el
`projects.yml` estático.

```bash
COORD="$(bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh" \
         --check "$REPO_NAME" 2>/dev/null)"
PR_STATE="$(sed -n 's/^pr_state=//p'   <<<"$COORD")"
HOST_ST="$(sed -n 's/^host_status=//p' <<<"$COORD")"
VPS_WORK="$(sed -n 's/^vps_work=//p'   <<<"$COORD")"
OPEN_PR="$(sed -n 's/^open_pr=//p'     <<<"$COORD")"
RELEASE_AUTH="$(sed -n 's/^release_merge=//p' <<<"$COORD")"
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
MERGE_ALLOWED=1

# Guard 1 — host equivocado. El trabajo de este proyecto vive en el clon de otro
# VPS; commitear acá deja el fleet inconsistente (los scripts que filtran por
# server: empiezan a saltarlo, y el commit aterriza en la rama equivocada).
if [ "$HOST_ST" = "wrong-host" ]; then
    echo "⏭️  $REPO_NAME trabaja en $VPS_WORK, no en este host — abortando sin tocar nada."
    echo "    Continuá allá:  tailscale ssh ryzepeck@$VPS_WORK"
    exit 0
fi

# Guard 2 — rama release. La condición NO es "hay un solo PR abierto" sino "la
# rama que estás pisando es el head de un PR release". Con pr_state=ambiguous
# (dos PRs release abiertos, caso real de vastago: release-may-2026-v2 +
# release-may-2026) seguís parado sobre una release igual, y un guard que sólo
# mirara `single` la mergearía.
IS_RELEASE_BRANCH=0
if [ -n "$OPEN_PR" ] && [ "$OPEN_PR" != "none" ]; then
    while IFS= read -r head; do
        [ "$head" = "$CURRENT" ] && IS_RELEASE_BRANCH=1
    done < <(tr ',' '\n' <<<"$OPEN_PR")
fi

# La decisión de merge sale de projects.yml — release_merge= (autorización
# one-shot de lanzamiento que nombra la rama release exacta), emitida por el
# resolver. Sin flags: la fuente de verdad se consulta en cada invocación.
if (( IS_RELEASE_BRANCH == 1 )); then
    if [ "$RELEASE_AUTH" = "$CURRENT" ]; then
        echo "✅ '$CURRENT' es rama release AUTORIZADA (release_merge en projects.yml)."
        echo "    Flujo completo incluido el merge; tras mergear se limpia el campo."
    elif [ -n "$RELEASE_AUTH" ]; then
        echo "❓ '$CURRENT' es rama release, pero release_merge autoriza otra: '$RELEASE_AUTH'."
        echo "    Ambigüedad → se pregunta (abajo), no se asume."
    else
        MERGE_ALLOWED=0
        echo "⏸️  '$CURRENT' es rama release (head de PR abierto; pr_state=$PR_STATE), sin autorización."
        echo "    Se integrará y se esperará el CI, pero NO se mergea."
        echo "    Para lanzarla: setear 'release_merge: $CURRENT' en projects.yml y re-invocar."
    fi
fi

# Autorización stale: release_merge nombra una rama que no es head de ningún
# PR abierto (la release ya se mergeó/cerró). No bloquea, pero se reporta y se
# ofrece limpiarla en Next steps.
if [ -n "$RELEASE_AUTH" ] && (( IS_RELEASE_BRANCH == 0 )); then
    case ",$OPEN_PR," in
        *",$RELEASE_AUTH,"*) : ;;   # respalda otra rama release abierta — válida
        *) echo "ℹ️  release_merge='$RELEASE_AUTH' no corresponde a ningún PR abierto (stale)." ;;
    esac
fi

# Sin coordenada resoluble (repo fuera de projects.yml, gh caído) no se puede
# afirmar que NO es una release → también es ambigüedad: se pregunta.
case "$PR_STATE" in
    ""|gh-error|gh-unavailable|no-repo)
        echo "❓ coordenada no resoluble (pr_state='${PR_STATE:-vacío}') — el guard de"
        echo "    release no pudo evaluarse. Se pregunta antes de seguir." ;;
esac
```

**Ambigüedad → AskUserQuestion, nunca asumir** (los dos casos `❓` de arriba):

- **`release_merge` nombra OTRA rama** — preguntar: «projects.yml autoriza
  `$RELEASE_AUTH` pero estás sobre `$CURRENT`». Opciones: **Mantener hold
  (Recommended)** — integrar sin merge, `MERGE_ALLOWED=0`; **Mergear `$CURRENT`
  igual** — tratarla como autorizada (al mergear se limpia el campo, que quedó
  stale); **Abortar** — salir sin tocar nada.
- **Coordenada no resoluble** — preguntar según la causa visible. Opciones:
  **Continuar sin merge** — integra y espera el CI, `MERGE_ALLOWED=0` (elegila
  si `gh` falló y podrías estar sobre una release); **Continuar como rama
  normal** — flujo completo con merge (esperable si el repo no pertenece al
  fleet / no está en projects.yml); **Abortar**.

Reportá `PR_STATE`, `HOST_ST`, `RELEASE_AUTH` y el valor final de
`MERGE_ALLOWED` en la tabla de salida: el operador tiene que ver por qué se
mergeó o por qué no.

**Base de integración de la rama (stacked).** Bajo el protocolo por sesión la
base de un PR **no siempre es la default**: en un repo que participa del flujo
release (resolver: `pr_state=single`), una rama de sesión integra contra la
**release** (`resolved_branch`), y sólo la release misma integra contra la
default. Mergear un PR de sesión a la release **no** requiere `release_merge`
(esa autorización gobierna únicamente release→default). Las Phases 1.5 y 2
derivan `BASE_INT` con esta regla (cada bloque re-deriva lo suyo — las
variables no sobreviven entre bloques).

## Phase 1 — Commit + push

Reutilizá el flujo de `$git-commit` sobre la rama de trabajo:

- `git status --porcelain` vacío → no hay nada que commitear; seguí a Phase 1.5
  (la rama ya debe estar pusheada). **No** saltes directo a Phase 2: con el tree
  limpio el caso más probable es que el trabajo ya esté en la base.
- Con cambios → inspeccioná `git status` + `git diff`, generá un mensaje
  `FEAT/FIX/DOCS` propio, `git add` selectivo + `git commit -m "…"` + `git push`
  (con `-u origin <rama>` si no hay upstream). Mostrá cada comando antes de correrlo.
- Si el push falla → reportá y **abortá** (sin PR pusheado no hay CI que esperar).

## Phase 1.5 — ¿El trabajo ya está en la base?

**El hueco que cerraba (histórico, pre-2026-08-17):** varias sesiones abiertas sobre
el MISMO repo compartían working tree y rama; la primera que mergeaba se llevaba
puesto el trabajo de las demás, y las que seguían encontraban su trabajo ya en la
base.

Hoy cada sesión tiene su worktree, su rama y su PR, así que ese choque no existe. El
caso vigente es otro: **una rama cuyo contenido ya aterrizó** (squash de
$merge-queue o del operador). Esperar el CI ahí es tiempo muerto — ese contenido
ya pasó los checks que gatearon aquel merge — y si la rama nunca tuvo PR propio,
Phase 2 abriría un **PR nuevo y vacío**. Este gate corta las dos cosas.

Corre acá y no antes porque Phase 1 ya commiteó y pusheó lo pendiente — evaluar
antes leería trabajo sin commitear como "no hay nada nuevo". Y corre acá y no
después porque Phase 2 es la que crea el PR.

```bash
# Las variables NO sobreviven entre bloques bash de una skill (sólo el cwd):
# re-derivar todo acá, igual que Phase 0.5 y Phase 2.
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
DEFAULT_BRANCH="$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo master)"
# BASE_INT — base de integración de ESTA rama (stacked):
#   1) la rama ya tiene PR abierto → la base ES la del PR;
#   2) sin PR: repo participante con release viva (pr_state=single) y no estamos
#      parados EN la release → la release; 3) si no → la default.
# El nombre del proyecto sale del git-common-dir (en un worktree el toplevel es
# ~/webapps/.wt/<repo>/<slug>, no el repo).
BASE_INT="$DEFAULT_BRANCH"
PR_BASE="$(gh pr view "$CURRENT" --json baseRefName,state -q 'select(.state=="OPEN") | .baseRefName' 2>/dev/null || true)"
if [ -n "$PR_BASE" ]; then
    BASE_INT="$PR_BASE"
else
    PROJ="$(basename "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")")"
    RESOLVER="$HOME/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh"
    if [ -x "$RESOLVER" ]; then
        RB="$(bash "$RESOLVER" --check "$PROJ" 2>/dev/null | awk -F= '$1=="pr_state"{ps=$2} $1=="resolved_branch"{rb=$2} END{if(ps=="single") print rb}')"
        [ -n "$RB" ] && [ "$RB" != "$CURRENT" ] && BASE_INT="$RB"
    fi
fi
BASE_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin "refs/heads/$BASE_INT" 2>/dev/null || true)"
BASE_SHA="${BASE_LINE%%[[:space:]]*}"
if echo "$BASE_SHA" | grep -Eq '^[0-9a-fA-F]{40,64}$'; then
    git cat-file -e "${BASE_SHA}^{commit}" 2>/dev/null \
      || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$BASE_SHA"
else
    BASE_SHA=""
fi
LANDED=0; LANDED_HOW=""

# Precondición: sólo se evalúa con el tree limpio. Con cambios sin commitear hay
# trabajo nuevo por definición — nunca cortocircuitar. Es el vector de falso
# positivo más probable acá: el `git add` de Phase 1 es SELECTIVO, así que la
# sesión de al lado pudo dejar archivos sin trackear.
if [ "$CURRENT" = "HEAD" ] || [ -z "$BASE_SHA" ] || ! git rev-parse --verify --quiet "$BASE_SHA" >/dev/null; then
    # detached HEAD o sin base remota: no se puede afirmar NADA. Flujo normal.
    echo "⚠️  no evaluable (detached HEAD o tip remoto ausente) — sigue el flujo normal."
elif [ -n "$(git status --porcelain)" ]; then
    echo "ℹ️  working tree con cambios — hay trabajo nuevo; sigue el flujo normal."
elif [ "$CURRENT" = "$BASE_INT" ]; then
    # La sesión quedó parada sobre su base de integración (la rama anterior la
    # borró --delete-branch + el cierre de la sesión que mergeó). Nada que integrar.
    LANDED=1; LANDED_HOW="la sesión ya está sobre $BASE_INT"
else
    # Capa 1 — fast path. Cubre --merge, --rebase y la rama ya integrada tal cual.
    AHEAD="$(git rev-list --count "$BASE_SHA..HEAD" 2>/dev/null || echo -1)"
    if [ "$AHEAD" = "0" ]; then
        LANDED=1; LANDED_HOW="0 commits por delante de $BASE_SHA"
    else
        # Capa 2 — squash path. El default del fleet es --squash: la rama mergeada
        # NO queda como ancestro y sus commits cambian de patch-id, así que
        # is-ancestor/rev-list/cherry son todos ciegos acá. merge-tree hace el merge
        # de 3 vías en memoria: si el árbol resultante ES el de la base, mergear
        # sería un no-op ⇒ todo el trabajo de la rama ya está ahí.
        # rc=0 limpio · rc=1 conflicto (⇒ NO landed) · rc>1 error//git<2.38.
        # OJO: sin pipe en la asignación — con `| head -1` el $? sería el de head
        # (siempre 0) y se perdería el rc de git, que es justo lo que distingue
        # "merge limpio" de "conflicto".
        MT_OUT="$(git merge-tree --write-tree "$BASE_SHA" HEAD 2>/dev/null)"; MT_RC=$?
        MT="$(printf '%s\n' "$MT_OUT" | head -1)"
        BASE_TREE="$(git rev-parse "$BASE_SHA^{tree}" 2>/dev/null || echo none)"
        if [ "$MT_RC" -eq 0 ] && [ -n "$MT" ] && [ "$MT" = "$BASE_TREE" ]; then
            LANDED=1; LANDED_HOW="mergear a $BASE_INT sería un no-op (mismo árbol)"
        elif [ "$MT_RC" -gt 1 ]; then
            # git < 2.38 no tiene --write-tree. Sin capa 2 no se puede afirmar nada
            # sobre un squash ⇒ seguir el flujo normal (conservador, nunca al revés).
            echo "ℹ️  git sin 'merge-tree --write-tree' — detección de squash no disponible."
        fi
        # Señal informativa: parte del trabajo ya está y parte no.
        EQ="$(git cherry "$BASE_SHA" HEAD 2>/dev/null | grep -c '^-' || true)"
        if [ "$LANDED" -eq 0 ] && [ "${EQ:-0}" -gt 0 ]; then
            echo "⚠️  parcial: $EQ de $AHEAD commit(s) ya están en $BASE_INT, el resto no."
            echo "    NO se cortocircuita — sigue el flujo normal para integrar lo que falta."
        fi
    fi
fi

if [ "$LANDED" -eq 1 ]; then
    echo "✅ El trabajo de esta sesión YA está en $BASE_INT ($LANDED_HOW)."
    echo "   base_sha=$BASE_SHA"
else
    echo "→ Hay trabajo por integrar; sigue a Phase 2."
fi
```

**Sesgo del gate (a propósito, hacia el falso negativo):** un tree sucio, un
`detached HEAD`, la falta del SHA remoto de `<base>`, un conflicto del merge de 3 vías o
un git < 2.38 hacen que NO se cortocircuite y siga el flujo normal. Un falso
positivo dejaría el trabajo del operador sin mergear para siempre; un falso
negativo sólo cuesta una espera de CI (el comportamiento de antes). No hay flag
para desactivarlo. La rama local obsoleta se **nombra pero no se borra**: tras un
squash, `git branch -d` la rechaza; el `-D` lo decide el operador.

**Si `LANDED=1`:** el trabajo está completo y en la base. Ya pasó el CI que gateó
aquel merge, así que **saltá Phases 2-5** — ni PR, ni `--watch`, ni merge.

1. **Evidencia** (el operador quiere saber *dónde* aterrizó su trabajo, no sólo
   que aterrizó). Buscá el PR que lo llevó y, si no hay, el commit de la base.
   El bloque anterior imprime `base_sha=` para que el siguiente comando use ese
   SHA literal (las variables no persisten entre bloques):
   ```bash
   CURRENT="$(git rev-parse --abbrev-ref HEAD)"
   gh pr list --state merged --head "$CURRENT" --limit 1 \
     --json number,url,mergedAt,mergeCommit 2>/dev/null
   git log <sha-base-impreso> --oneline -1
   ```
2. **Cierre** (equivalente a Phase 6). Depende de DÓNDE está corriendo la sesión:
   - **En un worktree de sesión** (`git rev-parse --show-toplevel` cae bajo
     `.wt/`): no se hace checkout ni fetch de refs; `base_sha` ya fue
     sondeado de forma neutra. El retiro lo hace $all-in-base al cierre.
   - **En el clon principal** (transicional/legacy): también queda intacto. Si
     su HEAD difiere del tip de `deploy_branch=`, reportá `deploy pendiente` y
     derivá al operador a `scripts/deployment/deploy-project.sh --apply`; esta
     skill de merge nunca despliega ni usa el escape del guard.
   La rama local obsoleta se **reporta, NO se borra** — borrarla es decisión del
   operador.
3. Reportá con el veredicto `⏭️` (ver "Output final").

**Rama release ya integrada:** si Phase 0.5 marcó `MERGE_ALLOWED=0` **y** acá da
`LANDED=1`, también cortocircuita — el CI ya se pronunció sobre ese contenido y no
hay nada que integrar. Se reporta igual, aclarando que sigue siendo release.

## Phase 2 — Asegurar el PR

```bash
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
PR_JSON="$(gh pr view "$CURRENT" --json number,url,state,baseRefName 2>/dev/null || echo '')"
```

- Si existe un PR **abierto** para `CURRENT` → usalo (`number`, `url`) y tomá su
  `baseRefName` como la base (no la recalcules).
- Si `state` es **`MERGED`** o `CLOSED` → **no** cuenta como PR abierto. `gh pr view`
  devuelve el PR más reciente de la rama aunque esté cerrado, así que hay que mirar
  `state` (por eso se pide en el `--json`) y no sólo si vino algo. Llegar acá con un
  `MERGED` significa que Phase 1.5 ya verificó que **hay trabajo nuevo** sobre una
  rama reusada después de su merge → crear un PR nuevo es lo correcto.
- Si no existe y `CREATE_PR=1` → crear con la base de integración (`BASE_INT`,
  misma receta de Phase 1.5: la release en repos participantes, la default si no)
  y con el **ownership del protocolo por sesión** en el body:
  ```bash
  gh pr create --base "$BASE_INT" --fill \
    --body "$(printf 'Sesión: %s\nIntención: %s\n\n%s' "<nombre de la sesión, o el slug de la rama si no lo sabés>" "<1 línea: qué entrega esta rama>" "<resumen de los commits>")"
  ```
  Capturá la URL. Las dos líneas `Sesión:` / `Intención:` son el contrato que
  $merge-queue usa para delegar conflictos a la sesión dueña — no las omitas.
- Si no existe y `CREATE_PR=0` → **frená** y reportá: "rama sin PR abierto; pasá sin
  `--no-create-pr` o abrí el PR a mano".

Reportá la URL del PR (`PR URL: <url>`).

## Phase 3 — Esperar el CI

```bash
# Bloquea hasta que todos los checks resuelvan; no aborta al primer fallo.
# Llamada foreground: pasarle timeout: 600000 al tool Bash (su default es 120000).
gh pr checks "$PR_NUMBER" --watch --fail-fast=false; RC=$?
# Estado por check (nombre + conclusión) para clasificar:
gh pr checks "$PR_NUMBER" --json name,state,bucket 2>/dev/null \
  || gh pr view "$PR_NUMBER" --json statusCheckRollup \
       -q '.statusCheckRollup[] | "\(.name)\t\(.conclusion // .state)"'
```

- `RC == 0` (todos los checks en verde/`bucket=pass`) → **Phase 5 (merge)**.
- Algún check en `fail` → **Phase 4 (fix loop)**.
- El `--watch` foreground muere al tope de la tool Bash (600000 ms; exit 143 —
  les pasa a suites E2E largas). Si expira: **NO re-bloquees con otro `--watch`**.
  Montá el watcher variante PR-checks del «Cierre asíncrono de CI» (abajo) con
  `NEXT:` verde = "retomar Phase 5 (merge) del PR #<n>" / rojo = "Phase 4 (fix
  loop)", reportá `⏸️ CI en vuelo — CI-MONITOR [<repo>#<n>] montado` y cortá el
  turno: el flujo se retoma al llegar la notificación (regla de reanudación de
  esa sección, re-verificando el estado en vivo).
- Si el PR **no tiene checks** (repo sin CI en esa rama) → avisá "sin checks; no
  hay verde que esperar" y frená (no mergees a ciegas salvo que el operador lo pida).

## Phase 4 — Fix loop (máx `MAX_ITER` iteraciones)

Por cada check en `fail`, clasificalo:

- **Test jobs**: `backend-tests` (pytest), `frontend-unit-tests` (jest),
  `frontend-e2e-tests` (playwright, sharded).
- **Gates no-test**: `test-quality-gate`, `design-tokens-guard`,
  `e2e-flow-definitions-sync`, `shellcheck`, `yaml-validation`, `config-integrity`,
  y los agregadores `coverage-summary` / `e2e-merge-reports`.

**Si falla un gate no-test:**
- Con `FIX_NONTEST=0` (default) → **frená y reportá** el gate + su log
  (`gh run view <run-id> --log-failed`). No lo intentes arreglar. `## Next steps`
  con el comando local equivalente (ej. `npm run check:design-tokens:strict`).
- Con `FIX_NONTEST=1` → intentá el arreglo directo (ej. reemplazar el color-literal,
  regenerar `flow-definitions.json` con `npm run ci:e2e-flow-summary`), commiteá y
  volvé a Phase 3.

**Si fallan test jobs:**
1. Traé los logs del run fallido: `gh run view <run-id> --log-failed` (el `<run-id>`
   sale del `link` del check o de `gh run list --branch "$CURRENT" --limit 1`).
2. **Extraé los IDs concretos** de los tests fallidos de esos logs:
   - pytest → líneas `FAILED path/test_x.py::TestClase::test_y`
   - jest → nombre del `describe > it` y el archivo `.spec/.test`
   - playwright → el spec `e2e/xxx.spec.ts` + título del test
3. Invocá la skill **`$fix-broken-tests`** pasándole ESA lista (ella corre sólo esos
   tests + regresión del módulo, nunca la suite completa). Respeta sus estándares
   (`docs/TESTING_QUALITY_STANDARDS.md`).
4. **Aprobación de código de prod**: si `fix-broken-tests` reporta que tuvo que tocar
   **código de producción** (fila ⚠️ en su output), y `AUTONOMOUS=0` (default),
   **PAUSÁ**: mostrá el cambio propuesto y pedí aprobación del operador antes de
   commitear. Con `AUTONOMOUS=1`, seguí sin pausar.
5. Commiteá el arreglo (`git commit -m "fix: <test> …"`) + `git push`. Volvé a
   **Phase 3** (el CI re-corre la suite completa y confirma el verde).
6. Contá la iteración. Si superás `MAX_ITER` sin llegar a verde → frená y reportá el
   estado (qué sigue rojo, hipótesis, comando exacto para el próximo intento).

## Phase 5 — Merge

**Phase 5 es del operador.** Si llegaste acá por delegación desde una SESIÓN
($all-in-base, $pr-green), **PARÁ**: para las sesiones esta fase no existe — su
entrega termina en el PR verde y el merge lo hace $merge-queue o el operador.

**Guard de release primero** (Phase 0.5). Si la rama es release sin
autorización en projects.yml, acá termina el flujo: el trabajo ya está
integrado y el CI ya dio su veredicto, que es lo que se venía a saber.

```bash
if [ "${MERGE_ALLOWED:-1}" = "0" ]; then
    echo "⏸️  Rama release ($CURRENT, PR #$PR_NUMBER) — commit y CI hechos, merge NO."
    echo "    Para lanzarla: setear 'release_merge: $CURRENT' al proyecto en"
    echo "    projects.yml (vps-ops-toolkit) y re-invocar $merge-when-green."
    # Saltar Phase 6. El PR queda abierto a propósito.
fi
```

Antes de terminar con `MERGE_ALLOWED=0`, aplicá el «Cierre asíncrono de CI»
(caso release-hold): normalmente NO se monta nada — Phase 3 ya vio el veredicto
del PR; sólo queda watcher si su `--watch` expiró.

Con `MERGE_ALLOWED=1`, seguí normalmente:

```bash
# Confirmar que el PR es realmente mergeable antes de mergear (nunca forzar).
gh pr view "$PR_NUMBER" --json mergeStateStatus,reviewDecision,mergeable \
  -q '"mergeable=\(.mergeable) state=\(.mergeStateStatus) review=\(.reviewDecision)"'
```

- Si `mergeable != MERGEABLE` o `mergeStateStatus` es `BLOCKED` (review/ruleset
  requerido, o checks no verdes) → **frená y reportá**; no fuerces el merge.
- Si está limpio → mergeá:
  ```bash
  gh pr merge "$PR_NUMBER" --"$MERGE_METHOD" --delete-branch
  ```

**Post-merge de una release autorizada (consumir la autorización):** si el
merge fue habilitado por `release_merge:` (o el operador eligió mergear en la
pregunta de ambigüedad), la autorización es one-shot — limpiála de
`projects.yml` acotando el borrado al bloque del proyecto:

```bash
OPS="$HOME/webapps/vps-ops-toolkit"
awk -v proj="$REPO_NAME" '
  /^[[:space:]]*- name:/ { in_p = ($NF == proj) }
  !(in_p && $1 == "release_merge:")
' "$OPS/projects.yml" > "$OPS/projects.yml.tmp" && mv "$OPS/projects.yml.tmp" "$OPS/projects.yml"
grep -n 'release_merge:' "$OPS/projects.yml" || echo "✓ autorización consumida"
```

Reportá el cambio del toolkit pendiente de commit (directo a `master` vía
`$git-commit`), y sugerí `resolve-work-coordinate.sh --apply <proyecto>` para
refrescar `branch_working`/`branch:` ahora que la release aterrizó.

## Phase 6 — Post-merge

**No corras esta fase si `MERGE_ALLOWED=0`** — no hubo merge y la rama release
sigue siendo la rama de trabajo del proyecto.

El cierre **nunca flipea el checkout del clon principal** (en VPS es el tree del
servicio corriendo):

- **En un worktree de sesión** (`git rev-parse --show-toplevel` bajo `.wt/`):
  no se mueve ninguna ref del gitdir compartido. El worktree de la
  **sesión dueña** lo retira ella misma con `$all-in-base` cuando ve su PR ya
  mergeado (`session-worktree.sh remove <slug>`, sin `--force`); los huérfanos los
  junta el **gc del operador**
  (`bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh" gc --apply`).
  Esta skill no retira worktrees ajenos.
- **En el clon principal** (operador): dejar checkout y HEAD intactos. Consultar
  `refs/heads/<deploy_branch>` con `ls-remote`, traer sólo el SHA si falta con el
  fetch object-only de Phase 1.5 y reportar la distancia. Si hay avance, el
  próximo paso es el deploy manual tipado (`deploy-project.sh --apply`), nunca un
  `checkout`/`pull` desde esta skill.

Reportá el PR mergeado + el SHA del merge en la base del PR.

Cerrá con el «Cierre asíncrono de CI» (caso Path A mergeado): **sweep** de
watchers propios obsoletos primero; después, si el squash disparó un run en
la base que sigue en vuelo (`gh pr view <n> --json mergeCommit` da el
SHA), UN watcher sobre `<base>@<merge-sha>`.

---

# Path B — vps-ops-toolkit (trunk flow, sin PR)

Este repo commitea **directo a `master`, sin rama feature ni PR** (política del
CLAUDE.md). El análogo de "merge when green" acá es: **validar el verde localmente
ANTES de integrar → commit + push a master → propagar al fleet → confirmar el run de
CI en master**. El "verde" son los mismos checks que corre
`.github/workflows/validation-coverage.yml`.

## Phase T1 — Green gate local (pre-push)

Con `VERIFY=1` (default), correr los validadores del CI contra el working tree.
Reportar SIEMPRE qué gate corrió y cuál se saltó (sin caps silenciosos). Este es un
bloque autocontenido: recomputa todo desde el cwd e imprime `GATE:GREEN` o `GATE:RED`.

```bash
cd "$(git rev-parse --show-toplevel)"
if [ "${VERIFY:-1}" = "0" ]; then
    echo "⏭️  green gate saltado (--no-verify) — se integra sin validar localmente."
else
    fails=0
    # (a) Sintaxis: bash -n sobre cada .sh cambiado/untracked.
    mapfile -t CHANGED_SH < <(git status --porcelain | sed 's/^...//' | grep -E '\.sh$' || true)
    if [ "${#CHANGED_SH[@]}" -gt 0 ]; then
        for f in "${CHANGED_SH[@]}"; do
            [ -f "$f" ] || continue
            if bash -n "$f"; then echo "  ✅ bash -n  $f"; else echo "  ❌ bash -n  $f"; fails=$((fails+1)); fi
        done
    else
        echo "  ⏭️  bash -n — sin scripts .sh cambiados"
    fi
    # (b) shellcheck si está instalado (mismo umbral de fallo que el CI: error-level).
    if command -v shellcheck >/dev/null; then
        if [ "${#CHANGED_SH[@]}" -gt 0 ]; then
            if printf '%s\n' "${CHANGED_SH[@]}" | xargs -r shellcheck --severity=error \
                 --exclude=SC1090,SC1091,SC2154; then echo "  ✅ shellcheck (error-level)"
            else echo "  ❌ shellcheck (error-level)"; fails=$((fails+1)); fi
        fi
    else
        echo "  ⏭️  shellcheck — no instalado en este host (lo confirma T4 vía CI de master)"
    fi
    # (c) validadores del CI: correr el .sh (escribe ci-results/*.json) y leer 'errors'.
    for pair in "validate-projects-yml:yaml-validation-summary.json" \
                "validate-config-integrity:config-integrity-summary.json"; do
        v="${pair%%:*}"; j="ci-results/${pair##*:}"
        bash "scripts/ci/$v.sh" >/dev/null 2>&1 || true
        errs="$(python3 -c "import json;print(json.load(open('$j'))['errors'])" 2>/dev/null || echo '?')"
        if [ "$errs" = "0" ]; then echo "  ✅ scripts/ci/$v.sh (0 errores)"
        else echo "  ❌ scripts/ci/$v.sh ($errs errores)"; fails=$((fails+1)); fi
    done
    [ "$fails" -gt 0 ] && echo "GATE:RED ($fails gate(s) en rojo)" || echo "GATE:GREEN"
fi
```

- `GATE:RED` → 🔴 **STOP**: NO commitees ni pushees. Reportá los gates rojos + el
  comando local para reproducirlos (`bash scripts/ci/<x>.sh`). **Distinguí el origen**:
  si el rojo lo introdujo TU cambio → arreglalo y reinvocá. Si es un rojo
  **pre-existente / no relacionado** (el repo ya estaba rojo antes de tocar nada) →
  surfacealo como item aparte y, si querés integrar igual, usá `--no-verify` (o
  `$git-commit`); no arrastres el arreglo del drift ajeno a este commit.
- `GATE:GREEN` (o `--no-verify`) → seguí a T2.

## Phase T2 — Commit + push a master

Sólo con `GATE:GREEN` (o `--no-verify`). Reutilizá el flujo de `$git-commit` sobre
`master` (sin rama feature ni PR).

Primero, el equivalente trunk-flow de Phase 1.5 — si `master` ya tiene todo, no hay
commit, ni propagación, ni run de CI **de esta corrida** que mirar:

```bash
MASTER_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin refs/heads/master 2>/dev/null || true)"
MASTER_SHA="${MASTER_LINE%%[[:space:]]*}"
if echo "$MASTER_SHA" | grep -Eq '^[0-9a-fA-F]{40,64}$'; then
    git cat-file -e "${MASTER_SHA}^{commit}" 2>/dev/null \
      || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$MASTER_SHA"
fi
if [ -n "$MASTER_SHA" ] && [ -z "$(git status --porcelain)" ] && git merge-base --is-ancestor HEAD "$MASTER_SHA"; then
    # Estaba atrás (otro host ya pusheó): dejar el clon al día igual.
    [ "$(git rev-parse HEAD)" = "$MASTER_SHA" ] || git merge --ff-only "$MASTER_SHA"
    echo "✅ nada que integrar: master ya contiene todo ($(git rev-parse --short HEAD))."
    echo "   No se commitea, no se propaga (T3) y no se vigila el CI (T4)."
    exit 0
fi
```

- Cortó el bloque de arriba → **terminá acá**, sin T3 ni T4, y andá al Output final.
  Para confirmar que el fleet quedó al día:
  `bash scripts/maintenance/propagate-toolkit-commit.sh --check`.
- `git status --porcelain` vacío pero con commits sin pushear (`git log @{u}..HEAD`)
  → pusheá y seguí a T3.
- Con cambios → inspeccioná `git status` + `git diff`, generá un mensaje
  `FEAT/FIX/DOCS` propio, `git add` **selectivo** (sólo lo de este cambio) +
  `git commit -m "…"` + `git push`. Mostrá cada comando antes de correrlo. El hook
  `pre-commit` corre igual (guard de credenciales).
- Si `git push` falla → reportá y **saltá la propagación** (T3): el commit local
  queda; no hay nada nuevo en el remoto que jalar.

Capturá el SHA pusheado: `git rev-parse HEAD`.

## Phase T3 — Propagación al fleet (ON por defecto)

Con `PROPAGATE=1` (default) y sólo si T2 hizo un commit real **y** el push tuvo
éxito: sincronizá la copia del toolkit en los otros hosts del fleet (otros VPS + dev
si está prendida) con el commit recién pusheado, corriendo el core de `git-sync` en
cada host remoto vía Tailscale.

```bash
if [ "$(basename "$(git rev-parse --show-toplevel)")" != "vps-ops-toolkit" ]; then
    echo "⏭️  Repo no-toolkit — sin propagación."
else
    bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/propagate-toolkit-commit.sh" --apply
fi
```

- **Exit code `75`** (Tailscale pide autorización interactiva): el script imprimió un
  link `https://login.tailscale.com/...`. **Mostrale el link tal cual al operador**,
  pedile que lo abra y autorice con la cuenta del fleet, esperá su confirmación, y
  **re-ejecutá el mismo comando** (idempotente). Repetí hasta que el exit deje de ser
  `75`. Una autorización habilita TODOS los VPS de la ventana de re-auth. NO caigas a
  `ssh` directo, NO abortes, NO asumas que un VPS está caído (ver CLAUDE.md "Flujo de
  auth de Tailscale SSH").
- Reportá por host: `SYNCED <sha>` (actualizado) / `CONFLICT_NEEDS_MANUAL_SYNC`
  (divergencia real; quedó con el working tree intacto → requiere `git-sync` manual;
  no bloquea el commit ya hecho) / `UNREACHABLE` (dev apagada / VPS caído; warning,
  seguí).

Con `--no-propagate` (`PROPAGATE=0`) → omitir esta fase y decirlo en el resumen.

## Phase T4 — Confirmar CI en master (post-push, best-effort)

Con `CI_WATCH=1` (default), `gh` disponible + autenticado, y un push exitoso en T2:
confirmá que `validation-coverage` quedó en verde para el SHA pusheado.

**Si T2 cortó por "master ya contiene todo", esta fase NO corre.** El `git rev-parse
HEAD` de abajo resolvería a un commit **ya pusheado hace rato**, y `gh run watch`
quedaría mirando el run viejo de ese SHA como si fuera de esta corrida — un no-op se
reportaría ✅ o ❌ sin que esta invocación haya tocado nada.

```bash
SHA="$(git rev-parse HEAD)"
if [ "${CI_WATCH:-1}" = "0" ] || ! command -v gh >/dev/null || ! gh auth status >/dev/null 2>&1; then
    echo "⏭️  CI watch saltado (--no-ci-watch o sin gh). El run corre igual en GitHub Actions."
else
    RUN_ID="$(gh run list --branch master --commit "$SHA" \
        --workflow=validation-coverage.yml --json databaseId -q '.[0].databaseId' 2>/dev/null || true)"
    # El run puede tardar unos segundos en aparecer; reintentá 1-2 veces si viene vacío.
    if [ -n "$RUN_ID" ]; then
        # gh run watch es foreground: pasarle timeout: 600000 al tool Bash.
        gh run watch "$RUN_ID" --exit-status; echo "CI_RC=$?"
    else
        echo "⚠️  aún no aparece el run para $SHA; revisá: gh run list --branch master --limit 3"
    fi
fi
```

- `CI_RC=0` → ✅ run en verde (cubre el shellcheck que quizá no corrió local en T1).
- `CI_RC≠0` → ⚠️ **CI rojo en master**: reportá el job fallido +
  `gh run view <RUN_ID> --log-failed`. `master` ya está integrado (direct-to-master:
  no se puede "des-pushear") → el operador arregla **hacia adelante** con un commit de
  fix. NO revierte el commit ya hecho.
- Sin `gh` → saltar; el run corre igual en GitHub Actions (revisar a mano).
- El `gh run watch` expiró (exit 143) o el run no apareció tras 1-2 reintentos →
  **NO re-bloquees**: montá el watcher canónico del «Cierre asíncrono de CI»
  sobre `master@<SHA>` (su loop tolera el run ausente), reportá la fila
  `Monitor CI 👁️` y seguí al Output final — la notificación trae el veredicto
  (rojo ⇒ fix hacia adelante; master no se des-pushea). Con `--no-ci-watch` NO
  se monta nada: el opt-out es del operador.

---

# Path C — `--all-repos` (multi-repo de ESTE host, dos fases)

Sólo alcanzable desde `vps-ops-toolkit` (gate en Phase 0). Recorre los repos del
host — misma lista que `$git-commit --all-repos` — reusando los Paths A y B por
repo, pero **separando la integración de la espera del CI**: si se hiciera repo
por repo de punta a punta, el tiempo total sería la suma de todos los CI. Al
pushear todo primero, los runs de GitHub corren en paralelo y el total es ≈ el
del CI más lento.

**No hay eje `--all-vps`**: no se mergea a ciegas en clones de otros VPS, que
pueden estar sucios o parados en una rama de release.

```bash
OPS_ROOT="$HOME/webapps/vps-ops-toolkit"
source "$OPS_ROOT/scripts/lib/bootstrap-common.sh"
PROJECT_DEFS_QUIET=1 source "$OPS_ROOT/scripts/lib/project-definitions.sh"
REPOS=("${LOCAL_PROJECTS[@]}" "vps-ops-toolkit")
echo "🔧 Path C — ${#REPOS[@]} repos en este host:"
printf '   - %s\n' "${REPOS[@]}"
```

## Phase C1 — Integrar todos (rápido, sin esperas)

**Sobre qué opera C1:** los **PRs de sesión ya abiertos** y, si hace falta un tree,
los **worktrees de sesión** de cada repo
(`bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh" list --all`).
El **clon principal** de un repo de proyecto es el checkout del servicio: se lee, no
se commitea. Por cada repo en `REPOS` (lectura desde `$HOME/webapps/<repo>`, sin
`checkout` ni `stash`):

1. **Nada que hacer** — `git status --porcelain` vacío **y** sin commits sin
   pushear (`git log @{u}..HEAD`). No generes mensaje ni toques nada; antes de
   clasificar corré el chequeo de **Phase 1.5** (sonda SHA ref-neutral):
   - la rama ya está contenida en la base → ⏭️ `skipped:ya-en-base`. Nombrá la
     rama obsoleta (**no la borres**); el clon principal se deja como está (si el
     operador quiere desplegar `deploy_branch=`, se deriva a
     `deploy-project.sh --apply`; esta skill nunca avanza el checkout del
     servicio).
   - no está → ⏭️ `skipped:sin-cambios`, como hasta ahora.
2. **Clon principal sucio sobre una rama base** (`main`/`master`/release con
   `dirty>0`) → **⚠️ `skipped:anomalía-clon-principal`**: es trabajo de otra sesión
   o del operador en el tree del servicio. Se **reporta con el conteo de archivos y
   NO se commitea, ni se stashea, ni se revierte**. El trabajo de sesión vive en
   `.wt/`.
3. **Coordenada** (Phase 0.5). `host_status=wrong-host` → ⏭️
   `skipped:wrong-host:<vps_work>`; ese repo se trabaja en otro VPS.
   Rama del PR = head de un PR abierto (la MISMA prueba de Phase 0.5 sobre
   `open_pr`, no `pr_state=single`) → `release-hold`, salvo que `release_merge=`
   nombre exactamente esa rama (autorización de projects.yml) → `mergeable`.
4. **Toolkit** → Path B completo (T1 green gate → T2 commit+push → T3
   propagación). Es el único repo donde C1 commitea, y lo hace en su `master`
   (flujo trunk). Un `GATE:RED` marca `failed:green-gate` para **ese** repo y
   sigue con el resto.
5. **Proyecto** → Path A Phases 1 → 1.5 → 2 sobre el **worktree de la sesión dueña**
   (commit + push + short-circuit ya-en-base + asegurar PR); si no hay worktree ni
   nada que commitear, C1 es sólo censo: el PR ya está abierto. Sin la 1.5, una rama
   ya mergeada llega a Phase 2 y abre un PR vacío. Sobre una rama release **no se
   crea PR nuevo**: el del release ya existe y es el que `gh pr view "$CURRENT"`
   encuentra.
6. **Registrar** una fila: `repo · rama · PR# · clasificación`, con clasificación
   en `mergeable` / `release-hold` / `skipped:<razón>` / `failed:<razón>`.

Al cerrar C1, mostrá la tabla de integración antes de entrar a C2 — el operador
tiene que poder cortar ahí si algo no le cierra.

## Phase C2 — Esperar CI y mergear

Sólo sobre los repos cuya clasificación es `mergeable` o `release-hold` (los
`skipped` y `failed` no tienen nada corriendo). Por cada uno:

1. Phase 3 (esperar el CI) → si rojo, Phase 4 (fix loop, con las mismas reglas:
   pausa si hay que tocar código de producción salvo `--autonomous`).
2. `mergeable` → Phase 5 (merge) + Phase 6 (post-merge).
3. `release-hold` → reportá el veredicto del CI y **no mergees** (⏸️). Es el
   caso normal, no un error. (Una release autorizada por `release_merge:` ya
   quedó clasificada `mergeable` en C1 y se mergea como cualquier rama —
   consumiendo la autorización, Phase 5.)

**Política de errores**: ningún fallo individual corta el barrido. Un repo que
falla queda con su razón en la tabla y se sigue con el siguiente. El reporte
final lista los N repos con su estado.

---

## Cierre asíncrono de CI

**Por qué:** un CI-wait bloqueante (`gh pr checks --watch`, `gh run watch`) corre
foreground bajo el timeout de la tool Bash (default 120000 ms; máx 600000) — una
suite E2E larga lo mata con exit 143 y el veredicto se pierde. La alternativa: el
veredicto llega como **notificación de una task de fondo** (Bash con
`run_in_background`), que corre detached, sobrevive turnos y no está sujeta al
timeout foreground. Esta sección es el contrato canónico; $merge-queue y
$all-in-base lo instancian por prosa.

**Regla de no-redundancia:** se monta un watcher SÓLO si queda un run/checks EN
VUELO cuyo veredicto esta sesión no vio. Antes de montar, UN chequeo
`--json status`: si ya está `completed` → veredicto inline, sin watcher. Verde ya
confirmado (T4 con `CI_RC=0`, `--watch` con RC=0, short-circuit ya-en-base) ⇒
nada. Rojo ya visto ⇒ nada (ya se reportó con `--log-failed`). **Máximo un
watcher por objeto** — jamás dos del mismo run/PR.

**Qué monitorear por caso:**

| Caso | Al cierre |
|---|---|
| Path A mergeado | el run de la BASE para el merge SHA (`gh pr view <n> --json mergeCommit`) si sigue en vuelo — el CI del PR validó la rama, no el squash sobre la base movida. Repo sin CI on-push a la base → nada, y se dice |
| Path A release-hold | nada — Phase 3 ya vio el veredicto del PR; watcher sólo si su `--watch` expiró |
| Path A ya-en-base (1.5) | nada — el CI que gateó aquel merge ya corrió |
| Path B toolkit | nada si T4 vio `CI_RC`; watcher sobre `master@<SHA>` sólo si el watch expiró o el run no apareció; con `--no-ci-watch`, nada (opt-out del operador) |
| Path C / $merge-queue | **nada sobre la base** — merge-queue no la vigila: su validación es el run del tren de integración (montado y consumido en su Phase 5) más el verde propio de cada PR; el CI de la base sólo se imprime como eco informativo. Jamás watchers de PRs ya mergeados; los deferred con `--watch` expirado ya montaron el suyo |
| $all-in-base | sweep de watchers propios obsoletos; mount nada propio (la delegación monta el suyo) |

**Watcher canónico (run de una rama)** — montar con Bash `run_in_background:
true`. El bloque es autocontenido: los literales se hornean AL MONTAR (las
variables no persisten entre bloques y `-R` lo hace cwd-independiente). Se
auto-capea a 2h y **emite igual al agotarse** — el silencio nunca es éxito:

```bash
R="<owner/repo>"; BR="<base>"; SHA="<sha>"; L="CI-MONITOR [<repo> base:<base>@<sha7>]"
ID=""; ST="absent"; CONC=""
for i in $(seq 1 240); do          # 240 × 30s = 2h de tope propio
  read -r ID ST CONC <<<"$(gh run list -R "$R" --branch "$BR" --commit "$SHA" --limit 1 \
    --json databaseId,status,conclusion -q '.[0] | "\(.databaseId) \(.status) \(.conclusion)"' 2>/dev/null)"
  [ "$ST" = "completed" ] && break
  sleep 30
done
case "$CONC" in
  success) echo "$L ✅ success (run $ID). NEXT: nada pendiente — cerrar." ;;
  failure|cancelled|timed_out)
    echo "$L ❌ $CONC (run $ID). NEXT: gh run view $ID -R $R --log-failed → fix hacia adelante." ;;
  *) if [ -z "$ID" ]; then echo "$L ⚠️ run ausente para $SHA tras 2h. NEXT: gh run list -R $R --branch $BR --limit 3"
     else echo "$L ⚠️ watcher agotado (status=$ST, run $ID). NEXT: gh run view $ID -R $R"; fi ;;
esac
```

**Variante PR-checks** (mismo esqueleto, para un PR cuyo `--watch` expiró):
terminal cuando `gh pr checks <n> -R <slug> --json bucket -q
'[.[]|select(.bucket=="pending")]|length'` llega a 0; rojo si algún bucket ∈
{fail, cancel}. `NEXT:` verde = «retomar merge-when-green Phase 5 (merge) del PR
#<n>» · rojo = «Phase 4 (fix loop): gh run view <id> --log-failed».

**Labels:** `CI-MONITOR [<repo>#<pr> tren]` · `CI-MONITOR [<repo>#<pr> hold]` ·
`CI-MONITOR [<repo> base:<default>@<sha7>]` — estables, horneados como literal al
montar. El reporte final lista el **ledger**: `label → qué vigila → acción al
resolver` (la referencia cruzada cuando llega cada notificación).

**Reanudación por notificación:** (1) al montar un watcher, registralo en el
reporte: «👁️ `CI-MONITOR [<label>]` montado (task de fondo) — al llegar su
notificación: <acción>». (2) La línea final del watcher es autosuficiente (label
+ veredicto + `NEXT:`): al recibir una notificación cuyo output contenga
`CI-MONITOR [`, tratala como continuación de esta skill **sin reconstruir
contexto** — respondé con UNA línea de veredicto y ejecutá el `NEXT:` de la
línea, sin importar cuántos mensajes hubo en el medio. (3) Si el `NEXT:` retoma
una fase (p.ej. «retomar Phase 5 del PR #n»), **re-verificá el estado en vivo
antes** (`gh pr view <n> --json state,mergeStateStatus` — otro proceso pudo
mergearlo/cerrarlo mientras tanto) y recién entonces ejecutala. (4) Con varios
watchers en vuelo jamás asumas cuál resolvió: **el label lo dice**; respondé
sólo por el que notificó y dejá los demás listados como "en vuelo".

**Higiene de shells (sweep → mount, siempre en ese orden):**
- **Matable (las tres condiciones a la vez):** la task la montó ESTA sesión · su
  comando/output lleva el prefijo `CI-MONITOR [` · quedó obsoleta — su run/PR ya
  está `completed`/mergeado (confirmalo con UN `gh run view <id> --json status`
  ANTES de matar) o duplica un watcher del mismo objeto. Matar con `TaskStop`.
- **Intocable:** cualquier shell sin el prefijo o fuera del ledger de la sesión —
  dev servers de `dev-up`, `tailscale up`, tasks del operador, otras sesiones.
  Fuente: tu propio contexto/ledger, **jamás `ps`**. En duda: reportar, no matar.
- **Orden fijo — sweep ANTES de mount:** el watcher nuevo aún no existe
  (imposible matarlo por error) y el trabajo recién hecho es lo que invalidó los
  viejos. Doble seguro: el label nuevo lleva el run-id/SHA nuevo, así que ni un
  sweep torpe lo matchea.

**Degradación (espejo Codex):** si el harness no soporta shells de
fondo con notificación, saltá mount y sweep, y dejá en Next steps el comando
manual `gh run watch <id> -R <repo>`.

**Output final:** si esta sección montó o barrió algo, agregá la fila condicional
`Monitor CI` (👁️ montado + label / 🧹 N barridos) a la tabla y el bullet de
respaldo manual en Next steps. Sin actividad de monitores: sin fila (cero ruido).

---

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos
(reglas de gating de $output-protocol §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| --merge-method=merge\|rebase | mergear el PR sin squash (conserva los commits de la rama) | `$merge-when-green --merge-method=merge` |
| --fix-nontest | deja que el fix loop arregle también código no-test (lint/gates rojos) | `$merge-when-green --fix-nontest` |
| Ver el PR en el browser | abrir el PR para review manual | `gh pr view <n> --web` |
| Drenar varias ramas/PRs pendientes | si el repo acumuló trabajo de varias sesiones (N ramas/PRs), la cola ordenada la arma $merge-queue | `$merge-queue` |

NUNCA ofrecer `--autonomous` ni `--no-verify` como opciones — se tipean
deliberadamente (pausa del fix loop / green gate del toolkit). El merge de una
release tampoco se ofrece: lo decide `release_merge:` en projects.yml.

## Output final

Reportar siguiendo $output-protocol. Si el «Cierre asíncrono de CI» montó o
barrió monitores, agregá la fila condicional `Monitor CI` (👁️ montado + label /
🧹 N barridos) y el bullet de respaldo manual en Next steps; sin actividad de
monitores, sin fila.

**Path A — proyecto (`$merge-when-green` en un repo con PR/CI):**

```markdown
🟢 merge-when-green OK
✨ Todo en orden — no hay acciones pendientes.

| Dimensión | Estado | Detalle |
|---|---|---|
| Coordenada | ✅ | pr_state=<x> · host=<on-work-host> · merge permitido |
| Commit + push | ✅ | <sha> en la rama <rama> |
| PR | ✅ | #<n> — <url> |
| CI checks | ✅ | N/N en verde (pytest, jest, playwright, gates) |
| Fix loop | ⏭️ | no hizo falta (CI verde de una) |
| Merge | ✅ | --<method> a <base>, rama borrada |
```

Reemplazá ✅ por ⚠️/❌/⏸️ según corresponda y agregá `## Next steps`:
- **Trabajo ya en la base** (Phase 1.5) → veredicto `⏭️ merge-when-green — nada que
  integrar: <rama> ya está en <base> (verificado)`. La tabla cambia de forma: el
  valor de la corrida es **la verificación**, así que lleva fila propia y
  PR/CI/Merge quedan en ⏭️:

  | Dimensión | Estado | Detalle |
  |---|---|---|
  | Coordenada | ✅ | pr_state=<x> · host=on-work-host |
  | Trabajo vs <base> | ✅ | <señal>: 0 commits por delante / merge no-op · PR #<n> |
  | Commit + push | ⏭️ | working tree limpio, nada nuevo que commitear |
  | PR / CI / Merge | ⏭️ | no se crea PR, no se espera CI, no se mergea |
  | Clon principal | ⏭️ | intacto (no se hace checkout ni pull) · rama obsoleta: <rama> |

  `## Next steps` (la rama obsoleta **no** se borra sola):
  - `gh run list --branch <base> --limit 5` — mirar el CI de `<base>` igual, si querés.
  - (manual) `git branch -D <rama>` — borrar la rama local. Va `-D` y **no** `-d`:
    tras un **squash merge** los commits de la rama no son ancestros de `<base>`, así
    que `-d` la rechaza aunque el trabajo esté 100% integrado.
- **Rama release ya en la base** → mismo corte, pero mostrá las dos cosas:
  `Coordenada` en ⏸️ (sigue siendo release) y `Trabajo vs <base>` en ✅. Un PR release
  abierto sobre una rama ya mergeada es un dato que el operador quiere ver, con
  `gh pr view <n> --web` en next steps.
- **Rama release sin autorizar** → veredicto `⏸️ merge-when-green — release
  integrada y verde, sin mergear`, fila `Merge` en ⏸️ con "rama release; sin
  `release_merge:` en projects.yml" y next step: setear `release_merge: <rama>`
  al proyecto en projects.yml (vps-ops-toolkit) y re-invocar `$merge-when-green`.
- **Release autorizada mergeada** → fila `Merge` en ✅ con "release lanzada
  (`release_merge` consumida)" y next steps: `$git-commit` en el toolkit (el
  projects.yml editado quedó pendiente) + `resolve-work-coordinate.sh --apply
  <proyecto>` para refrescar `branch_working`/`branch:`.
- **`release_merge` stale** (nombra una rama sin PR abierto) → next step con la
  limpieza del campo (el `awk` de Phase 5) o su corrección en projects.yml.
- **Host equivocado** (`host_status=wrong-host`) → `⏭️ merge-when-green — N/A`,
  fila `Coordenada` en ⏭️ y next step `tailscale ssh ryzepeck@<vps_work>`.
- **Coordenada no resoluble** → fila `Coordenada` en ℹ️ diciendo que el guard de
  release no pudo evaluarse; nunca omitir la fila.
- Fix loop que pausó por código de prod → ⏸️ + el cambio a aprobar.
- Gate no-test rojo (sin `--fix-nontest`) → ❌ + el comando local para reproducirlo.
- Merge bloqueado por review/ruleset → ❌ + `gh pr view <n> --web` para revisar.
- Superó `MAX_ITER` sin verde → ❌ + qué test sigue rojo y el comando del próximo intento.

**Path B — toolkit (`$merge-when-green` en `vps-ops-toolkit`):**

```markdown
🟢 merge-when-green (toolkit) OK
✨ master integrado y en verde.

| Dimensión | Estado | Detalle |
|---|---|---|
| Green gate local | ✅ | bash -n N/N · projects.yml 0 err · config-integrity 0 err (shellcheck ⏭️ no local) |
| Commit + push | ✅ | <sha> → master |
| Propagación fleet | ✅ | vps-X SYNCED · vps-Y SYNCED · dev UNREACHABLE |
| CI master | ✅ | validation-coverage verde (<run-url>) |
```

Reemplazá ✅ por ⚠️/❌/⏸️ según corresponda y agregá `## Next steps`:
- **Nada que integrar** (T2 cortó: tree limpio + `HEAD` ancestro del SHA remoto de `master`)
  → veredicto `⏭️ merge-when-green (toolkit) — master ya contiene todo`, fila nueva
  `Estado vs master remoto` en ✅ con el SHA corto, y `Commit + push` /
  `Propagación fleet` / `CI master` en ⏭️. Next steps:
  `bash scripts/maintenance/propagate-toolkit-commit.sh --check` (confirmar el fleet)
  y `gh run list --branch master --limit 5` (mirar el CI igual).
- Green gate rojo → ❌ + el validador que falló y su comando local (`bash scripts/ci/<x>.sh`).
- Push falló → ❌ + causa (no upstream / conflicto remoto) + `$git-sync`.
- Propagación con `CONFLICT_NEEDS_MANUAL_SYNC` → ⚠️ + los hosts que requieren `git-sync` manual.
- CI rojo en master post-push → ⚠️ + el job fallido + `gh run view <id> --log-failed` (fix hacia adelante).

**Path C — `--all-repos` (multi-repo):** una fila por repo, columna `Repo` antes
de `Dimensión`. Es tabla grande (>15 filas con varios repos) → anteponer
`### Resumen ejecutivo` con el conteo por clasificación.

```markdown
🟡 merge-when-green (--all-repos) OK con N warning(s) — 11 repos

### Resumen ejecutivo
mergeados: N · release-hold: N · ya en base: N · sin cambios: N · wrong-host: N · fallidos: N

| Repo | Rama | PR | CI | Resultado |
|---|---|---|---|---|
| projectapp | feat/… | #124 | ✅ verde | ✅ mergeado (squash) |
| vastago_project_staging | release-may-2026-v2 | #12 | ✅ verde | ⏸️ release — no se mergea |
| kore_project | — | — | — | ⏭️ wrong-host → vps-projectapp-staging |
| mimittos_project | — | — | — | ⏭️ sin cambios |
| taptag | fix/… | #41 | — | ⏭️ ya en base (lo llevó #41) |
| vps-ops-toolkit | master | — | ✅ verde | ✅ push + fleet SYNCED |
```

`## Next steps` sólo con lo accionable: los `failed:*`, los `release-hold` que ya
estén listos para lanzar, y los `wrong-host` con el `tailscale ssh` de destino. Los
`skipped:ya-en-base` **no** van a Next steps: la fila ya nombra la rama obsoleta y
borrarla es decisión del operador, repo por repo.
