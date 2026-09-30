---
name: merge-queue
description: "Usar cuando VARIAS ramas/PRs pendientes (trabajo de N sesiones paralelas) deben integrarse en orden: 'mergeá todo lo pendiente', 'drená las ramas', 'cerrá el trabajo de todas las sesiones', 'merge queue/train'. Censa el trabajo pendiente (PRs de sesión con dueño en el body + ramas sin PR + local-only + gone + ya-en-base), arma la estrategia en dos niveles (tier 1: sesiones→release o →default; tier 2: release→default sólo con release_merge y tier 1 drenado) y ejecuta: batch de verdes disjuntos server-side + TREN DE INTEGRACIÓN (rama temporal queue/integration-* que valida la COMBINACIÓN con UN solo run de CI — verde ⇒ merges de corrido sin re-CI por unidad; rojo ⇒ bisect). NO espera ni vigila el CI de la base: la confianza está en el verde de cada sesión + el run del tren. Al cerrar avisa a cada sesión dueña que su trabajo ya aterrizó y le pide su propio visto bueno con `/all-in-base --check-only` (fire-and-forget, no espera respuesta). Conflictos semánticos y fix loop se DELEGAN a la sesión dueña vía SendMessage (señal de resuelto = push al head; timeout ⇒ inline). En cada pausa y al final emite el Tablero de estado. NO usar para una sola rama ([[merge-when-green]]), ni para commits sueltos ([[git-commit]]), ni para sync sin merge ([[git-sync]]), ni en cron/headless. Nunca rebasea ramas pusheadas (force push denegado); nunca toca el checkout del clon principal: toda mutación de tree ocurre en el worktree propio de la queue (~/webapps/.wt/<repo>/queue-*)."
allowed-tools: Bash, AskUserQuestion, ListAgents, SendMessage, TaskStop
argument-hint: "[--all-repos] [--plan-only] [--batch-only] [--include-no-pr=r1,r2] [--autonomous] [--max-iterations=N]"
---

> **⚠️ How to invoke**:
> - Sin argumento: `/merge-queue` → arma y ejecuta la cola de merges del repo git
>   del **cwd** (resuelto con `git rev-parse --show-toplevel`). Pensada para el
>   estado que N sesiones paralelas dejan atrás: varias ramas/PRs pendientes que,
>   mergeados sin orden, generan conflictos y reprocesos.
> - Con `--all-repos` (**sólo desde `vps-ops-toolkit`**): una cola por cada repo de
>   `LOCAL_PROJECTS` del host. Los repos son independientes entre sí: primero se
>   integra todo (los CI corren en paralelo), después se mergea repo por repo. El
>   toolkit NO es unidad de cola (trunk flow, sin ramas): sólo aparece al cierre,
>   para commitear en UN solo paso el `projects.yml` que los merges de release
>   hayan dejado dirty.
> - `--all` / `--all-vps` → **error duro**: no se mergea a ciegas en clones de
>   otros VPS (mismo racional que [[merge-when-green]]).
> - `--plan-only`: censo + estrategia + tabla del plan, sin ejecutar nada.
> - `--batch-only`: ejecuta sólo el batch (verdes disjuntos, server-side); el tren
>   queda planificado en Next steps.
> - `--include-no-pr=r1,r2`: incluye esas ramas sin PR en la cola sin preguntar
>   (útil para re-invocar tras un primer censo).
>
> **Qué ejecuta cada merge:** los guards de [[merge-when-green]] (mergeable,
> `gh pr merge --squash --delete-branch`, consumo de `release_merge`), pero la
> **validación de CI es por GRUPO, no por unidad**: los verdes disjuntos van en
> batch sin re-CI, y el resto se valida COMBINADO en el tren de integración (un
> solo run). Defaults heredados: squash, fix loop máx 5 iteraciones
> (`--max-iterations=N`).
>
> **Dos niveles (two-tier, protocolo por sesión):** tier 1 = PRs de sesión hacia
> su base de integración (la release en repos participantes, la default en
> prod-directos). Tier 2 = la release hacia la default, SÓLO si `release_merge:`
> la autoriza **y** el tier 1 de esa release quedó drenado (0 PRs de sesión
> colgando de ella — mergear la release con hijos vivos los dejaría apuntando a
> una base muerta). La release va al FINAL de la cola de su repo.
>
> **Guards siempre ON (heredados):** coordenada (`resolve-work-coordinate.sh`) —
> `wrong-host` ⇒ el repo entero se salta; una rama release se mergea SÓLO si
> `release_merge:` en projects.yml la nombra (sin autorización: se integra, se
> espera el CI y queda en hold, jamás se ofrece mergearla); tree sucio ⇒ nunca
> checkout ni stash automático; la tabla del plan SIEMPRE se muestra antes de
> ejecutar — con o sin flags, el operador puede cortar ahí (patrón C1 de
> merge-when-green).
>
> **Nunca force push:** `git push --force*` está denegado a nivel permisos del
> fleet (cubre `--force-with-lease`), así que esta skill **no rebasea ramas
> pusheadas jamás**. Una rama BEHIND se actualiza server-side
> (`gh pr update-branch`); una CONFLICTING se pone al día mergeando el SHA
> anunciado de `<base>` DENTRO de la rama — desde el **worktree de la queue, en
> detached HEAD** (`git checkout --detach <sha-rama>` + merge + `git push
> origin HEAD:refs/heads/<rama>`, fast-forward normal), porque la rama puede
> estar checkouteada en el worktree de su sesión dueña y el checkout normal
> fallaría. Con squash como merge method, esos merge commits intermedios
> desaparecen del historial final.
>
> **El clon principal es intocable:** esta skill jamás hace checkout en
> `~/webapps/<repo>` (en VPS es el tree del servicio corriendo). Toda mutación
> de working tree ocurre en su worktree propio `~/webapps/.wt/<repo>/queue-<ts>`.
> El alta/retiro de ese worktree sí escribe su ref `queue/*` y registro exacto
> en el gitdir compartido; ese alcance `gitmeta` está inventariado como
> `session-worktree` y no se disfraza como escritura exclusiva bajo `.wt/`.

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): (1) flags explícitos → ejecutar directo, sin
menú — la tabla del plan (Phase 2) se muestra igual y el operador puede cortar;
con flags, las ramas sin PR quedan **excluidas por default** (se re-invoca con
`--include-no-pr=`); (2) intención clara en la sesión ("drená todo lo pendiente")
→ proponer el comando en una línea y esperar confirmación; (3) invocación sin
flags → censo primero y UNA sola AskUserQuestion sobre el plan (Q1+Q2 fusionadas
en una llamada); (4) nunca en cron/headless ni dentro de un barrido.

**Q1 — Ejecución del plan** (`multiSelect: false`; tras mostrar la tabla):

| label | description | preview |
|---|---|---|
| Ejecutar todo (Recommended) | release autorizada + batch + tren + holds según la tabla; CIs en paralelo, merges en orden | la cola completa de la tabla |
| Sólo el batch | mergea únicamente los PRs verdes disjuntos (server-side, minutos); el tren queda en Next steps | `/merge-queue --batch-only` |
| Sólo el plan | quedarse con el censo + estrategia, sin ejecutar | `/merge-queue --plan-only` |
| Abortar | salir sin tocar nada | — |

**Q2 — Ramas sin PR a incluir** (`multiSelect: true`; SÓLO si el censo encontró
ramas con trabajo y sin PR; va en la MISMA llamada AskUserQuestion que Q1):

- Con **≤4** ramas: una fila por rama; description = la evidencia del censo
  ("fría 3d · ahead 2 · remoto vivo" / "local-only · ahead 1 · ayer").
