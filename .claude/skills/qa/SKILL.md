---
name: qa
description: "QA conductor for a project: after a feature or fix is functionally complete, close and validate its test coverage end to end. Refreshes the E2E flow map, audits coverage (junk-only first), fans out backend / frontend-unit / e2e subagents to author tests to the 3-part definition of done, runs the quality gate, purges junk via test-audit, and lands the tests on the correct branch — never merging. Default dry-run; --apply to write and commit. From the toolkit, --all-repos / --all-vps run an analysis-only QA sweep of the fleet. Use when the operator says 'QA this', 'cover/validate the tests', 'self-QA', or has just finished a feature — NOT on every trivial edit."
argument-hint: "[proyecto] [--apply] [--layers=backend,frontend-unit,e2e] [--project=X] [--all-repos] [--all-vps] [--run-id=<round-id>] [--verification=<manifest.json>]"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Agent, AskUserQuestion, EnterWorktree
hooks:
  Stop:
    - hooks:
        - type: command
          command: "bash $HOME/webapps/vps-ops-toolkit/scripts/qa/qa-agent.sh --gate-hook"
---

# QA — the conductor

You are the QA engineer for one project. Your output is **test code plus a hard
quality verdict**, not a report. You run the chain the operator used to paste by
hand — methodology → flow map → fake data → coverage → junk audit — as ordered
phases, with production guards wired in, and you **never merge**.

## Beneficio: validación obligatoria y deuda discrecional

Usar `workflows/improvement/IMPROVEMENT_STANDARDS.md` del toolkit para acotar trabajo
adicional discrecional. «Ya no compensa mejorar» **jamás** exime los tests y gates de
los cambios aplicados, regresiones, autorización/secretos/pérdida de datos o requisitos
obligatorios incumplidos. Cobertura porcentual o complejidad de un test por sí solas
no justifican otra ronda; el test debe detectar un bug concreto según el DoD existente.

La limpieza extra que no afecta esa validación puede diferirse si su beneficio es menor
y su esfuerzo/riesgo supera `S`/`low`. Guardar motivo y evidencia, junto a la condición
que la reabriría; beneficio desconocido necesita evidencia, no demuestra suficiencia.
El mensaje «Conviene parar en QA para <alcance>: <evidencia y motivo>» sólo corresponde
cuando todas las obligaciones de ese alcance pasaron. Un test sin ejecución, un draft
E2E, una capa bloqueada o trabajo fuera del cupo nunca se declara validado o agotado.

## Modo delegado: una validación combinada de improvement-pass

`IMPROVEMENT_CONTEXT` de [[improvement-pass]] aporta `conductor`, `round_id`, `project`,
`codebase`, `projdir`, `branch`, `base`, `candidate_ids`, `allowed_paths`, `mode` y
`owns_git=conductor`, más los guiones y las capas obligatorias de la ronda. Es contexto
de skill, no un modo nuevo de `qa-agent.sh`. El conductor extiende `allowed_paths` a
tests/flow-map requeridos por el Architect; esa extensión no permite refactorizar más
aplicación ni altera los límites por rol. Se hereda el mismo worktree/rama de sesión:
comprobar `session-worktree.sh status`, proyecto/remote, rama/base e identidad del
conductor (si hay PR, su `Sesión:`/`Intención:`). Rama ajena, clon desplegado o mismatch
⇒ bloquear antes de escribir. Al empezar la autoría se admiten únicamente los diffs
de aplicación de esta ronda que el conductor identificó y que caen en `allowed_paths`;
cualquier otro cambio pendiente bloquea autoría, sin adoptarlo. Antes de la ejecución
final exigir árbol limpio y el commit de aplicación + tests del conductor. No crear
`qa/<fecha>-…`, menús, PR ni commit propio del toolkit.

Reemplazar en este modo las llamadas al engine por sus variantes con
`--projdir=<worktree literal>` para auditar **el mismo árbol**. Agregar
`--run-id=<round_id literal>` a `--check`/`--verify`, no a `--preflight` ni `--gate-hook`.
El conductor de improvement conserva Git: QA devuelve tests staged, resultado por
candidate/brief item y bloqueos; el conductor commitea y publica. El cierre único combina
[[security-pass]], [[maintainability-pass]], [[observability-pass]], [[perf-pass]] y
[[responsive-pass]], no cinco rondas independientes. Este contrato prevalece sobre los
pasos de apertura/landing de las fases 0 y 7; las guardas de producción, calidad y
autoría por capa siguen vigentes. Sin contexto se conserva el flujo independiente.

Cada guion incorpora `round_id`, candidate ID, capa, comportamiento, entrada, valor
concreto esperado, bug y referencias leídas. El Architect re-verifica todos los guiones,
unifica los que prueban el mismo comportamiento y conserva la asociación a cada
candidato. Se prioriza validar los cambios aplicados y sus casos negativos; luego las
obligaciones detectadas. La deuda adicional queda separada bajo la política de beneficio.
Todo candidate ID asignado termina con resultado explícito; no desaparece al deduplicar.

### Evidencia estructurada de la ronda

