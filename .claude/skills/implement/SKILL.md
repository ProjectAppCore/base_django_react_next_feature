---
name: implement
description: "Implementation workflow — systematic code protocol with dependency analysis, step-by-step changes, and testing. Use when the user asks to build, code, or implement a feature or fix."
argument-hint: "[description of what to implement]"
---

Before starting, ALWAYS do 2 things:
a. Read and understand the documentation in `docs/` and `tasks/`
b. Get required code context from `backend/` and `frontend/` — o el layout que
   exista en el repo (ver [[methodology-setup]])

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): con `$ARGUMENTS` o intención clara en la sesión → ejecutar directo, PROHIBIDO preguntar el tema (un dato menor faltante se marca en el texto, no se convierte en pregunta). Sin argumentos ni contexto → UNA sola pregunta corta en texto por la tarea a implementar (no picker: el insumo es libre). Nunca en modo fleet/headless/cron.

Sin picker por diseño: no hay flags de modo — el argumento es la feature o el fix a implementar.

---

## Paso 0 — Worktree de sesión (obligatorio antes de escribir, en CUALQUIER repo)

`git rev-parse --show-toplevel` debe caer bajo `~/webapps/.wt/`; si cae en el
clon principal, creá tu worktree ANTES de tocar nada — `bash
$HOME/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh create
<prefijo> <slug>` (o la receta manual del tmpl §5) — y entrá: Claude Code
`EnterWorktree path=~/webapps/.wt/<repo>/<slug>`, Codex `cd`. Si la sesión YA
tiene su worktree de un turno anterior, seguí usándolo. Esto NO depende de si
el repo está en `projects.yml`: el guard del hook es por path del clon, no por
registro.

## Preflight (obligatorio)

Si el repo actual es un proyecto del fleet (aparece en
`~/webapps/vps-ops-toolkit/projects.yml`), ANTES de escribir:

```bash
bash ~/webapps/vps-ops-toolkit/scripts/maintenance/resolve-work-coordinate.sh --check <proyecto>
```

Si ya estás DENTRO de tu worktree (Claude, tras `EnterWorktree`), el mismo dato —más
la rama, la base del PR y el estado del CI— sale de un comando que además resuelve el
proyecto solo. Adentro de un worktree nativo Claude rechaza el comando con `$(...)`,
`{a,b}`, `for`/`while` o heredoc con sustitución, y el que apunta al clon compartido:
**un comando simple por llamada**, y los valores se escriben **literales** en la
siguiente (convención: `git-branch-protocol` §1 del CLAUDE.md del repo).

```bash
bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh status
```

- `resolved_branch` es la **BASE** del trabajo, no la rama donde se commitea:
  commitear SIEMPRE en TU rama de sesión (worktree propio, PR al primer push con
  base=`resolved_branch`) — nunca directo sobre la release ni sobre main/master,
  nunca en la rama de otra sesión (git-branch-protocol del CLAUDE.md del repo).
- `host_status=wrong-host` → **STOP**: el trabajo de este proyecto vive en el
  clon de `vps_work`, no en este host.

---

# Implementation Workflow

## Programming Principles

- **Algorithm efficiency**: Use the most efficient algorithms and data structures
- **Modularity**: Write modular code, break complex logic into smaller atomic parts
- **File management**: Break long files into smaller, more manageable files
- **Import statements**: Prefer importing functions from other files instead of modifying them directly
- **Reuse**: Prefer to reuse existing code instead of writing from scratch
- **Code preservation**: Don't modify working components without necessity
- **Systematic sequence**: Complete one step completely before starting another
- **Design patterns**: Apply appropriate patterns for maintainability and scalability
- **Proactive testing**: Functionality code should be accompanied with proper tests

## Systematic Code Protocol

### Step 1: Analyze Code

**Dependency Analysis:**
- Which components will be affected?
- What dependencies exist?
- Is this local or does it affect core logic?
- What cascading effects will this change have?

**Flow Analysis:**
- Conduct complete end-to-end flow analysis from entry point to execution of all affected code.
- Track data and logic flow throughout all components.
- Document dependencies thoroughly.

### Step 2: Plan Code

- Outline a detailed plan including component dependencies and architectural considerations.
- Provide a proposal specifying: (1) what files/functions/lines are changed; (2) why; (3) impacted modules; (4) potential side effects; (5) trade-offs.

### Step 3: Make Changes

1. Document current state in the memory files — los 7 canónicos de
   [[methodology-setup]]; `tasks/active_context.md` siempre
2. Plan single logical change at a time:
   - One logical feature at a time
   - Fully resolve by accommodating changes in other parts
   - Adjust all existing dependencies
   - Ensure new code integrates with existing architecture
3. Simulation testing: simulate user interactions, dry runs, trace calls before applying
4. If simulation passes, do the actual implementation

### Step 4: Test

