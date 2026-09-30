---
name: skills-help
description: "Catálogo de skills en tablas por categoría con ámbito de ejecución (repo/host/fleet/VPS-only/dev/buzones), modo default (check vs mutante), argumentos y alcance en una frase. Default: skills propias de .claude/skills. Con --all agrega plugins/globales. Respeta una lista de exclusión editable (ignore.txt). Acepta un término de filtro."
allowed-tools: Bash, Read, AskUserQuestion
argument-hint: "[--all] [filtro]"
---

# Skills Help — catálogo de skills

¿No te acordás qué skills tenés o para qué sirve cada una? Esta skill escanea las
skills del proyecto y las lista en una **tabla** con un alcance **breve** (una
frase) por cada una. Es dinámica: lee el frontmatter en vivo, así las skills
nuevas aparecen solas y ninguna queda hardcodeada/obsoleta.

> **⚠️ How to invoke**:
> - `/skills-help` → tabla de las skills del proyecto (`.claude/skills/`).
> - `/skills-help --all` → además, plugins/globales y comandos built-in.
> - `/skills-help test` → solo las skills cuyo nombre/descripción matchee "test".
> - `/skills-help --all coverage` → combinable: `--all` + filtro.
>
> Claude Code substituye `$ARGUMENTS` con los flags/términos pasados (vacío si se omiten).

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): (1) flags explícitos → directo, sin menú; (2) intención clara → proponer el comando en una línea; (3) sin args → UNA AskUserQuestion; (4) nunca en fleet/headless/cron.

Sin picker por diseño: los flags son filtros aditivos de un catálogo read-only; se tipean (--all, término de filtro).

---

## Phase 0 — Discovery

```bash
set -o pipefail
ARGS="$ARGUMENTS"
PROJECT_DIR=$(pwd)
SKILLS_DIR="$PROJECT_DIR/.claude/skills"
IGNORE_FILE="$SKILLS_DIR/skills-help/ignore.txt"

# Flag --all y término de filtro (lo que quede tras quitar los flags conocidos).
ALL=false
case "$ARGS" in *--all*) ALL=true;; esac
FILTER=$(printf '%s\n' "$ARGS" | sed -E 's/--all//g; s/^[[:space:]]+//; s/[[:space:]]+$//')

[ -d "$SKILLS_DIR" ] || { echo "❌ No encuentro $SKILLS_DIR — ¿estás en la raíz del repo?"; exit 1; }

echo "✅ Discovery OK:"
echo "  SKILLS_DIR: $SKILLS_DIR"
echo "  --all:      $ALL"
echo "  filtro:     ${FILTER:-<ninguno>}"
echo "  ignore:     $([ -f "$IGNORE_FILE" ] && echo "$IGNORE_FILE" || echo "<ausente>")"
```

---

## Phase 1 — Scan skills del proyecto + lista de exclusión

Por cada `.claude/skills/<name>/SKILL.md`: extrae `name`, `description` y si es
slash-only (`disable-model-invocation: true`). Salta las ignoradas y, si hay
filtro, las que no matcheen. Emite filas crudas `name \t slash \t description`
para que Claude las renderice en Phase 3.