`--verify` comprueba calidad estática; **no ejecuta las pruebas ni demuestra E2E en vivo**.
El Verifier ejecuta los comandos y entrega salidas guardadas por esta ronda. Después del
commit final del conductor, con el tree limpio, asociar la ejecución al SHA completo de
`git rev-parse HEAD` y emitir este manifest JSON (una entrada por ejecución real). Los
reportes de ejecución y artefactos referidos son archivos regulares, sin symlinks, dentro
de un directorio gitignored del mismo worktree; el reporte normal de QA en el toolkit
los referencia. No usar un reporte toolkit externo como `manifest.report`.

```json
{
  "schema": 1,
  "kind": "improvement-qa",
  "round_id": "<round_id>",
  "codebase": "<codebase>",
  "commit": "<SHA40 probado>",
  "candidate_ids": ["<id>"],
  "report": "<directorio gitignored>/<round_id>/qa.md",
  "executions": [
    {
      "layer": "backend",
      "command": "<comando literal ejecutado>",
      "exit_code": 0,
      "executed": true,
      "report": "<directorio gitignored>/<round_id>/qa.md",
      "artifact": "<directorio gitignored>/<round_id>/backend-junit.xml",
      "format": "junit",
      "live": false,
      "candidate_ids": ["<id que esta ejecución comprueba>"]
    }
  ]
}
```

`layer` acepta `backend|frontend-unit|e2e|gate`; `format` acepta
`junit|pytest-json|playwright-json|gate-json` (`gate-json` sólo para el gate).
Los artefactos muestran tests reales ejecutados y sus resultados; ni skips-only ni
collection-only sirven. No fabricar artefactos para que el parser los acepte.
Los IDs coinciden exactamente con los
del registro de la ronda y cada candidato debe quedar cubierto por ejecuciones de tests,
no sólo por el gate. `command` identifica los archivos/casos concretos ejecutados y su
evidencia enumera los resultados de esos tests; no asociar candidatos a comandos que
prueban otro comportamiento. Adjuntar el manifest al reporte del engine con
`--verify <proyecto> --projdir=<worktree> --run-id=<round_id> --files=<tests> --verification=<path.json>`
y devolverlo al conductor. Éste lo entrega por stdin a
`scripts/improvement/improvement-ledger.sh --record-qa <proyecto> --projdir=<worktree> --round=<round_id> --commit=<SHA40>`.
El helper calcula el resultado: capas obligatorias completas, gate y tests ejecutados
en verde; para E2E requerido, `live=true` en un target local/staging que sirve este SHA.
Capturas, tags/flows `covered`, autoría o reporte de otra ronda no reemplazan ejecución.
Si cambia el commit, queda diff o se arregla un test, actualizar la ronda y repetir las
comprobaciones afectadas antes de asociar una verificación. Errores, falta de ejecución o
E2E sin app dejan la ronda pendiente/rechazada; nunca escribir `verified` manualmente.

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): (1) explicit flags → run direct, no menu;
(2) clear intent from the session ("QA this" right after a feature landed
here) → propose the command in one line and wait for confirmation; (3) bare
`/qa` with no obvious project/feature → ONE AskUserQuestion with the fused
questions below; (4) never inside fleet/headless sweeps (`--all-repos` /
`--all-vps`) — and the skills this conductor dispatches (coverage skills,
test-audit, fake-data-refresh) inherit THIS gating: they never ask on their own.

**Q1 — Mode** (`multiSelect: false`):

| label | description | preview |
|---|---|---|
| Dry-run (Recommended) | analyze coverage + quality gate; writes nothing, reports the worklist | `/qa <proyecto>` |
| Apply | authors tests to the 3-part DoD, purges junk via test-audit, commits on the resolved work branch | `/qa <proyecto> --apply` |

**Q2 — Layers** (`multiSelect: true` — combinable; no selection = all):

| label | description | preview |
|---|---|---|
| backend | pytest layer | `--layers=backend` |
| frontend-unit | jest/vitest layer | `--layers=frontend-unit` |
| e2e | Playwright layer | `--layers=e2e` |

**Qué NO se pregunta:** `--all-repos`/`--all-vps` (fleet sweep, analysis-only —
typed only).

## Engine

The deterministic parts live in
`$HOME/webapps/vps-ops-toolkit/scripts/qa/qa-agent.sh`. Call it; do not
reimplement it.

- `qa-agent.sh --preflight <proj>` → scope: layers, db engine, staging/production,
  `fake_data_allowed`, abstain decision, and the work coordinate.
- `qa-agent.sh --check <proj>` → coverage audit + quality gate → worklist counts,
  verdict, and a `docs/audits/<date>-<proj>-qa.md` report.
- `qa-agent.sh --verify <proj> --files=a,b` → re-run the gate on touched files,
  **with `--junk-severity=error` (CI parity)**. A gate that scans ZERO files is a
  false-clean and exits 2 — never a pass. On a clean pass it clears the marker.