- Slice mínimo de verificación: el/los tests del comportamiento tocado (crear
  o correr sólo esos, en archivos separados) + confirmar que la regresión
  inmediata no se rompe.
- La cobertura completa (edge cases, casos negativos, gate) la cierra [[qa]]
  en el Cierre — no dupliques su trabajo acá.

### Step 5: Loop Steps 1-4

Incorporate all changes systematically, one by one. Verify and test each.

### Step 6: Optimize

Optimize the implemented code after all changes are tested and verified — la forma
canónica es delegar en [[perf-pass]] **modo A** (requerimiento = lo implementado): declara el
perfil de cómputo del host real, contrasta el camino de código nuevo contra
`docs/PERFORMANCE_STANDARDS.md` y aplica cambios acotados en el MISMO worktree de la sesión
(commit propio), dejando el guion `brief-perf` para `/qa`. Se sugiere siempre que el cambio
agregó vistas, listados, serializers, tareas o páginas; sin camino de datos nuevo se declara
`⏭️` en el cierre. Nunca se optimiza "a ojo" ni se toca la infra.

---

After every implementation, ALWAYS do these things (c. sólo aplica con mapa de vistas):
a. Update other possibly affected codes in `backend/` and `frontend/`
b. Update the memory files afectados por el cambio — los 7 canónicos de
   [[methodology-setup]]: `docs/methodology/product_requirement_docs.md`,
   `docs/methodology/technical.md`, `docs/methodology/architecture.md`,
   `docs/methodology/error-documentation.md`,
   `docs/methodology/lessons-learned.md`, `tasks/tasks_plan.md` y
   `tasks/active_context.md` (este último siempre)
c. Mapa de vistas — sólo si el repo tiene `frontend/config/viewCatalog.js` y la
   skill [[view-map-update]] está instalada para este runtime (Claude:
   `.claude/skills/view-map-update/`; Codex: `.agents/skills/view-map-update/`);
   si no, saltear (fila `⏭️`). Correrla con `--apply --diff` en el worktree de
   la sesión: nunca pregunta (la invoca este conductor, regla 4 de
   [[_output-protocol]] §4) y no commitea — sus cambios viajan en el commit de
   la sesión. Si la sesión ya la corrió sobre este mismo diff, citar ese
   resultado en vez de repetirla.

---

## Cierre — QA de lo implementado

Al terminar la implementación (feature funcionalmente completa), la forma
canónica de cerrar la cobertura es invocar **[[qa]]** — precedido por [[perf-pass]] (modo A,
aplica en el mismo worktree) cuando el cambio tocó listados, queries, serializers, tareas o
bundles; `/qa` absorbe el guion `brief-perf` — : audita el flow-map,
escribe los tests faltantes al DoD de 3 puntos (casos negativos incluidos),
corre el gate y purga junk — sin mergear. Sugerilo siempre en el cierre. La
sesión termina con PR abierto + CI verde (`/pr-green`); el merge NO es de
esta sesión.

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y sin flags explícitos (reglas de
gating de [[_output-protocol]] §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| /qa (Recommended) | dry-run, no mergea; cierra la cobertura de lo implementado | `/qa` |
| /perf-pass | modo A, antes de /qa cuando el cambio agregó listados, queries, serializers, tareas o páginas: presupuestos contra el host real y fixes acotados en el mismo worktree (commit propio) | `/perf-pass <requerimiento>` |
| /git-commit | commit + push + PR (primer push) desde el worktree | `/git-commit` |
| /pr-green | dejar el PR en verde, sin merge | `/pr-green` |

**NUNCA** ofrecer `/deploy-and-check` (manual-only por política — sólo como
texto en `## Next steps` si aplica).

## Output final

Reportar siguiendo [[_output-protocol]]. Plantilla específica de `/implement`:

```markdown
🟢 implement OK — <qué se implementó>
✨ Todo en orden — no hay acciones pendientes.

| Dimensión | Estado | Detalle |
|---|---|---|
| Análisis de dependencias | ✅ | componentes afectados + flujo end-to-end trazado |
| Plan | ✅ | archivos/funciones, side effects y trade-offs definidos |
| Cambios | ✅ | cambio mínimo coherente, integrado con la arquitectura |
| Tests | ✅ | cobertura para lo nuevo + regresión existente preservada |
| Verificación | ✅ | slice mínimo de verificación corrió y pasó |
| Docs/memory | ✅ | docs/ y tasks/ actualizados si el cambio lo exige |
| Mapa de vistas | ✅ | view-map-update --apply --diff al día (⏭️ si el repo no tiene mapa) |
```

Si un test falla, la verificación no pasa, o queda algo sin verificar,
reemplazar el ✅ correspondiente por ⚠️ o ❌, omitir la línea ✨ y agregar
`## Next steps` con el comando exacto de verificación pendiente
(p.ej. `<venv>/bin/python manage.py test <app>` o `npx playwright test <spec>`)
y lo que no se pudo confirmar.