- Con **>4**: filas-grupo por evidencia («frías >24h con remoto (N)», «tibias
  <24h (M)», «sólo local-only (K)», «ninguna») — el detalle por rama ya está en
  la tabla del plan; nombres puntuales se tipean por "Other" o se re-invoca con
  `--include-no-pr=r1,r2`.

**Qué NO se pregunta:** el merge de una rama release — lo decide `release_merge:`
en projects.yml (blocklist §4), esta skill sólo lo refleja. `--autonomous` se
tipea (quita la pausa de aprobación del fix loop, deliberadamente incómodo). La
rama ACTUAL con tree sucio nunca se ofrece: es la firma de una sesión activa sin
terminar (advisory en la tabla). El borrado de ramas obsoletas no es parte del
run: va al menú post-run, con evidencia.

## Phase 0 — Preflight + flags + lock advisory

```bash
ARGS_RAW="${ARGUMENTS:-}"
ALL_REPOS=0; PLAN_ONLY=0; BATCH_ONLY=0; AUTONOMOUS=0; MAX_ITER=5; INCLUDE_NO_PR=""
for tok in $ARGS_RAW; do
    case "$tok" in
        --all-repos)        ALL_REPOS=1 ;;
        --plan-only)        PLAN_ONLY=1 ;;
        --batch-only)       BATCH_ONLY=1 ;;
        --autonomous)       AUTONOMOUS=1 ;;
        --max-iterations=*) MAX_ITER="${tok#--max-iterations=}" ;;
        --include-no-pr=*)  INCLUDE_NO_PR="${tok#--include-no-pr=}" ;;
        --all|--all-vps)
            echo "❌ ERROR: '$tok' no existe en merge-queue."
            echo "   ¿La cola de TODOS los repos de este host? → --all-repos (sólo desde vps-ops-toolkit)"
            echo "   No hay eje fleet: no se mergea a ciegas en clones de otros VPS."
            exit 2 ;;
        *) echo "❌ ERROR: argumento desconocido '$tok'."; exit 2 ;;
    esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "❌ ERROR: el cwd no es un repo git. Lanzá Claude Code desde el repo a drenar."
    exit 2
}
cd "$REPO_ROOT"
REPO_NAME="$(basename "$REPO_ROOT")"

# --all-repos es acción de operador del fleet: el toolkit es su punto de entrada
# (mismo guard que merge-when-green Path C).
if (( ALL_REPOS == 1 )) && [ "$REPO_NAME" != "vps-ops-toolkit" ]; then
    echo "❌ ERROR: --all-repos sólo se invoca desde vps-ops-toolkit."
    echo "   Estás en '$REPO_NAME'. Para la cola de SÓLO este repo: /merge-queue (sin flags)."
    exit 2
fi

# El toolkit no tiene cola propia (trunk flow: commit directo a master, sin ramas).
if (( ALL_REPOS == 0 )) && [ "$REPO_NAME" = "vps-ops-toolkit" ]; then
    echo "❌ El toolkit no tiene cola de ramas (trunk flow)."
    echo "   ¿La cola de los proyectos de este host? → /merge-queue --all-repos"
    echo "   ¿Integrar el toolkit en sí?             → /merge-when-green"
    exit 2
fi

# gh es obligatorio: sin PRs no hay cola.
command -v gh >/dev/null || { echo "❌ ERROR: gh CLI no instalada — obligatoria."; exit 2; }
gh auth status >/dev/null 2>&1 || { echo "❌ ERROR: gh sin auth — corré 'gh auth login'."; exit 2; }

# Lock advisory per-repo en /tmp (a propósito: tiene que ser visible ENTRE
# sesiones de esta máquina; un scratchpad per-sesión no sirve acá). No es
# exclusión dura: protege del accidente de dos merge-queue simultáneos, no de un
# /merge-when-green suelto. TTL 30 min; cada fase re-toca el lock (los archivos
# SÍ persisten entre bloques bash, las variables no).
QDIR="/tmp/merge-queue-${REPO_NAME}"
if [ -f "$QDIR/lock" ] && [ -n "$(find "$QDIR/lock" -mmin -30 2>/dev/null)" ]; then
    echo "🚫 Lock advisory fresco: $(cat "$QDIR/lock")"
    echo "   ¿Otro /merge-queue en vuelo sobre $REPO_NAME? Si estás seguro de que no:"
    echo "   rm $QDIR/lock   (y re-invocá)"
    exit 1
fi
mkdir -p "$QDIR"; date -Is > "$QDIR/lock"

MODE_LABEL="repo actual ($REPO_NAME)"
(( ALL_REPOS == 1 )) && MODE_LABEL="--all-repos (cola por repo del host)"
echo "🎯 merge-queue — $MODE_LABEL | plan-only=$PLAN_ONLY batch-only=$BATCH_ONLY autonomous=$AUTONOMOUS max-iter=$MAX_ITER"
```

Con `--all-repos`, resolvé la lista de repos (el toolkit NO entra como unidad de
cola — sólo aparece en Phase 6):

```bash
OPS_ROOT="$HOME/webapps/vps-ops-toolkit"
source "$OPS_ROOT/scripts/lib/bootstrap-common.sh"
PROJECT_DEFS_QUIET=1 source "$OPS_ROOT/scripts/lib/project-definitions.sh"
echo "🔧 Colas a censar — ${#LOCAL_PROJECTS[@]} repos de proyecto:"
printf '   - %s\n' "${LOCAL_PROJECTS[@]}"
```

Las Phases 1–6 corren **por repo**. En modo default hay un solo repo (el del
cwd) y ningún loop real. En `--all-repos`, las Phases 1–2 se completan para TODOS
los repos antes de ejecutar nada (la tabla del plan es una sola, multi-repo), la
Phase 3 integra todo el host de una vez (CIs en paralelo), y las Phases 4–5
drenan repo por repo. Cada bloque bash **re-ancla** su contexto (cd al repo +
re-derivar `QDIR`/`DEFAULT`/`CURRENT` + `touch` del lock): las variables no
sobreviven entre bloques.

## Phase 1 — Censo (read-only, por repo)

Nada de esta fase muta el repo. Junta los datos crudos; la clasificación la hacés
vos (Claude) en contexto con las clases de abajo.