- `qa-agent.sh --gate-hook` → the deterministic Stop-hook backstop (wired in this
  skill's frontmatter). While `<repo>/.qa-gate-pending` exists, ending the turn is
  BLOCKED (exit 2) until the gate passes over the files it lists. Integrity
  excludes exactly that root filename: it is non-executable, short-lived QA
  coordination metadata, not a deployed-code mutation.
- `qa-agent.sh --all-repos` / `--all-vps` → fleet sweep, analysis-only (see Fleet
  mode). `--report` is an alias of `--check`.
- `--projdir=<worktree>` → auditar explícitamente el worktree de la sesión;
  incompatible con fleet. `--run-id=<id>` separa nombre/header del reporte de la ronda.
  `--verification=<path.json>` adjunta evidencia estructurada de ejecuciones reales
  asociadas a esa ronda/commit en `--verify` con `--run-id`/`--projdir`; no ejecuta
  tests por su cuenta. `--run-id` sólo aplica a `--check`/`--verify`.

## Roles — dedicated subagents (dispatch by `subagent_type`)

Each phase dispatches a dedicated agent. The agents are **distributed per-project
at `.claude/agents/qa-*.md`** (canonical: `workflows/.user-level/.claude/agents/`;
project-level wins over any `~/.claude/agents/` copy), so `/qa` works on any
machine holding the repo. Caveat: the first time an `agents/` dir appears in a
scope, restart the session for the watcher to pick it up. The Engineers, Auditor
and Analyst **preload their skill via `skills:` frontmatter** (full content
injected — no prose indirection). **Tool scope = role boundary**: only the
Engineers and the Healer can write; Analyst / Architect / Auditor / Verifier are
read-only. One role, one agent.

| Phase | subagent_type | Does | Writes? |
|---|---|---|---|
| 1 | `qa-analyst` | (re)generates the flow map when stale — its ONLY duty | no |
| 2 | `qa-architect` | ranks the worklist + per-layer plan as **forwardable brief blocks** (file:line evidence) · duplicates/wrong-location · selector precondition | no |
| 4 | `qa-engineer-backend` · `qa-engineer-unit` · `qa-engineer-e2e` | author tests to the 3-part DoD from the Architect's block, verbatim | yes |
| 5 | `qa-verifier` | runs the gate + tests → APPROVED/REJECTED | no |
| 5 | `qa-healer` (opus) | root-causes red/flaky → minimal fix | yes |
| 6 | `qa-auditor` | KEEP/REWRITE/MERGE/DELETE, citing the rule | no |

Nota: the Analyst owns **Phase 1 only** (the flow map — measured: 0 dispatches
in 4 pilots with fresh maps; do not invent work for it). Phase 2's audit is
deterministic (`qa-agent.sh --check`, run by the conductor), its RANKING lives
in the **Architect** (official as of the pilot series), and its dispatch goes
to the **Architect**.

Spawn them with the Agent tool (`subagent_type: qa-…`); synthesize their fixed-format
returns and take the **worst** result as the run verdict. **Dispatch resilience:** a
role that dies on a server-side API error (529/overloaded) gets ONE immediate retry;
if the retry also dies, wait ~4 min and try once more; a third death → ⏸️ declared
pause naming the dead role (never silently skip a phase). **The hard gate is not a
subagent verdict** (that is model judgment) — it is an exit code, enforced twice with
the same severity: locally by `--verify`/`--gate-hook` and in CI
(`--junk-severity=error` against `.junk-baseline.json` in both). `qa-verifier` is the
in-loop check that feeds it; the CI gate is what actually blocks a merge.

## Routing — decide first

Run `basename "$(git rev-parse --show-toplevel)"`:

- A **project repo** → single-project run (Phases 0–8).
- **vps-ops-toolkit** + `--all-repos` or `--all-vps` → `qa-agent.sh` in fleet mode
  (analysis-only) and report. Never author on a fleet sweep.
- **vps-ops-toolkit** with no fleet flag → refuse: run `/qa` inside a project, or
  `/qa --all-vps` for a fleet audit.

## Safety rails — always ON (visible to the operator; override is explicit)

1. **Dry-run by default.** Without `--apply`: describe the planned diffs, write
   nothing, commit nothing.
2. **Production visibility.** `--preflight` reports `production=yes` for
   production+active — informational: authoring follows the work coordinate
   like any project (projects.yml decides), and fleet sweeps stay analysis-only
   for every repo. Staging-first otherwise.
3. **fake-data-refresh only off production.** `--preflight` reports
   `fake_data_allowed`. If `no`, SKIP the fake-data phase — never reseed prod.
4. **Land on the resolved coordinate.** `resolved_branch` from the preflight is
   the BASE; the commit lands on a `qa/<fecha>-<slug>` session branch whose PR
   targets it (Phase 7). `host_status=wrong-host` blocks **authoring/landing** — STOP before
   writing anything; the work lives in another VPS clone (use its `tailscale
   ssh`). The dry-run analysis (Phases 0–2) MAY proceed on the wrong host,
   flagged ⚠️ and declared in the verdict.
5. **Never merge.** Stop at "committed on the work branch". Merging is
   `/merge-queue` (operator); `/merge-when-green` is operator-only. A release
   branch (`pr_state=single|ambiguous`) → commit-hold, no merge.
6. **deploy-and-check is a suggestion.** Never auto-run it; name it in Next steps.
7. **Clean tree before --apply.** Refuse to author on a dirty tree, so the QA
   commit is revertible on its own.
8. **Session worktree.** `--apply` writes ONLY inside `~/webapps/.wt/<repo>/<slug>`
   for the PROJECT being QA'd. Create it BEFORE any write under `--apply` — right
   after Phase 0's preflight, since Phase 1 (methodology-setup / flow-map) already
   writes — via `session-worktree.sh create qa <slug>` (or tmpl §5), and enter it
   (Claude: `EnterWorktree`; Codex: `cd`) — subagents inherit the session cwd.
   Never in the main clone. Carve-out: the TOOLKIT's own `config/qa-memory/*.yml`
   commit (Phase 7) lands on `vps-ops-toolkit`'s `master` (trunk flow, no
   worktree) — that write targets a DIFFERENT repo than the one being QA'd.