```bash
# --- Cargar lista de exclusión: ignores implícitos + ignore.txt del usuario ---
# Implícitos: _output-protocol (no invocable). El usuario agrega más en ignore.txt.
IGNORED=$'\n_output-protocol\n'
if [ -f "$IGNORE_FILE" ]; then
  # una skill por línea; '#' = comentario; se ignoran líneas vacías.
  while IFS= read -r line; do
    line="${line%%#*}"; line="$(printf '%s' "$line" | tr -d '[:space:]')"
    [ -n "$line" ] && IGNORED="$IGNORED$line"$'\n'
  done < "$IGNORE_FILE"
fi
is_ignored() { printf '%s' "$IGNORED" | grep -qxF "$1"; }

# --- Overrides estáticos (ámbito/modo NO derivables del frontmatter; EDITAR ACÁ) ---
# Ámbito: 🏠 repo cwd · 🖥️ este host · 🌐 fleet · 🔧 VPS-only · 💻 dev-only · ✉️ buzones
scope_override() {
  case "$1" in
    all-projects|incident)                                        echo "🌐" ;;
    full-audit|server-diagnostic|git-status-report|vps-cleanup)   echo "🖥️🌐" ;;
    tailscale-connect|init-fleet|bootstrap-ssh-fleet|bootstrap-tailscale-fleet|sync-ai-ecosystems) echo "🖥️" ;;
    migrate-project)                                              echo "🔧🌐" ;;
    mailbox-maintenance)                                          echo "✉️" ;;
    dev-up|dev-down)                                              echo "💻" ;;
    human|where-are-we)                                           echo "—" ;;
    *)                                                            echo "" ;;   # derivar
  esac
}
# Modo default: ✎ = muta de entrada. Todo lo demás deriva a ✓ (check/read-only).
mode_override() {
  case "$1" in
    git-commit|git-sync|merge-when-green|pr-green|merge-queue|all-projects|integrate-new-project|deploy-and-check|dev-up|dev-down|tailscale-connect|client-report|migrate-project) echo "✎" ;;
    *) echo "✓" ;;
  esac
}

# --- Extraer frontmatter + derivar ámbito/args de cada skill ---
RAW=""; n_listed=0; n_ignored=0
for f in "$SKILLS_DIR"/*/SKILL.md; do
  [ -f "$f" ] || continue
  fm=$(awk 'NR==1&&/^---/{f=1;next} /^---/{if(f)exit} f' "$f")
  name=$(printf '%s\n' "$fm" | sed -n 's/^name:[[:space:]]*//p' | head -1 | tr -d '"')
  [ -z "$name" ] && name=$(basename "$(dirname "$f")")
  desc=$(printf '%s\n' "$fm" | sed -n 's/^description:[[:space:]]*//p' | head -1 | sed 's/^"//; s/"[[:space:]]*$//')
  hint=$(printf '%s\n' "$fm" | sed -n 's/^argument-hint:[[:space:]]*//p' | head -1 | sed 's/^"//; s/"[[:space:]]*$//')
  tools=$(printf '%s\n' "$fm" | sed -n 's/^allowed-tools:[[:space:]]*//p' | head -1)
  slash=""; printf '%s\n' "$fm" | grep -qiE '^disable-model-invocation:[[:space:]]*true' && slash="⚡"

  # Ámbito: override estático → si vacío, derivar del hint/cuerpo.
  badges="$(scope_override "$name")"
  if [ -z "$badges" ]; then
    badges="🏠"
    # skills-help: su --all = plugins/globales, NO fleet (falso positivo conocido).
    if [ "$name" != "skills-help" ]; then
      printf '%s' "$hint" | grep -q -- '--all-repos' && badges="${badges}🖥️"
      printf '%s' "$hint" | grep -qE -- '--all-vps|--all \(todos los VPS' && badges="${badges}🌐"
    fi
  fi
  # VPS-only: el guard canónico anti-dev-machine (patrón preciso). Saltar a
  # skills-help misma: el patrón vive en ESTE código y se auto-matchearía.
  if [ "$name" != "skills-help" ]; then
    grep -q '/home/dev-env/webapps' "$f" 2>/dev/null && badges="${badges}🔧"
  fi
  # Buzones: tools MCP de mail.
  printf '%s' "$tools" | grep -qE 'mcp__(imap|claude_ai_Gmail)' && badges="${badges}✉️"

  mode="$(mode_override "$name")"

  if is_ignored "$name"; then n_ignored=$((n_ignored+1)); continue; fi
  # Filtro (case-insensitive sobre nombre+descripción)
  if [ -n "$FILTER" ]; then
    printf '%s %s' "$name" "$desc" | grep -qiF "$FILTER" || continue
  fi
  RAW="$RAW$name"$'\t'"$slash"$'\t'"$badges"$'\t'"$mode"$'\t'"$hint"$'\t'"$desc"$'\n'
  n_listed=$((n_listed+1))
done

echo "=== SKILLS_PROYECTO (name <TAB> slash <TAB> ambito <TAB> modo <TAB> args <TAB> description) ==="
printf '%s' "$RAW" | sort -f
echo "=== /SKILLS_PROYECTO  (listadas=$n_listed, ignoradas=$n_ignored) ==="

[ -f "$IGNORE_FILE" ] || cat <<EOF

ℹ️  No existe lista de exclusión. Para ocultar skills del listado, creá:
    $IGNORE_FILE
    (una skill por línea; '#' para comentarios)
EOF
```