```bash
# Re-anclaje: en modo default, el repo del cwd; en --all-repos, cd al repo de la
# iteración bajo ~/webapps/<repo>.
cd "$(git rev-parse --show-toplevel)"
REPO_NAME="$(basename "$PWD")"
QDIR="/tmp/merge-queue-${REPO_NAME}"
# En --all-repos cada repo tiene su propio lock: uno fresco ajeno ⇒ skipped:locked
# (se registra en la tabla y se sigue con el próximo repo).
if [ -f "$QDIR/lock" ] && [ -n "$(find "$QDIR/lock" -mmin -30 2>/dev/null)" ] \
   && ! grep -q "$(date -I)" "$QDIR/lock" 2>/dev/null; then
    echo "⏭️  $REPO_NAME: lock advisory ajeno fresco — skipped:locked"
fi
mkdir -p "$QDIR"; date -Is > "$QDIR/lock"

DEFAULT="$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo master)"
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
echo "=== $REPO_NAME | base=$DEFAULT | rama actual=$CURRENT ==="
echo "--- tree (sucio = posible sesión activa sin terminar) ---"
git status --porcelain | head -5

echo "--- coordenada (guards heredados) ---"
bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh" \
     --check "$REPO_NAME" 2>/dev/null || true

echo "--- PRs abiertos (enumeración propia: el resolver NO lista PRs feature en prod-directos) ---"
# body: de ahí sale la sesión dueña (línea 'Sesión:') y la intención — el
# contrato de ownership del protocolo por sesión. isDraft: los drafts (p.ej. el
# PR de integración de una corrida anterior) se EXCLUYEN de la cola.
gh pr list --state open \
   --json number,headRefName,baseRefName,createdAt,isDraft,mergeable,mergeStateStatus,statusCheckRollup,body \
   -q '.[] | {number,headRefName,baseRefName,createdAt,isDraft,mergeable,mergeStateStatus, checks: ([.statusCheckRollup[]?.conclusion] | join(",")), sesion: ((.body // "" | capture("Sesi[oó]n:\\s*(?<s>[^\\n]+)") .s) // "—")}'
# La RELEASE del repo (si participa): base de integración del tier 1.
RELEASE="$(bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh" \
   --check "$REPO_NAME" 2>/dev/null | awk -F= '$1=="pr_state"{ps=$2} $1=="resolved_branch"{rb=$2} END{if(ps=="single") print rb}')"
echo "RELEASE (tier-1 base si participa): ${RELEASE:-n/a — prod-directo o sin release}"
echo "--- merges recientes (señal doble-orquestador: <10 min ⇒ ⚠️) ---"
gh pr list --state merged --limit 3 --json number,mergedAt,title

echo "--- ramas locales (upstream · track · edad) ---"
git for-each-ref refs/heads \
   --format='%(refname:short)|%(upstream:short)|%(upstream:track)|%(committerdate:iso8601)'

echo "--- por rama local: ahead/behind + ya-en-base vs SU base de tier (merge-tree in-memory) ---"
# La base de comparación de cada rama es la de SU tier: la del PR si tiene
# (baseRefName del listado de arriba), la RELEASE si estamos en repo
# participante, la default si no. El loop evalúa contra ambas cuando hay
# RELEASE — la clasificación (abajo, en contexto) usa la que corresponda.
DEFAULT_TIP=""
for TB in "$DEFAULT" ${RELEASE:+"$RELEASE"}; do
    TIP_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin "refs/heads/$TB" 2>/dev/null || true)"
    TIP="${TIP_LINE%%[[:space:]]*}"
    if ! echo "$TIP" | grep -Eq '^[0-9a-fA-F]{40,64}$'; then
        echo "  $TB: no evaluable (tip remoto inaccesible)"; continue
    fi
    git cat-file -e "${TIP}^{commit}" 2>/dev/null \
      || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$TIP"
    [ "$TB" = "$DEFAULT" ] && DEFAULT_TIP="$TIP"
    BASE_TREE="$(git rev-parse "${TIP}^{tree}" 2>/dev/null || echo none)"
    echo "· vs $TB@$TIP:"
    for BR in $(git for-each-ref refs/heads --format='%(refname:short)'); do
        [ "$BR" = "$TB" ] && continue
        case "$BR" in queue/*) continue ;; esac   # ramas de integración: jamás unidades
        AHEAD="$(git rev-list --count "${TIP}..${BR}" 2>/dev/null || echo '?')"
        BEHIND="$(git rev-list --count "${BR}..${TIP}" 2>/dev/null || echo '?')"
        # merge-tree es in-memory: evaluable aun con tree sucio (la restricción
        # "tree sucio ⇒ no evaluar" de merge-when-green aplica sólo a la rama
        # ACTUAL, cuyo trabajo sin commitear es de ella).
        MT="$(git merge-tree --write-tree "$TIP" "$BR" 2>/dev/null | head -1)"
        if [ -n "$MT" ] && [ "$MT" = "$BASE_TREE" ]; then
            echo "  $BR: YA-EN-BASE de $TB (mergearla sería no-op)"
        else
            echo "  $BR: ahead=$AHEAD behind=$BEHIND"
        fi
    done
done

echo "--- ramas remotas sin rama local (trabajo pusheado desde otra máquina) ---"
if [ -n "$DEFAULT_TIP" ]; then
  GIT_TERMINAL_PROMPT=0 git ls-remote --heads origin | while read -r REMOTE_SHA REMOTE_REF; do
    B="${REMOTE_REF#refs/heads/}"
    case "$B" in "$DEFAULT"|HEAD|queue/*) continue ;; esac
    [ -n "${RELEASE:-}" ] && [ "$B" = "$RELEASE" ] && continue
    git show-ref --verify --quiet "refs/heads/$B" && continue
    git cat-file -e "${REMOTE_SHA}^{commit}" 2>/dev/null \
      || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$REMOTE_SHA"
    AHEAD="$(git rev-list --count "${DEFAULT_TIP}..${REMOTE_SHA}" 2>/dev/null || echo 0)"
      [ "$AHEAD" != "0" ] && echo "remote-only $B: ahead=$AHEAD"
  done
fi

echo "--- worktrees del repo (sesiones activas + huérfanos) ---"
git worktree list --porcelain | sed -n 's/^worktree //p'
```

**Clasificación (una clase por unidad de trabajo — rama o PR):**

| Clase | Criterio | Destino |
|---|---|---|
| `session-pr` | PR abierto no-draft con base = SU base de tier (la release en repo participante, la default en prod-directo). El body declara `Sesión:`/`Intención:` — sin esas líneas: fila advisory `sin-dueño` (se drena igual; la delegación degrada a heurística) | tier 1: batch o tren |
| `remoto-sin-PR` | rama (local o remote-only) con remoto vivo, ahead>0, sin PR — violación del protocolo por sesión (PR al primer push); se censa igual | operator-gated (Q2) |
| `local-only` | rama sin upstream, ahead>0 | operator-gated (Q2) |
| `gone-limpia` | upstream `[gone]` **y** ya-en-base | cleanup (sólo reporte) |
| `gone-con-trabajo` | upstream `[gone]` pero NO ya-en-base | operator-gated (Q2) |
| `ya-en-base` | merge-tree == árbol de SU base de tier | cleanup (sólo reporte) |
| `fría >48h` | unidad con último commit >48h — deuda de drenaje del protocolo | se drena igual + ⚠️ en la tabla |
| `diverged` | local y su remoto ahead entre sí | excluida — irresoluble sin force push; nota en Next steps |
| `base-rara` | PR cuya base no es NI la default NI la release del repo | excluida — `gh pr edit <n> --base <base-correcta>` |
| `queue/*` / PR draft de integración | restos de una corrida (ésta u otra) | jamás unidades — cleanup si quedaron huérfanos |
| `release` | head = candidato del resolver (`open_pr`, base=default) | tier 2: autorizada (`release_merge=`) → al FINAL, sólo con su tier 1 drenado · sin autorizar → hold |
| `rama-actual-sucia` | `CURRENT` con tree sucio | advisory "posible sesión activa" — excluida de auto-ejecución, jamás se ofrece |

`host_status=wrong-host` ⇒ el **repo entero** se salta (⏭️ con el
`tailscale ssh ryzepeck@<vps_work>` de destino), igual que merge-when-green.

## Phase 2 — Estrategia + tabla del plan + LA única pregunta

**Matriz de solapamiento** entre las unidades ejecutables (aproximación barata y
explicable; GitHub sigue siendo la autoridad al mergear — por eso Phase 4/5
re-verifican en vivo):