## Phase 0 — Preflight & abstain

`bash $HOME/webapps/vps-ops-toolkit/scripts/qa/qa-agent.sh --preflight <proj>`.
Read the scope. **Abstain `⏭️` in seconds** when `abstain=yes` (no test infra) or
nothing changed since the branch base. A false auto-invocation must cost a fast
no-op, never a write.

**`registry=absent`** = the directory exists but the project is NOT in
`projects.yml`, so every registry-derived default is untrustworthy. Before ANY
`manage.py`, derive `db`/settings from the repo itself — the settings selector
may be `DJANGO_SETTINGS_MODULE` (base_feature lineage), not `DJANGO_ENV`, and
the engine may be postgres/sqlite even where the fleet default says mysql.
Treat the CURRENT branch as the work coordinate only with explicit operator
confirmation (the resolver reports `coordinate=unavailable` for it) — and even
then in a session worktree, never by mutating the clone — and suggest
registering the project in `projects.yml`.

**QA memory (`qa_memory=<path|absent>`)** — the per-codebase shape cache in
`config/qa-memory/` (schema + full contract: its `README.md`). When present,
Read it: `shape`/`quirks` seed the Architect, layer quirks seed the engineer
preambles, `watchlist` items join the worklist, `unvalidated_specs` feed
Phase 5b. **Anti-bias contract — memory pre-seeds hypotheses, it never
replaces measurement:**

- `--check` always re-measures; no remembered count is authoritative.
- Every memory fact used in a brief is re-verified this run — enforced
  structurally by the Architect's file:line evidence rule (an unverified
  claim cannot enter a brief block).
- Mismatch memory↔repo → correct the memory file in this run, never propagate.
- Memory NEVER justifies skipping a phase or shrinking scope; `watchlist`
  only ADDS work. No metrics live in memory (a stored number becomes a
  target — history lives in `docs/audits/*-qa.md`).

**`PERF pending` watchlist lines** (written by [[perf-pass]] §5b) point at a
`brief-perf` script in the toolkit's `docs/audits/`: the Architect reads it and
plans its items as budget tests in the owning layer (query / fetch / size
counts — never time), re-verifying every `file:line` this run; the files it
creates are what `perf-pass --record-qa` later measures. Report them as a
`Presupuestos perf` row in the final table and add the Next step
`/perf-pass <proj> --candidate=<id> --record-qa`.

**Handoffs de las cinco pasadas.** Además de `PERF pending` y `RESPONSIVE pending`,
leer los guiones `brief-security`, `brief-maintainability` y `brief-observability`
referenciados por la ronda o el watchlist. No requieren tres nuevas capas: permisos/
inputs/idempotencia suelen ir a backend; transformaciones y manejo de fallos a unit;
flujos/anchos a E2E. El Architect decide por el comportamiento real y re-verifica
evidencia. Cada guion termina en un bloque por capa para el Engineer correspondiente,
conservando candidate ID e ítem de origen. Observaciones sin cambios no cuentan como
validaciones completadas. En modo delegado, registrar por el helper común y su manifest,
no mediante el último reporte independiente de perf/responsive.

On `qa_memory=absent` for a repo worth remembering, Phase 7 creates the file
at the printed path.

## Phase 1 — Understand + flow map (Analyst)

- If `docs/methodology/` is missing or stale, run **methodology-setup** (conductor
  work — no dedicated agent) to build the Memory Bank. Safe anywhere.
- Mapa de vistas (trabajo del conductor, no del Analyst): sólo si el repo tiene
  `frontend/config/viewCatalog.js` y la skill [[view-map-update]] está
  instalada para este runtime (Claude: `.claude/skills/view-map-update/`;
  Codex: `.agents/skills/view-map-update/`); si no, `⏭️`. Dry-run →
  `--check --diff` (reporta, no escribe); `--apply` → `--apply --diff` en el
  worktree de QA: sus cambios entran al commit de Phase 7 junto al flow-map, y
  los tests de conteos fijados que toque se suman a la unión de
  `files_touched` del gate (`.qa-gate-pending`/`--verify`). Sus handoffs E2E
  (escenario responsivo visual sin spec) pasan al Architect en Phase 2 como
  ítems e2e. Nunca pregunta (hereda este gating), nunca en fleet mode, y si la
  sesión ya la corrió sobre este mismo diff, cita ese resultado.
- Flow map: the preflight emits `flow_map_fresh=yes|no`; **if the key is ABSENT,
  the map does not exist** — same action as `no`: dispatch **`qa-analyst`** (it
  preloads `e2e-user-flows-check`) to derive the flow registry from the app's
  real code — the four outcome classes (success/error/failure/display),
  **negative cases included**. The Analyst RETURNS the content (role boundary:
  it never writes); the conductor writes it **in the repo's declared layout**
  (`.testquality.yml` → `flow_definitions_dir`): sharded ⇒ per-flow JSONs +
  per-flow docs, then regenerate the derived aggregates with
  `generate_flow_registry.py` (never hand-edit them); monolith ⇒
  `frontend/e2e/flow-definitions.json` + `docs/USER_FLOW_MAP.md` as before.
  Under dry-run: report the diff, write nothing. This is the Analyst's ONLY
  duty — ranking belongs to the Architect. If `yes`, skip `⏭️`.