---

## Phase 2 — (solo con `--all`) plugins / globales

Best-effort: cuenta skills de plugins en disco. La lista limpia y deduplicada la
completa Claude desde las skills disponibles de la sesión (Phase 3).

```bash
if [ "$ALL" = true ]; then
  echo "=== PLUGINS_DISCO (best-effort, puede haber duplicados por versión) ==="
  # dedupe por nombre de carpeta de skill
  find "$HOME/.claude/plugins" -path '*/skills/*/SKILL.md' 2>/dev/null \
    | awk -F/ '{print $(NF-1)}' | sort -u | sed 's/^/  - /'
  echo "=== /PLUGINS_DISCO ==="
  echo "ℹ️  --all activo: Claude debe COMPLETAR esta sección con las skills de"
  echo "    plugins (superpowers:*, code-review, frontend-design, deep-research, …)"
  echo "    y comandos built-in (/loop, /verify, /run, /schedule, …) que conoce de"
  echo "    la lista de skills disponibles de la sesión, respetando el ignore.txt."
fi
```

---

## Phase 3 — Render (tabla)

Con los datos crudos de Phase 1 (y Phase 2 si `--all`), Claude arma la salida:

1. **Agrupar** las skills en categorías legibles (no hay campo de categoría —
   agrupá por propósito). Buckets canónicos — **un bucket vacío NO se imprime**
   (cubren tanto repos de proyecto como el toolkit):
   - **Mejora transversal** (improvement-pass, security-pass, maintainability-pass, observability-pass, perf-pass, responsive-pass, vuln-audit)
   - **QA & tests** (qa, test-audit, test-quality-gate, coverage ×3, e2e-user-flows-check, fix-broken-tests, new-feature-checklist, playwright-validation, fake-data-refresh)
   - **Git & fleet** (git-sync, git-commit, git-status-report, merge-when-green, pr-green, merge-queue, all-in-base, all-projects, full-audit, deploy-and-check)
   - **Bootstrap & conectividad** (init-fleet, bootstrap-ssh-fleet, bootstrap-tailscale-fleet, tailscale-connect, sync-ai-ecosystems)
   - **Servidores & incidentes** (server-diagnostic, incident, migrate-project, integrate-new-project, vps-cleanup)
   - **Entorno & dev local** (dev-up, dev-down, methodology-setup)
   - **Planning & desarrollo** (plan, plan-task, implement, debug, debugme)
   - **Contenido & reportes** (client-report, user-walkthrough, human, where-are-we, repo-cleanup, skills-audit, skills-help)
   - **Buzones** (mailbox-maintenance)
   - **Otras** (cualquiera que no encaje — nunca dejes una skill afuera)
2. Una **tabla por categoría** con 4 columnas: `| Skill | Ámbito | Args | Alcance |`
   - `Skill`: ``/nombre`` (con backticks).
   - `Ámbito`: los badges derivados en Phase 1 (`🏠🖥️🌐🔧💻✉️` + modo `✓`/`✎` +
     `⚡` si slash-only), concatenados sin espacios.
   - `Args`: los flags del `argument-hint` **compactados** (sólo flags, sin las
     aclaraciones entre paréntesis), ≤40 chars. Si el hint compactado excede 40:
     poné `(ver ↓)` y agregá una **fila de continuación** debajo —
     `| ↳ | | | <argument-hint completo> |`. Sin `argument-hint` → `—`.
   - `Alcance`: **una frase, ≤48 chars** resumida de la descripción.