```bash
cd "$(git rev-parse --show-toplevel)"; REPO_NAME="$(basename "$PWD")"
QDIR="/tmp/merge-queue-${REPO_NAME}"; touch "$QDIR/lock"; mkdir -p "$QDIR/files"
# <unidades>: las ramas ejecutables del censo. REF por unidad: el SHA remoto
# capturado en Phase 1 si vive; la rama local si es local-only. BASE_U por unidad
# = el SHA de su base de tier
# (baseRefName del PR; la release para tier-1 en repos participantes; la default
# si no). El diff va contra BASE_U — no siempre la default.
# El filename del set de archivos usa base64 url-safe: el aplanado ingenuo
# `${U//\//_}` colisionaba (`a/b` y `a_b` → mismo archivo).
key() { printf '%s' "$1" | base64 | tr -d '=\n' | tr '/+' '_-'; }
for U in <unidades>; do
    git diff --name-only "<BASE_SHA_U>...<UNIT_SHA_O_LOCAL>" 2>/dev/null | sort > "$QDIR/files/$(key "$U")"
done
for A in <unidades>; do for B in <unidades posteriores a A, mismo tier/base>; do
    N="$(comm -12 "$QDIR/files/$(key "$A")" "$QDIR/files/$(key "$B")" | wc -l)"
    (( N > 0 )) && echo "SOLAPA: $A ⇆ $B ($N archivo(s) en común)"
done; done
```

**Armado de la cola (el orden ES la estrategia; two-tier):**

1. `[BATCH]` (tier 1) — PRs de sesión con CI verde + `MERGEABLE` + **disjuntos
   entre sí** (misma base de tier); orden: más viejo primero (`createdAt`).
   Merges consecutivos server-side, sin esperas entre sí.
2. `[TREN DE INTEGRACIÓN]` (tier 1) — el resto ejecutable (sin-PR incluidas por
   el operador, CI pendiente/rojo, CONFLICTING, solapadas): se valida la
   **combinación completa** con UN solo run de CI sobre una rama temporal
   `queue/integration-<ts>` y, en verde, se drenan los PRs de corrido (Phase 5).
   El orden de armado del tren sigue siendo **solapamiento ascendente**
   (desempate más-viejo-primero): minimiza conflictos al construir la
   integración y deja los "hubs" al final.
3. `[TIER 2 — RELEASE AUTORIZADA]` — la release con `release_merge:` va **al
   FINAL de la cola de su repo**, y SÓLO si su tier 1 quedó drenado (0 PRs de
   sesión abiertos con base=esa release). Mergearla con hijos vivos los dejaría
   apuntando a una base muerta; si quedan, la release pasa a
   `hold:tier1-pendiente` con la lista. La release espera su CI completo como
   siempre (el atajo sin-re-CI del tren NO aplica al tier 2).
4. `[HOLDS]` — releases sin autorizar: se integran y esperan su CI, sin merge
   (⏸️ es el caso normal, no un error). Un hold CONFLICTING sólo se REPORTA —
   no se muta una release no autorizada.
5. `[CLEANUP]` — `ya-en-base` / `gone-limpia` / restos `queue/*`: sólo reporte
   (el `-D` es del operador, menú post-run).

**Tabla del plan** (SIEMPRE se muestra, con o sin flags — el operador puede
cortar acá):

| # | Unidad (rama) | PR | Tipo | CI | Mergeable | Solapa con | Fase |
|---|---|---|---|---|---|---|---|

(En `--all-repos`: columna `Repo` primero, y la tabla cubre todos los repos antes
de ejecutar nada.)

Después de la tabla:
- `--plan-only` → saltar directo al Output final (y borrar el lock).
- Flags explícitos (`--all-repos`, `--batch-only`, `--include-no-pr=`) → ejecutar
  directo según el plan.
- Sin flags → **UNA llamada AskUserQuestion** con Q1 (+Q2 si hay ramas sin PR) —
  specs en "Cómo invocar este skill".

## Phase 3 — Integrar todo (C1-análogo: push + PR, sin esperas)

Para TODAS las unidades ejecutables de la cola (batch + tren + holds), de una
vez, así los runs de CI corren **en paralelo** y el tiempo total ≈ el del CI más
lento (racional del Path C de merge-when-green). Ningún fallo individual corta el
barrido: `failed:push` saca ESA unidad de la cola y se sigue.

```bash
cd "$(git rev-parse --show-toplevel)"; touch "/tmp/merge-queue-$(basename "$PWD")/lock"
RAMA="<unidad>"; BASE_U="<base de tier de la unidad>"   # release en participantes, default si no
# Push sólo si hace falta (local-only o local por delante de su remoto):
git push -u origin "$RAMA" || echo "failed:push — $RAMA sale de la cola, se sigue"
# Asegurar PR (state=MERGED/CLOSED no cuenta como abierto — regla de Phase 2 de
# merge-when-green). El body lleva el contrato de ownership; para ramas censadas
# sin sesión conocida, 'Sesión: — (censada por merge-queue)'.
ST="$(gh pr view "$RAMA" --json state -q .state 2>/dev/null || echo none)"
if [ "$ST" != "OPEN" ]; then
    gh pr create --head "$RAMA" --base "$BASE_U" --fill \
      --body "$(printf 'Sesión: %s\nIntención: %s\n' '<sesión dueña o "— (censada por merge-queue)">' '<intención inferida de los commits>')"
fi
gh pr view "$RAMA" --json number,url -q '"PR #\(.number) — \(.url)"'
```

- Si la unidad es la rama ACTUAL e incluye cambios sin commitear que el operador
  pidió incluir explícitamente (vía "Other" en Q2): primero el flujo de
  [[git-commit]] sobre esa rama (add selectivo + commit + push), como la Phase 1
  de merge-when-green.
- Una release (autorizada o hold) ya tiene su PR: no se crea uno nuevo.

Al cerrar esta fase, emití la primera foto del **Tablero de estado** (sección
más abajo): todo integrado, CIs corriendo en paralelo.

## Phase 4 — Batch (verdes disjuntos, server-side, cero checkouts)

Inmune al working tree: ningún checkout, así que las otras sesiones no se pisan.
Por cada PR del batch, **en orden**:

```bash
cd "$(git rev-parse --show-toplevel)"; touch "/tmp/merge-queue-$(basename "$PWD")/lock"
PR=<n>
# GitHub recomputa mergeable tras cada merge a la base: UNKNOWN transitorio.
# Poll c/5s, máx 60s — nunca mergear sobre UNKNOWN.
for i in $(seq 1 12); do
    ST="$(gh pr view "$PR" --json mergeable,mergeStateStatus -q '"\(.mergeable) \(.mergeStateStatus)"')"
    case "$ST" in "UNKNOWN"*) sleep 5 ;; *) break ;; esac
done
echo "PR #$PR → $ST"
# Checks siguen verdes (re-confirmación barata, sin --watch):
gh pr checks "$PR" >/dev/null 2>&1; CHECKS_RC=$?
case "$ST" in
    "MERGEABLE BLOCKED"*) echo "⏸️ #$PR BLOCKED (review/ruleset) → se degrada al tren" ;;
    MERGEABLE*)
        if [ "$CHECKS_RC" -eq 0 ]; then
            gh pr merge "$PR" --squash --delete-branch || echo "❌ #$PR falló el merge → tren"
        else
            echo "⚠️ #$PR con checks no-verdes ahora → se degrada al tren"
        fi ;;
    *) echo "⚠️ #$PR quedó $ST tras el merge anterior → se degrada al tren" ;;
esac
```

**Riesgo aceptado y documentado:** el CI no se re-corre entre merges del batch —
válido sólo porque sus unidades son file-disjoint (la matriz de Phase 2) y cada
PR ya llegó verde por su cuenta. **Nada valida la combinación del batch y no hay
red posterior** (la queue no vigila el CI de la base): un conflicto semántico
cross-archivo entre dos unidades disjuntas aterrizaría sin detección. Es el
riesgo que el batch compra a cambio de su velocidad; ante la duda, degradá la
unidad al tren. Todo lo degradado pasa **al tren de integración** (Phase 5)
conservando su orden relativo — ahí la combinación sí se valida.

## Phase 5 — Tren de integración (la combinación se valida UNA vez)

El tren viejo (una unidad por vez: update → CI completo → merge → la base se
movió → la siguiente paga otro ciclo) costaba N × ~27 min de CI serial y aun
así no validaba la combinación — un bug entre dos PRs sin conflicto textual
(mismo watch, hunks distintos; caso real 2026-08-16) aterrizaba en la base. El
tren v2 valida la **combinación completa con UN run** y recién después drena
los PRs de corrido.

### 5.1 — Construir la rama de integración (worktree propio + rerere)

```bash
cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
REPO_NAME="$(basename "$PWD")"; touch "/tmp/merge-queue-${REPO_NAME}/lock"
BASE_T="<base del tier>"          # release (tier 1 participante) o default
TS="$(date +%d%m%Y-%H%M)"
WT="$HOME/webapps/.wt/${REPO_NAME}/queue-${TS}"
BASE_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin "refs/heads/$BASE_T")"
BASE_SHA="${BASE_LINE%%[[:space:]]*}"
echo "$BASE_SHA" | grep -Eq '^[0-9a-fA-F]{40,64}$' || { echo "base remota ilegible"; exit 2; }
git cat-file -e "${BASE_SHA}^{commit}" 2>/dev/null \
  || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$BASE_SHA"
git worktree add --detach "$WT" "$BASE_SHA"
cd "$WT"
git switch -c "queue/integration-$TS"
```

Después, **una unidad por vez, en el orden del tren** (solapamiento ascendente):

```bash
cd "$WT"; RAMA="<unidad>"
HEAD_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin "refs/heads/$RAMA")"
HEAD_SHA="${HEAD_LINE%%[[:space:]]*}"
echo "$HEAD_SHA" | grep -Eq '^[0-9a-fA-F]{40,64}$' || { echo "head remoto ilegible"; exit 2; }
git cat-file -e "${HEAD_SHA}^{commit}" 2>/dev/null \
  || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$HEAD_SHA"
git -c rerere.enabled=true merge --no-edit "$HEAD_SHA" || echo "CONFLICTO en la integración — ver reglas abajo"
```

- Conflicto **mecánico** (registros, lockfiles, archivos generados): resolvelo
  acá mismo (reglas de git-sync Phase 6: mostrar ambos lados, nunca a ciegas;
  un archivo GENERADO se regenera con su generador, no se mergea a mano). Tras
  stagear la resolución corré `git -c rerere.enabled=true rerere`: graba el
  replay de 5.3 sin escribir `rerere.enabled` en el config del clon desplegado.
- Conflicto **semántico** (lógica real de dos sesiones): **delegá a la sesión
  dueña** (sección «Delegación» abajo). Mientras llega su push, seguí
  integrando las unidades NO afectadas; la delegada se re-integra al volver o
  sale del tren por timeout (`deferred:delegada`).
- Merge irrecuperable ⇒ `git merge --abort`, la unidad sale
  (`failed:integracion`) y el tren sigue.

### 5.2 — UN run de CI sobre la combinación

```bash
cd "$WT"
git push -u origin "queue/integration-$TS"
```

El CI se dispara abriendo un **PR draft** `queue/integration-<ts>` → `<BASE_T>`
(`gh pr create --draft`): los repos del fleet ya traen `pull_request` cubriendo
sus bases (main/master y las release vía `release-*` o nombre explícito —
verificado 2026-08-17), así que el draft corre la matriz completa sin tocar
ningún workflow. Ese draft **jamás se mergea** y se cierra en 5.5. (Optimización
opcional por repo: trigger `push: queue/**` — evita el PR draft; si existe, el
push de arriba alcanza.)

La espera sigue el «Cierre asíncrono de CI» de [[merge-when-green]]: consultá
el run una vez (`gh run list --branch "queue/integration-$TS" --limit 1`); si
sigue en vuelo, montá el watcher `CI-MONITOR [<repo> integración@<sha7>]` con
`NEXT: verde ⇒ drenar (5.3) · rojo ⇒ bisect (5.4)` y pausa de tablero (en
`--all-repos`: mientras tanto, el tren de OTRO repo). Nunca un `--watch`
foreground de más de 600000 ms.

### 5.3 — Verde ⇒ drenar los PRs de corrido (sin re-CI por unidad)

La validez del atajo: el árbol final de la base tras drenar el grupo **es** el
árbol de la integración (mismas resoluciones — rerere las replaya — y mismo
orden), y ese árbol es exactamente lo que el CI validó. Ese run **es** la
validación del grupo: no hay una segunda verificación después. Los estados
intermedios (tras la unidad 1..k<N) no se testean y nadie los consume — el único
estado que importa es el final, ya cubierto. Precondición por repo (verificada en F2 del rollout): la base del tier sin
`required_status_checks` que exijan re-CI del head tras cada push.

Por cada PR del tren, en orden:

```bash
cd "$WT"; PR=<n>; RAMA="<head>"; BASE_T="<base del tier>"
BASE_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin "refs/heads/$BASE_T")"
HEAD_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin "refs/heads/$RAMA")"
BASE_SHA="${BASE_LINE%%[[:space:]]*}"; HEAD_SHA="${HEAD_LINE%%[[:space:]]*}"
echo "$BASE_SHA $HEAD_SHA" | grep -Eq '^[0-9a-fA-F]{40,64} [0-9a-fA-F]{40,64}$' \
  || { echo "tips remotos ilegibles"; exit 2; }
for TIP in "$BASE_SHA" "$HEAD_SHA"; do
  git cat-file -e "${TIP}^{commit}" 2>/dev/null \
    || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$TIP"
done
# GitHub recomputa mergeable tras cada squash: poll UNKNOWN → veredicto (c/5s máx 60s)
for i in $(seq 1 12); do
    ST="$(gh pr view "$PR" --json mergeable,mergeStateStatus -q '"\(.mergeable) \(.mergeStateStatus)"')"
    case "$ST" in "UNKNOWN"*) sleep 5 ;; *) break ;; esac
done
case "$ST" in
  MERGEABLE*)
    gh pr merge "$PR" --squash --delete-branch || echo "❌ #$PR rechazado — ver BLOCKED" ;;
  *DIRTY*|*CONFLICTING*)
    # El squash anterior lo dejó DIRTY (solapaba con lo ya drenado). Update en
    # DETACHED HEAD: la rama puede estar checkouteada en el worktree de su
    # dueña y un checkout normal fallaría. El merge desciende del head remoto
    # ⇒ push fast-forward normal, jamás force.
    git checkout --detach "$HEAD_SHA"
    git -c rerere.enabled=true -c rerere.autoupdate=true merge --no-edit "$BASE_SHA"    # replay sin mutar .git/config
    git push origin "HEAD:refs/heads/$RAMA"
    for i in $(seq 1 12); do
        M="$(gh pr view "$PR" --json mergeable -q .mergeable)"
        [ "$M" = "MERGEABLE" ] && break; sleep 5
    done
    # SIN espera de re-CI: la combinación ya está validada por el run del tren
    gh pr merge "$PR" --squash --delete-branch || echo "❌ #$PR sigue rechazado — failed:merge" ;;
  *BLOCKED*)
    echo "⏸️ #$PR BLOCKED (review/ruleset del repo) — failed:blocked; no se fuerza" ;;
esac
```

### 5.4 — Rojo ⇒ triage y bisect por mitades

Un rojo de la integración no dice qué unidad lo causó. Triage barato primero:
si los tests rojos mapean a archivos de UNA unidad (matriz de Phase 2) ⇒ es la
culpable — fix **delegado a su dueña** (o `/fix-broken-tests` inline tras
timeout, con la pausa por código de producción salvo `--autonomous`), y al
llegar el push se re-mergea esa unidad en la integración y se re-pushea (un
run nuevo). Si no es atribuible: **bisect por mitades** — rebuild de
`queue/integration-<ts>-b<k>` con la mitad de las unidades (1 run por paso,
~log2(N) pasos; con 7 unidades son 2-3 runs — igual más barato que 7 ciclos).
La(s) culpable(s) salen del tren (`failed:integracion-roja`, fix delegado) y el
resto se drena con 5.3.

### 5.5 — Cleanup del tren

```bash
cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
git push origin --delete "queue/integration-<ts>" 2>/dev/null || true
gh pr close <nº del draft de integración, si se usó> 2>/dev/null || true
git worktree remove --force "$HOME/webapps/.wt/$(basename "$PWD")/queue-<ts>" 2>/dev/null || true
```

La rama de integración **jamás se mergea** — es el banco de pruebas de la
combinación; lo que aterriza en la base son los squashes por unidad
(atribución intacta).

**Holds al final:** integrar + esperar CI + reportar veredicto, sin merge (⏸️).
**Tier 2 (release autorizada):** recién acá, con su tier 1 drenado (si quedan
PRs de sesión colgando de la release ⇒ `hold:tier1-pendiente` con la lista) —
flujo completo de [[merge-when-green]] con espera de CI real (el atajo
sin-re-CI NO aplica al tier 2) y consumo de `release_merge` (el `projects.yml`
del toolkit queda dirty y se ACUMULA para el cierre — no se commitea acá).

**Tablero de estado**: al inicio de cada sub-fase y en CADA pausa (conflicto en
resolución, delegación en vuelo, watcher montado, pausa de aprobación del fix
loop) — refrescá el tablero completo para que el operador vea dónde está cada
pieza sin preguntar.

## Delegación a la sesión dueña (contrato)

La dueña sale de la línea `Sesión:` del body del PR (fallback: matcheo por
tokens nombre-de-sesión ↔ nombre-de-rama vía ListAgents). Se delega: el
conflicto **semántico** de 5.1 y el fix de un rojo atribuible (5.4). Los
conflictos mecánicos de registros/generados los resuelve la queue inline — no
requieren contexto ajeno. (El aviso post-merge de Phase 6 usa esta misma
resolución de dueña pero **no** es una delegación: no pide trabajo ni espera
señal.)

**Qué se le pide exactamente:** la **Phase 4 de [[pr-green]]** sobre SU rama —
resolver el conflicto o el rojo en su worktree, commitear y **pushear al head del
PR**. Nada más: la dueña **no mergea** (el merge es de esta queue o del operador) ni
toca el clon principal.

1. `SendMessage` a la dueña con: rama y PR, el problema exacto (archivos y
   markers, o tests rojos con su output), qué se le pide (`/pr-green` — commit + push
   al head, sin merge), y el compromiso:
   *«la queue no toca tu head hasta las <T> o tu push — lo que llegue primero»*.
2. **La señal de resuelto es el push al head del PR** — no una respuesta:
   pollear `gh pr view <n> --json headRefOid` (c/60s, comparando contra el OID
   del momento de delegar).
3. Timeout **~15 min** sin push ⇒ la queue resuelve inline (comportamiento
   clásico) y lo anota (`resuelto-inline:timeout`). Si la dueña pushea DESPUÉS
   del timeout, su push se re-censa como unidad nueva — no se pisa.
4. Una delegación en vuelo NO frena el tren: se sigue con las unidades no
   afectadas y la delegada se re-toma al llegar su push.

## Phase 6 — Cierre

```bash
cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
REPO_NAME="$(basename "$PWD")"
# El clon principal es el árbol desplegado: esta fase sólo compara su HEAD con
# el SHA anunciado para branch: y deriva cualquier avance al deploy tipado.
DEPLOY="$(bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh" \
   --check "$REPO_NAME" 2>/dev/null | sed -n 's/^deploy_branch=//p')"
CUR="$(git rev-parse --abbrev-ref HEAD)"
DEPLOY_LINE="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code --refs origin "refs/heads/$DEPLOY" 2>/dev/null || true)"
DEPLOY_SHA="${DEPLOY_LINE%%[[:space:]]*}"
if echo "$DEPLOY_SHA" | grep -Eq '^[0-9a-fA-F]{40,64}$'; then
    git cat-file -e "${DEPLOY_SHA}^{commit}" 2>/dev/null \
      || GIT_TERMINAL_PROMPT=0 git fetch --no-auto-gc --no-tags --no-write-fetch-head --quiet origin "$DEPLOY_SHA"
    if [ "$(git rev-parse HEAD)" = "$DEPLOY_SHA" ]; then
        echo "✅ clon desplegado intacto y current: $CUR@$DEPLOY_SHA"
    else
        PENDING="$(git rev-list --count "HEAD..$DEPLOY_SHA" 2>/dev/null || echo '?')"
        echo "⚠️ clon desplegado intacto: deploy pendiente ($PENDING commit(s))"
        echo "   ejecutar manualmente: cd $PWD && bash $HOME/webapps/vps-ops-toolkit/scripts/deployment/deploy-project.sh --apply --project=$REPO_NAME $DEPLOY"
    fi
else
    echo "⚠️ clon desplegado intacto: deploy_branch/tip irresoluble ($CUR) — se reporta"
fi
echo "--- ramas obsoletas (se REPORTAN, jamás se borran: -D es del operador) ---"
git for-each-ref refs/heads --format='%(refname:short) %(upstream:track)'
echo "--- worktrees restantes (los queue-* de esta corrida ya se retiraron en 5.5) ---"
git worktree list
echo "--- CI de la base (INFORMATIVO: no se espera, no se vigila, no frena nada) ---"
DEFAULT="$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo master)"
gh run list --branch "$DEFAULT" --limit 3
rm -rf "/tmp/merge-queue-${REPO_NAME}"
```

### Integridad (eco) — informativo, NUNCA un gate

La queue mergeó trabajo de N sesiones sobre clones que además son árboles
deployados. Antes del tablero final, pedile su línea al motor `vps-integrity`.
**No condiciona el drenaje**: `drift>0` o críticos abiertos se REPORTAN, jamás
frenan un merge ni degradan una fila ya mergeada.

```bash
if [ -f "$HOME/webapps/vps-ops-toolkit/scripts/integrity/fleet-integrity-status.sh" ]; then bash "$HOME/webapps/vps-ops-toolkit/scripts/integrity/fleet-integrity-status.sh"; elif [ -x /usr/local/sbin/vps-integrity ]; then sudo -n /usr/local/sbin/vps-integrity status --line; else echo "ℹ️ vps-integrity no instalado — sin eco de integridad"; fi
```

La vista de fleet resuelve sola local vs `tailscale ssh`; su **exit 75** es la
pausa de auth de Tailscale, no un error: mostrale el link al operador y seguí.
Va como UNA línea bajo el tablero (`Integridad: drift=<n> · críticos=<n> · <VPS>`
o `Integridad: ⏭️ motor no instalado`), nunca como columna ni como veredicto.

Los **worktrees de sesión** cuyo PR quedó mergeado se reportan como **retirables**:
los retira la **sesión dueña** con `/all-in-base` al ver su PR ya mergeado
(`session-worktree.sh remove <slug>`, sin `--force`); los **huérfanos** los junta el
gc del operador
(`bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh" gc --apply`).
La queue sólo retira los `queue-*` propios.

**Cierre asíncrono** — regla completa en [[merge-when-green]] § «Cierre
asíncrono de CI»; instancia de esta skill, en este orden:

1. **Sweep primero** (TaskStop): sólo watchers `CI-MONITOR [...]` que ESTA
   sesión montó y quedaron obsoletos — PRs que este drenaje mergeó, o runs que
   UN `gh run view <id> --json status` confirme `completed` ANTES de matar.
   Nada sin el prefijo ni fuera del ledger de la sesión (un dev server de
   `dev-up` o una shell del operador NO se tocan; en duda, se reporta y no se
   mata). Fuente: el contexto propio, jamás `ps`.
2. **NO se monta watcher de base.** La base no se vigila: el `gh run list` de
   arriba es un eco informativo del bash, nada más — se imprime en el reporte y
   no gatea, no espera y no puede frenar el drenaje. La validación del grupo ya
   la pagó el run del tren (5.2) sobre exactamente el árbol que aterrizó, y cada
   PR llegó verde por su cuenta; un tercer veredicto sobre el mismo árbol no
   agrega información. Si ese eco muestra rojo, es material para el operador
   (Next steps), no una acción de la queue. El único watcher de esta skill es el
   de la integración (`[<repo> integración@…]`), montado y consumido en Phase 5.
3. El reporte final lista el **ledger**: `label → qué vigila → acción al
   resolver` (referencia para cada notificación entrante). Tras un drenaje
   normal el ledger queda vacío — el watcher de integración ya se consumió.

**Toolkit (recolector de `release_merge`):**
- En `--all-repos`: si `projects.yml` quedó dirty por consumos de autorizaciones,
  UN solo commit al final reusando por prosa las Phases T1–T2 de
  [[merge-when-green]] (green gate local + commit directo a master + push; T3
  propagación incluida).
- En modo default (cwd = repo de proyecto): **NO se commitea el toolkit** desde
  acá — se reporta pendiente con `/git-commit` en Next steps (espejo exacto del
  comportamiento de merge-when-green Path A).

**Aviso a las sesiones activas** (si el harness expone las tools; si no, se
omite entero y va a Next steps): llamá `ListAgents` **una vez** y mandá
`SendMessage`. **Un solo mensaje por sesión** — hay DOS formas y son excluyentes:
si una sesión es dueña de algo mergeado recibe la forma (a) y nunca las dos.

**(a) Sesión dueña de una rama mergeada** — la dueña sale de la línea `Sesión:`
del body del PR (misma resolución que la sección «Delegación»: `Sesión:` primero,
fallback `ListAgents` + solapamiento de tokens nombre-de-sesión ↔ nombre-de-rama):

> 🚂 merge-queue: tu trabajo ya está en `<base>`. Mergeadas: `<rama>` (PR #N,
> squash `<sha7>`)… **Tu worktree quedó retirable: corré `/all-in-base`** (lo retira
> al ver tu PR mergeado). **Verificalo vos y dame tu veredicto: corré
> `/all-in-base --check-only`.** Si seguís trabajando en este repo, `/git-sync`
> primero (la base se movió).

**(b) Sesión activa que no es dueña de nada mergeado** — informativo:

> 🚂 merge-queue: se drenó la cola de `<repo>` — mergeadas: `<rama1>`, `<rama2>`
> (…). La base `<default>` se movió: corré `/git-sync` antes de seguir
> trabajando. Ramas en hold/pausadas: `<lista o "ninguna">`.

**Reglas del aviso (a):**

- **Fire-and-forget: la queue NO espera el veredicto ni lo pollea.** El merge ya
  ocurrió — el aviso es cortesía y cierre de lazo, jamás un gate. Es la
  diferencia con la sección «Delegación», donde la señal SÍ se espera (push al
  head, timeout 15 min): ahí se pide trabajo, acá sólo se informa y se sugiere
  una verificación. No confundir los dos mecanismos.
- **El `--check-only` es obligatorio en el pedido.** Sin el flag, un veredicto NO
  hace que [[all-in-base]] delegue en [[pr-green]] (commit/push/PR/CI) — ya **no**
  mergea, pero igual se pondría a tocar git y a empujar commits en paralelo con esta
  queue, que puede seguir drenando otros repos/unidades. Con el flag responde SÍ/NO
  y no toca git.
- **Dueña declarada pero sin sesión viva** (no aparece en `ListAgents`) → no se
  manda nada, se anota `⚠️ sesión no alcanzable` en el Tablero y se sigue.
- **PR sin línea `Sesión:`** → `— (sin dueño)`, sin mensaje (el advisory para
  arreglarlo ya está en Next steps).
- **Harness sin `ListAgents`/`SendMessage`** → todo este bloque se omite, las
  filas quedan `n/a (harness sin SendMessage)` y el pedido baja a Next steps.

## Tablero de estado (en cada pausa y al final)

El operador tiene N sesiones paralelas y necesita ver de un vistazo dónde está
cada pieza de trabajo. **En CADA pausa del proceso** — espera de CI que supere
~1 min, montaje de un watcher, resolución de conflictos, pausa de aprobación,
unidad `deferred`/`paused` — y **SIEMPRE al final**, emití este tablero:

| Sesión | Unidad (rama) | PR | CI | Mergeable | Estado | Aviso | Próximo paso |
|---|---|---|---|---|---|---|---|

(+columna `Repo` primero en `--all-repos`.)

- **Sesión**: la línea `Sesión:` del body del PR (contrato del protocolo por
  sesión — fuente primaria). Fallback best-effort: `ListAgents` una vez y
  matcheo por solapamiento de tokens nombre-de-sesión ↔ nombre-de-rama. Sin
  dato → `— (sin dueño)` con ⚠️ advisory; unidades creadas por esta corrida →
  `esta`; releases → `operador (release)`.
- **Estado** (vocabulario fijo — incluye el "¿ya está en su base?" explícito):
  `en cola (#N)` · `integrando` · `en integración (CI combinado)` ·
  `👁️ watcher (<label>)` · `delegada a <sesión> (hasta <T>)` ·
  `resolviendo conflictos` · `deferred:delegada` · **`✅ en <base> (squash
  <sha7>)`** · `⏸️ hold release` · `⏸️ hold:tier1-pendiente` ·
  `⏸️ paused:tree-sucio` · `🧹 cleanup` · `⏭️ excluida:<razón>` ·
  `❌ failed:<razón>`.
- **Aviso** (vocabulario fijo — el aviso post-merge de Phase 6): `📨 notificada`
  (se le mandó el mensaje con el pedido de `/all-in-base --check-only`) ·
  `⚠️ sesión no alcanzable` (dueña declarada, sin sesión viva en `ListAgents`) ·
  `— (sin dueño)` (el PR no trae línea `Sesión:`) · `n/a (harness sin
  SendMessage)`. Hasta Phase 6 la columna va `—`: sólo se puebla al cerrar, y
  **nunca** condiciona el resultado de la fila (el merge ya ocurrió).
- **Próximo paso**: la acción concreta que destraba esa fila (o `—` si terminó).
- El tablero es ACUMULATIVO: cada emisión muestra TODAS las unidades del censo
  (las ya mergeadas quedan ✅ — el operador ve el progreso total, no un delta).
- **Al final**, el tablero completo ES la tabla del Output final (con la columna
  `Resultado` consolidada) — no se emite dos veces.

Puntos de emisión cableados: al cerrar Phase 3 (primera foto post-integración) ·
en Phase 4 antes del primer merge del batch y al degradar una unidad · en
Phase 5 al inicio de cada sub-fase y en cada pausa (conflicto, delegación en
vuelo, watcher del CI combinado, bisect) · en Phase 6 como reporte final.

## Safety rules

- **Nunca force push**, en ninguna variante — ni `--force`, ni `--force-with-lease`
  (los cubre el deny del fleet), ni el refspec `+` (sería evadir una policy que
  guarda contra accidentes). La alternativa SIEMPRE es `gh pr update-branch` o
  `git merge <sha-base>` en detached HEAD desde el worktree de la queue
  (push `HEAD:refs/heads/<rama>` fast-forward).
- **Nunca `git rebase` sobre una rama pusheada** (su push sería force). Rebase
  sólo sería aceptable en una rama local-only jamás pusheada — y aun ahí el
  merge es más simple y igual de válido con squash.
- **El clon principal jamás se toca**: ni checkout, ni pull, ni merge, ni stash
  en `~/webapps/<repo>` — toda mutación de tree ocurre en el worktree
  `~/webapps/.wt/<repo>/queue-<ts>` de la corrida. Phase 6 sólo sondea el SHA y
  deriva un avance pendiente a `deploy-project.sh` (manual, operación tipada).
- **La rama `queue/integration-*` jamás se mergea** — banco de pruebas de la
  combinación; se borra en 5.5 (remota + worktree). Sus restos huérfanos de
  corridas anteriores son cleanup, nunca unidades.
- **El atajo sin-re-CI es sólo del tier 1 validado por integración** — el tier
  2 (release→default) espera SIEMPRE su CI completo.
- **Nunca borrar ramas locales** (`-D` lo decide el operador; menú post-run con
  evidencia). Excepción documentada: el auto-delete REMOTO de
  `gh pr merge --delete-branch`, default heredado de merge-when-green.
- **El merge de una release lo decide sólo `release_merge:`** en projects.yml.
  Esta skill jamás lo ofrece, jamás lo asume, y consume la autorización
  (one-shot) tras el merge.
- **Nunca checkout con tree sucio, nunca stash automático** — el tree puede ser
  de otra sesión. La unidad se pausa y el tren sigue.
- **Conflictos nunca a ciegas** — mostrar ambos lados; si es complejo, frenar y
  preguntar (reglas de git-sync Phase 6).
- **Ningún fallo individual corta la cola** (política Path C): cada unidad
  termina en ✅/⏸️/⏭️/❌ con su razón, y se sigue.
- **El lock es advisory**: protege del doble-merge-queue accidental, NO de un
  `/merge-when-green` suelto en otra sesión. La mitigación real es de uso: al
  drenar multi-rama se usa esta skill EN VEZ de merge-when-green por sesión —
  para eso existe.
- **TaskStop sólo sobre watchers `CI-MONITOR` propios y obsoletos** — jamás una
  shell de fondo desconocida (puede ser un dev server u otra sesión). En duda:
  reportar, no matar. El único watcher que esta skill monta es el de la
  integración (5.2); **no monta watcher de la base** ni espera su CI.
- **El aviso post-merge nunca frena nada** — es fire-and-forget: si la sesión
  dueña no está, no responde o el harness no expone `SendMessage`, se anota en
  la columna `Aviso` y se sigue. El merge ya está hecho; el aviso no es un gate.
- **Nunca en cron/headless**; la tabla del plan siempre se muestra antes de
  ejecutar, con o sin flags.

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos (reglas
de gating de [[_output-protocol]] §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| Ejecutar el tren pendiente | si corrió `--batch-only`/`--plan-only` o quedaron unidades pausadas | `/merge-queue` |
| Borrar ramas ya-en-base (lote con evidencia) | `-D` SÓLO las listadas arriba como ya-en-base/gone-limpia — el trabajo está verificado en la base | `git branch -D <r1> <r2>` |
| Ver un PR puntual | review manual en el browser | `gh pr view <n> --web` |
| Re-censo | refrescar el estado tras cambios externos | `/merge-queue --plan-only` |

NUNCA ofrecer `--autonomous` (se tipea) ni el merge de una release (lo decide
`release_merge:` en projects.yml).

## Output final

Reportar siguiendo [[_output-protocol]].

```markdown
🟢 merge-queue OK — cola drenada
(🟡 si quedaron holds/paused/excluidas · 🔴 si hubo failed · ⏸️ si TODO quedó en
hold de release · ⏭️ si la cola estaba vacía — nada que drenar)

### Resumen ejecutivo
mergeadas: N (batch B + tren T) · holds: N · paused: N · cleanup: N · excluidas: N · failed: N

La tabla final es el **Tablero de estado** completo (todas las unidades del
censo, con `Resultado` consolidado — el "¿ya está en main?" de cada una):

| # | Sesión | Unidad | PR | CI | Resultado | Aviso |
|---|---|---|---|---|---|---|
| 1 | folder-counters | fix/15082026-… | #186 | ✅ | ✅ en main (batch, squash a1b2c3d) | 📨 notificada |
| 2 | emails-module | feat/16082026-… | #187 | ✅ integración | ✅ en main (tren, squash e4f5a6b) | 📨 notificada |
| 3 | docs-module | feat/16082026-… | #188 | ✅ integración | ✅ en july-release (tier 1, squash 9c8d7e6) | ⚠️ sesión no alcanzable |
| 4 | group-header | feat/16082026-… | #189 | 🔴 integración | ❌ failed:integracion-roja — fix delegado a group-header | — |
| 5 | operador (release) | july-release (autorizada) | #52 | ✅ | ✅ en master — tier 1 drenado, release_merge consumida | — |
| 6 | operador (release) | release-y (sin autorizar) | #9 | ✅ | ⏸️ hold — release sin release_merge | — |
| 7 | — (sin dueño) | feat/vieja | — | — | 🧹 ya-en-base (cleanup) | — (sin dueño) |
| 8 | — | fix/rara | #190 | — | ⏭️ excluida:base-rara | — |

CI de la base (informativo, no gatea): `<último run de <default>>`
```

En `--all-repos`: columna `Repo` primero; >15 filas ⇒ anteponer
`### Top 3 acciones prioritarias`.

`## Next steps` — sólo lo accionable, con el comando exacto:
- `failed:*` → el comando del próximo intento (`gh run view <id> --log-failed`, …).
- Holds listos para lanzar → «setear `release_merge: <rama>` al proyecto en
  projects.yml (vps-ops-toolkit) y correr `/merge-when-green`».
- `paused:tree-sucio` → «cerrá/commiteá la sesión dueña del tree y re-invocá
  `/merge-queue`».
- Toolkit pendiente (consumo de `release_merge` en modo default) → `/git-commit`
  en vps-ops-toolkit.
- `excluida:base-rara` → `gh pr edit <n> --base <base-correcta>` (la release en
  repos participantes, la default en prod-directos) y re-censar.
- `failed:integracion-roja` / `deferred:delegada` → el estado de la delegación
  (dueña, deadline) + el comando de re-entrada: `/merge-queue` re-censa y
  re-integra al llegar el push.
- PRs sin `Sesión:` en el body → pedirle a cada sesión que lo agregue
  (`gh pr edit <n> --body ...`) — sin dueño declarado la delegación degrada a
  heurística.
- `excluida:diverged` → reconciliar a mano (el force push está denegado; mirá
  `git log --oneline <rama>...<sha-remoto>` del censo).
- (manual) `git branch -D <ramas ya-en-base>` — borrado a decisión del operador.
- Si no se pudo avisar a las sesiones (harness sin ListAgents/SendMessage, o
  filas `⚠️ sesión no alcanzable`) → «en cada sesión dueña de este repo:
  `/all-in-base --check-only` para su visto bueno, y `/git-sync` antes de seguir
  trabajando».
- Monitores en vuelo → una fila del ledger por watcher (`label → qué vigila →
  acción al resolver`) + respaldo manual `gh run watch <id> -R <repo>` por si la
  sesión se cierra antes de la notificación. Tras un drenaje normal no queda
  ninguno: el watcher de integración se consumió en Phase 5 y la base no se
  vigila. (Con `--plan-only` tampoco: no se ejecutó nada.)
- Si el eco informativo del CI de la base salió rojo → es material del operador,
  no de la queue: `gh run view <id> --log-failed` y fix hacia adelante. El
  drenaje no se revierte.