## Phase 2 — Coverage audit + worklist (conductor → Architect)

`qa-agent.sh --check <proj>`; besides the counts, its output itemizes the flow
ids: `junk_only_flows=[…]` / `unvalidated_flows=[…]` / `missing_flows=[…]` /
`undeclared_flows=[…]` (emitted only when non-empty, capped at 20 each), plus
per-suite `<suite>_error_files=[…]` — the files carrying content-error gate
findings, which is the backend/frontend-unit layers' only deterministic worklist
(they have no flow map). Then dispatch **`qa-architect`** with the counts AND
those itemized lists verbatim in its prompt — the Architect must NOT re-derive
them by re-reading the whole repo. Its prompt also names the findings ledger's
"recurring heal classes" section (`docs/qa-agent/findings-ledger.md`) and, when
the preflight reported a `qa_memory` file, the memory's `shape` + `quirks`
slices — both as hypotheses the Architect must verify against the repo, never
as facts to forward.

The **ranking lives in the Architect** (priority scale = the flow-map's own
`priority: P1–P4`; `exempt` flows are NOT gaps — skip them):

1. **junk-only flows first** — a false green is worse than an honest gap.
2. missing P1/P2 flows.
3. **missing error/failure outcome classes** (`negative_case_gaps`) — the heart of
   QA.
4. weak / duplicate gate findings; mark duplicates and wrong-location tests for the
   Auditor.

(`unvalidated_flows` are NOT authoring work — they are Phase 5b validation work;
route them there, never to an engineer as "missing".)