3. Si `--all`: sección extra **"Plugins / globales"** con esas skills (de Phase 2 +
   contexto de sesión), mismo formato.
4. **Leyenda ÚNICA al final** (nunca por tabla):
   `Ámbito: 🏠 repo · 🖥️ este host (--all-repos) · 🌐 fleet (--all-vps) · 🔧 VPS-only · 💻 dev-only · ✉️ buzones — Modo: ✓ check/dry-run default · ✎ muta de entrada · ⚡ solo slash`.
5. **Pie**: `N skills listadas · M ignoradas` y, si aplica, cómo editar la lista de
   exclusión (`$IGNORE_FILE`). Si no existe el ignore.txt, repetí el hint para crearlo.

> Las **celdas de las tablas-catálogo NO llevan emoji de estado** (✅/⚠️/❌) — es
> un catálogo, no un reporte de salud. Aun así, la skill cierra con el veredicto
> de una línea del protocolo (ver "Output final").

---

## Output final

Reportar siguiendo [[_output-protocol]]. Skill informativa: la salida principal
son las tablas-catálogo de Phase 3 (sus celdas no llevan emoji de estado). Cerrar
con el veredicto de una línea, derivado del scan:

- `🟢 skills-help OK` — discovery + scan + render completaron; catálogo emitido.
- `⏭️ skills-help — N/A o saltado` — filtro sin matches (0 skills listadas).
- `🔴 skills-help — 1 error, revisar arriba` — discovery falló (no existe
  `.claude/skills/`, exit 1); sin catálogo.

Tabla de dimensiones del scan (complementa las tablas-catálogo, no las reemplaza):

| Dimensión | Estado | Detalle |
|---|---|---|
| Discovery (`.claude/skills/`) | ✅/❌ | dir hallado; `--all=<bool>`, filtro=`<val>` |
| Scan proyecto | ✅ | N skills listadas · M ignoradas |
| Plugins / globales (`--all`) | ✅/⏭️ | listados si `--all`; ⏭️ si no se pasó |
| Render tablas-catálogo | ✅ | K categorías |

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos (gating
de [[_output-protocol]] §4), ofrecer vía AskUserQuestion:

| Opción (label) | description | preview |
|---|---|---|
| Ver plugins/globales (Recommended) | agrega superpowers, built-ins y skills de plugins | `/skills-help --all` |
| Filtrar por término | re-render sólo con las que matcheen | `/skills-help <término>` |
| Ocultar skills del catálogo | crear/editar la lista de exclusión local | `edit .claude/skills/skills-help/ignore.txt` |

## Next steps
- `/skills-help --all` — agregar plugins/globales y comandos built-in
- `/skills-help <término>` — filtrar el catálogo por nombre/descripción
- (manual, operador) editar `.claude/skills/skills-help/ignore.txt` para ocultar skills

---

## Notas

- **Dinámica**: lee el frontmatter en vivo; skills nuevas aparecen automáticamente.
- **Lista de exclusión** editable por el usuario en `.claude/skills/skills-help/ignore.txt`
  (una skill por línea, `#` para comentarios). `_output-protocol` se ignora siempre.
- El `ignore.txt` es **local del proyecto** y NO forma parte del baseline del fleet,
  así que el sync de skills nunca lo pisa.
- `--all` agrega plugins/globales (best-effort en disco + contexto de sesión).
- Funciona en cualquier proyecto del fleet (solo necesita `.claude/skills/`).

---

## Notas de fleet

- Fuente canónica: `vps-ops-toolkit/workflows/.claude/skills-help.md`. La versión
  en `.agents/skills/` es la copia generada para Codex.
- El `ignore.txt` NO se distribuye por el sync (no está en el baseline): es por-proyecto.