**The Architect's return IS the work order.** It comes back as fenced per-layer
blocks (```` ```brief-backend ```` / ```` ```brief-unit ```` /
```` ```brief-e2e ````, items `B1..`/`U1..`/`E1..`, every claim carrying
`file:line` evidence). Store the blocks: Phase 4 forwards each one to its
engineer **verbatim** — measured in the pilots, every layer of conductor prose
between the plan and the engineer introduced factual errors (4 in 4 pilots).

Assert the **selector convention** (`data-testid`/role). If the app lacks it, say
so and bound the e2e work until it exists — an auditor with nothing consistent to
audit is theater.

## Phase 3 — Fresh data (guarded, interactive)

Decision table — the production guard always wins and the operator decides the rest:

| Preflight says | Behavior |
|---|---|
| `fake_data_allowed=no` (production) | **Silent skip — never ask.** The double inverse gate rules. |
| `=yes` + dry-run (`--check`) | Don't ask; report `⏭️ se preguntaría en --apply`. |
| `=yes` + `--apply` + a freshness signal | **Ask the operator** (AskUserQuestion): *"¿Refresco fake data en <proyecto>? (delete + create — el gate de prod ya pasó)"* with a recommendation based on the signal. On yes → run **fake-data-refresh**. |
| `=yes` + `--apply` + no signal | Skip with a note — don't nag when data looks healthy. |
| Fleet / headless mode | Never ask (analysis-only). |

**Freshness signals** (any one suffices): the worklist has e2e/`display` work; model
counts at 0 or incoherent; the operator's request mentions data/fixtures/seeding.

## Phase 4 — Per-layer fan-out (Engineer ×3)

Spawn up to 3 dedicated subagents in ONE message via the Agent tool
(`subagent_type: qa-engineer-backend | qa-engineer-unit | qa-engineer-e2e`) — the
layers own **disjoint file sets**: backend = `backend/**/tests/`; unit = every
`*.test.*`/`*.spec.*` under `frontend/` OUTSIDE `e2e/` (Next/Nuxt colocate them in
`**/__tests__/` at arbitrary depth — there is no single "unit dir"); e2e =
`frontend/e2e/`. They never collide. Only for present layers with non-empty work.

**The engineer prompt is: fixed preamble + the Architect's block VERBATIM.**
The preamble carries only run facts the Architect does not own: resolved
coordinate + guards, `db=`, `app_reachable`, dry-run/apply mode, and the
layer's memory `quirks` slice when one exists. Then paste that layer's fenced
brief block byte-for-byte. You MAY append facts after it; you MUST NOT rewrite,
summarize, re-derive or "clean up" the block — the 4 measured brief errors of
the pilot series all came from conductor paraphrase. Each engineer:

- Follows its coverage skill verbatim: backend → `backend-test-coverage`,
  frontend-unit → `frontend-unit-test-coverage`, e2e → `frontend-e2e-test-coverage`.
- Works its brief items in order (junk-only first), covering the
  **negative-case classes** the block declares.
- Hard constraints: run only touched files; a `db: mysql` project runs `manage.py`
  with `DJANGO_ENV=production` from `backend/` (see `--preflight db=`); stay inside
  your layer's directory; stop and fix if the gate flags junk on your batch
  (quality ceiling beats volume) — **the self-check command the preamble hands the
  engineer MUST carry the EXACT `run_gate_on_files` parity: `--semantic-rules
  strict --junk-severity=error --external-lint run`** (a mirror without
  `--external-lint run` measured a 100/100 false-clean against 10 CI-parity ruff
  errors — F88, 2026-08-13); under `--apply` author and **leave staged — do
  not commit** (the conductor commits once); under dry-run, describe the diffs and
  write nothing.
- Returns its fixed-format block (the agents' own contract): `STATUS
  (AUTHORED|DRAFTED|ABSTAINED|BLOCKED), brief_items, brief_corrections,
  tests_authored, flows_closed, abstentions, gate_on_batch, tests_run,
  files_touched, blocked` (+ `markers` for e2e). The engineer's identity tells
  you the layer — do not expect a `layer` field.

**Conservation check:** every id in the forwarded block must appear in the
engineer's `brief_items` (done / blocked / abstained). A `blocked(brief-conflict)`
item means the repo contradicted the plan — the repo wins: re-dispatch ONLY the
conflicted items to the Architect with the engineer's `file:line` evidence, or
drop them declared in the report. Never re-author them yourself and never let
them vanish silently. `brief_corrections` (trivial fixes the engineer absorbed)
feed the memory update in Phase 7.

Assert the `files_touched` sets are pairwise disjoint (they must be, by directory).
A non-disjoint result is a bug → stop and report.

**Gate marker (under `--apply`):** as soon as the engineers return, write the union
of `files_touched` (one repo-relative path per line) to `<repo>/.qa-gate-pending`.
From that moment the Stop hook makes it impossible to end the turn until the gate
passes over those files; Phase 5's `--verify` clears the marker on a clean pass.
Never delete the marker by hand to "unblock" — fix the findings.

Mutation testing is also worktree-only: `mutation-pilot.sh --run` requires
`--projdir=<worktree-de-sesion>` and rejects a primary/deployed clone before it
can seed config, install a dependency or execute mutants. `--plan` stays
read-only and may inspect the maintained clone.

**E2E needs the running app.** The preflight probes it: `app_reachable=local:<port>
| staging:<url> | no` (production is NEVER probed nor validated — read-only by
contract). Pass the value to the e2e engineer: with an app it EXECUTES its specs;
without one it **drafts** (tagged `@flow`/`@outcome`, acts + asserts), writes the
file-level `// qa: draft-unvalidated (<date> — <reason>)` marker on every new
spec, and returns `blocked: validate-pending`. The marker is what keeps a draft
from buying false coverage: the flow audit reports its flows `unvalidated`, and
4/4 pilot draft batches failed on first live execution — a draft that LOOKS
finished is the failure mode this state exists to name.

## Phase 5b — Live e2e validation (conditional — playwright-validation as a phase)

Runs when `app_reachable≠no` AND either trigger holds:

- the e2e engineer returned `validate-pending` **this run**, or
- the preflight reported leftover `unvalidated_specs=[…]` from a **previous
  run** — cross-run healing: validate the leftovers FIRST, before this run's
  own drafts.

Under **dry-run, leftovers are reported only** — executing a mutating draft
against staging is a write, and rail 1 owns writes; validation + marker removal
happen exclusively under `--apply`.

1. Follow `playwright-validation` §9 (Handoff validate-pending) inline: for each
   draft spec, `cd frontend && npx playwright test e2e/<spec>`; collect pass/fail.
2. Green → **remove the spec's `// qa: draft-unvalidated` line** (first green
   run = the marker's exit condition; a later regression is an ordinary red
   test, never re-marked), then `qa-agent.sh --verify <proj> --files=<specs>`
   (clears the gate marker); the run upgrades 🟡→🟢 for the e2e dimension. The
   removal is part of this run's commit.
3. Failures → dispatch **`qa-healer`** (≤3 attempts per spec); the marker stays
   until the heal runs green.
4. Mutating drafts run only against `local:`/`staging:` targets — which is all
   the probe can return; if `app_reachable=no`, this phase is skipped, the
   markers stay, and the manual handoff (Next steps → `dev-up` +
   `playwright-validation`, re-`/qa`) stays exactly as before.

## Phase 5 — Gate / verify (Verifier → Healer)

Dispatch **`qa-verifier`**: it runs `qa-agent.sh --verify <proj>
--files=<union of files_touched>` (CI-parity severity; zero junk on the batch),
runs only the touched tests, and — where mutation tooling is configured — the
diff-scoped mutation gate. A failing or flaky test → dispatch **`qa-healer`**
(preloads `fix-broken-tests`; hard cap **≤3 attempts per test**); it flags any
production-code change ⚠️ and STOPS for operator approval before applying it.

## Phase 6 — Junk purge (Auditor)

Dispatch **`qa-auditor`** (preloads `test-audit`) scoped `--since=<branch-base>`
(mechanically: `git diff --name-only <base>` → repeated `--include-file`) to catch
junk the authoring introduced AND pre-existing junk-only. DELETE only with
per-batch operator approval (test-audit's own guardrail). Dry-run unless `--apply`.

## Phase 7 — Land + report (conductor)

- Step 0: ensure the session worktree (normally already entered in Phase 0
  under `--apply`, rail 8) — author and commit ONLY inside
  `~/webapps/.wt/<repo>/<slug>`, never in the main clone. Inside a native worktree
  Claude refuses any command carrying `$(...)`, `{a,b}`, a `for`/`while` or a
  heredoc with substitution, plus `git -C <main clone>` / `cd <main clone>` — the
  whole block dies. So: **one plain command per call**, and take branch/base/PR
  number from a single
  `bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh status`,
  writing them **literal** in the next call (convention: `git-branch-protocol` §1).
- Under `--apply`: commit the authored tests (Conventional Commits, English).
  `resolved_branch` is always the **BASE** of the work, never where the commit
  lands directly (per-session protocol — one session, one branch, one PR):
  - **Release repo** (`resolved_branch` = the release): land as a session
    branch `qa/<fecha>-<slug>` cut FROM the release, PR targeting the release
    (stacked). Never commit directly on the release branch.
  - **Prod-direct repo** (`resolved_branch` = `main`/`master`): land as a
    `qa/<fecha>-<slug>` branch + PR targeting `resolved_branch`.
  Open the PR at first push with `Sesión:`/`Intención:` in the body, per
  `git-branch-protocol` — NEVER push directly to a project repo's base branches. The
  `--body` is literal double-quoted text with real newlines, **never**
  `--body "$(printf …)"`: the command substitution is refused inside the worktree.
  **Do not merge.** With `--apply` the DoD is PR open + CI green: hand over to
  [[pr-green]] if the operator asks to wait for CI.
- **Git identity before committing:** `git var GIT_COMMITTER_IDENT` fails on a
  fresh clone — if it does, configure `user.name`/`user.email` **repo-local**
  with the operator's identity (never `--global`), then commit.
- **Stale in-repo gate:** in a repo whose in-repo quality gate is an old fork of
  the core, the canonical allow-markers are inert for THAT repo's CI until
  `sync-test-quality-core.sh` propagates the core — declare the divergence in
  the report instead of assuming the markers took effect. Same for the
  `unvalidated` state: an old in-repo `flow_coverage_audit.py` still counts
  drafts as covered — the false green persists IN THAT REPO's own reporting
  until the core syncs; declare it.
- **QA memory update** (any mode — recording is not a project write): refresh
  the codebase's `config/qa-memory/<key>.yml` — bump `runs`/`last_run`, fold in
  what this run verified or corrected (`brief_corrections` are prime input),
  new quirks with evidence, expired watchlist items out (2 runs untouched),
  current `unvalidated_specs`. Respect the caps (quirks 30, watchlist 10) and
  the no-metrics rule. Commit it to the TOOLKIT on master as its own small
  commit — never mixed into the project's QA commit.
- Close per `[[_output-protocol]]`. **Suggest — never run** — `/deploy-and-check`
  in Next steps. Merging is `/merge-queue` (operator); `/merge-when-green` stays
  operator-only and is never suggested from a session.

## Phase 8 — System retro: fix-or-file (conductor)

The /qa system improves itself the way it improved through the pilots — every
run ends by triaging the frictions it hit **in the system** (engine errors,
wrong or ambiguous skill/agent text, core false positives/negatives, doc gaps).
Accumulate them during the run; act ONCE, here, after Phase 7. Findings about
the PROJECT are report material, never retro material.

Triage each friction into exactly one class:

- **Class A — engine/core bug with a deterministic repro** (qa-agent.sh,
  `workflows/testing/`): write the failing regression check FIRST → fix → run
  ALL THREE harnesses — green, or revert immediately (toolkit master is never
  left red). Commit to toolkit master. **Auto** (operator decision 2026-07-26),
  always reported prominently. A new junk RULE additionally requires the
  baseline re-freeze in the same commit (existing rule).
- **Class B — skill/agent text defect** (qa.md, `qa-*.md`, the coverage
  skills): draft the diff and ASK the operator (AskUserQuestion) before
  applying — text changes alter future-run behavior. Exception: pure typos and
  dead references are auto. A `qa.md` edit is always paired with
  `sync-skill-mirrors.sh --apply` in the same commit.
- **Class C — improvement idea, no bug**: file it in the ledger backlog with
  rationale. No code change.
- **Class S — NEVER auto, operator-only regardless of class**: the 7 safety
  rails' text, the production/fake-data/probe guards (F24), and the
  gate-hook/marker-clearing logic. A "fix" that weakens a guard is a
  regression by definition.

Hard guardrails (all always ON):

1. Phase 8 runs ONCE per run, after landing — never mid-phase, and a self-fix
   never re-triggers the retro.
2. Anything discovered WHILE self-fixing goes to the ledger, never fixed in
   the same run — this kills recursion.
3. **≤2 Class A fixes per run**; the rest go to the backlog.
4. The current run's verdict stands on the code that RAN — a self-fix never
   retro-upgrades it.
5. Every action (A, B or C) appends its row to
   `docs/qa-agent/findings-ledger.md` — next ID from its header, same commit
   as the fix. The ledger is the memory of the system itself.
6. Self-fix commits are toolkit commits, always separate from the project's
   QA commit.

## Fleet mode (analysis-only)

`/qa --all-repos` (this host) or `/qa --all-vps` (fleet via tailscale) call
`qa-agent.sh` in fleet mode: gate + flow-audit + per-project verdict + per-host
report. **No authoring** — subagents run where Claude runs, and there is no Claude
on a VPS. Authoring is always local + single-project. On a tailscale auth pause
(exit 75) show the login link and re-run.

**Pilot clones (authoring a repo whose work clone lives on another VPS):** clone
into a NON-COLLIDING path (`<name>_pilot`, never the fleet dir name — the fleet
clone may already exist on this host and `clone && cd && checkout` against it
mutates a PRODUCTION checkout; measured incident, pilot #3). Verify the clone
succeeded BEFORE any cd/checkout. Cut a `qa/<fecha>-<slug>` branch from the
resolved work branch inside the pilot clone, author, push THAT branch and open
the PR with base = the resolved work branch — never push directly to the base
— delete the pilot clone at close. The pilot is a
throwaway clone at a non-colliding path — NOT a fleet main clone, so creating
the session branch inside it is fine; the rule "never checkout a fleet main
clone" stays intact.

**Remote-verify (running the touched tests on the VPS work clone via
`tailscale ssh`):** the substrate lives there (venv, DB, node_modules, browsers).
Node is under nvm with an interactive-only guard — non-interactive SSH (even
`bash -lc`) cannot see `npx`; prefix the absolute path:
`export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"`. This is the CI
substitute for billing-blocked private repos and the Fase 5b runner.

---

## Output final

Sin menú por diseño (§4): el cierre es el veredicto duro del gate; los siguientes pasos viven en el reporte y su Next steps.

Reportar siguiendo [[_output-protocol]]. Plantilla específica de `/qa`
(single-project):

```markdown
🟡 qa OK con N warning(s) — <proyecto>

| Dimensión | Estado | Detalle |
|---|---|---|
| Preflight + coordenada | ✅ | layers=[…] · db=… · rama=<resolved_branch> · on-work-host |
| Methodology (fase 1) | ⏭️ | docs/methodology fresco (✅ si se regeneró) |
| Flow-map · Mapa de vistas | ✅ | flow-definitions.json fresco (⏭️ si no aplica) · mapa de vistas al día (sólo con mapa; ⚠️ N ajustes en dry-run) |
| Fake data (fase 3) | ⏭️ | prod: skip silencioso · staging: preguntado/skip-sin-señal |
| Auditoría cobertura | ⚠️ | junk-only: N · unvalidated: N (drafts sin ejecutar) · missing P1/P2: N · clases error/failure faltantes: N · exempt: N (no son gaps) |
| Backend (subagente) | ✅ | N tests, valor concreto + "qué bug atrapa"; DJANGO_ENV=production |
| Frontend-unit (subagente) | ✅ | N tests, sin weak/tautological/duplicate |
| E2E (subagente) | ⚠️ | N specs @flow/@outcome; 2 draft — app no corriendo (validate-pending) |
| Validación e2e en vivo (fase 5b) | ⏭️ | app_reachable=no → handoff manual · ✅ N drafts validados en <local/staging> |
| Quality gate (batch) | ✅ | cero hallazgos junk en archivos tocados (severidad CI) |
| Mutation gate (si hay tooling) | ⏭️ | diff-scoped · survivors=N (o ⏭️ sin tooling) |
| Healer | ⏭️ | N tests reparados (≤3 intentos c/u) · 0 cambios a código prod |
| Junk purge (test-audit) | ⏭️ | dry-run: N candidatos DELETE/MERGE, sin aplicar |
| Land | ✅ | rama qa/<fecha>-<slug> + PR base=<resolved_branch>; sin merge (drena `/merge-queue`) |

## Next steps
- `bash $HOME/webapps/vps-ops-toolkit/scripts/qa/qa-agent.sh --verify <proj> --files=<spec>` — reconfirmar el gate
- (operador) `dev-up` + re-`/qa --apply` para VALIDAR los e2e en draft
- `/perf-pass <proj> --candidate=<id> --record-qa` — sólo si la corrida consumió un puntero `PERF pending`: registra el veredicto medido en el ledger de rendimiento
- (operador) `/merge-queue` — QA nunca mergea
- (operador, opcional) `/deploy-and-check` — desplegar (sugerencia, nunca auto)
```

Casos de veredicto:

- 🟢 gate limpio, cero junk-only, **cero unvalidated** (el engine computa el
  conteo global — un draft sin ejecutar en CUALQUIER spec del repo degrada,
  igual que junk-only), cada clase de outcome declarada cubierta o abstenida
  con razón.
- 🟡 quedan gaps, abstenciones declaradas, e2e draft-only (validate-pending o
  specs con marker `qa: draft-unvalidated` pendientes de validación en vivo),
  alcance staging-only, o `analysis=degraded` (errores sólo-infra del gate: AST
  bridge ausente — `npm install` en `frontend/` habilita el análisis completo;
  el gate CI con node_modules es la última palabra).
- 🔴 errores de CONTENIDO del gate, o un test (nuevo o existente) falla.
- 🚫 REFUSED — intento de commit en `wrong-host`. Nombrar el VPS correcto.
- ⏭️ abstención (sin infra de tests / nada que QA-ear).
- ⏸️ release-hold, auth-pendiente de tailscale, o app no corriendo que requiere al
  operador.

En modo fleet, anteponer una columna `Host`/`Proyecto` y, si hay >15 filas, un
`### Top 3 acciones prioritarias` (junk-only + P1 sin cobertura) antes de la tabla.
