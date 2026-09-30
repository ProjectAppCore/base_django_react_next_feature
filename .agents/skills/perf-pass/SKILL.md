---
name: "perf-pass"
description: "Mejora el rendimiento de un proceso o hasta tres candidatos del ledger de un proyecto, contra el perfil real del host y con validación de qa. Usar cuando hay lentitud, N+1, consumo de memoria, tareas bloqueantes o bundles pesados. Registra decisiones de beneficio/coste y recomienda parar ante mejoras marginales. Aplica por default con un requerimiento en contexto; sin él ofrece selección, revisión o refresco. La infraestructura sólo se observa."
---

# Perf pass — un requerimiento, o hasta 3 candidatos, contra el host real

Sos el responsable de rendimiento de UN proyecto del fleet. Tu salida es **hallazgos
contrastados contra los presupuestos derivados del perfil de cómputo + cambios acotados a
los `paths` del candidato (mismo contrato, mismos datos) + un guion de tests de presupuesto
para $qa + el ledger al día** — no un rediseño, no una suite de tests, no un tuning del
servidor. La secuencia de fases es fija (Fase 0 → 6) para que dos corridas sean
comparables, y **la verificación la hace `$qa`, nunca esta skill**: una skill que se da por
buena a sí misma no está verificando nada. El QUÉ (presupuestos, LÍMITES, casos, evidencia)
vive en `docs/PERFORMANCE_STANDARDS.md` (canónico `workflows/testing/PERFORMANCE_STANDARDS.md`);
esta skill no lo re-narra.

## Beneficio y límite de la pasada

Aplicar la política común `workflows/improvement/IMPROVEMENT_STANDARDS.md` del toolkit
antes de seleccionar y antes de editar. Un presupuesto obligatorio incumplido, una
regresión, pérdida de datos o riesgo de seguridad demostrado **no se descarta por costo**:
se corrige dentro de los LÍMITES o se declara bloqueado con su siguiente acción.

Cada candidato lleva `value_assessment: {benefit, effort, change_risk, mandatory, reason,
evidence}`: `benefit=material|minor|unknown`, `effort=S|M|L`, `change_risk=low|medium|high`.
Beneficio material requiere evidencia concreta; beneficio menor sólo es elegible con
`S`, riesgo `low` y utilidad concreta. Menor con mayor esfuerzo/riesgo queda
`deferred-low-value`; incierto queda diagnosticado con decisión `needs-evidence`, nunca
como frente suficiente. Una mejora puramente cosmética sin utilidad queda descartada.
No reinterpretar un fallo del presupuesto obligatorio como beneficio menor.

El helper conserva IDs/estados históricos y calcula la decisión y el contexto: código
relevante, dependencias, política/estándar y perfil de cómputo. No escribir fingerprints
a mano ni repetir métricas en el ledger; `reason` explica el retorno y `evidence` apunta
al reporte. Sin evaluación vigente se reevalúa antes de aplicar, también en `--top3` o
modo A. Un diferido queda fuera del selector hasta que ese contexto cambie.

Si el alcance **inventariado** ya cumple sus obligaciones y sólo quedan cambios de poco
retorno, decir: «Conviene parar en rendimiento para <alcance>: <evidencia y motivo>.
Revisar si cambia <condición concreta>». No editar ese frente. Un alcance sin mediciones
necesarias, sin inspeccionar o pendiente por el cupo se declara así; nunca «agotado».

## Modo delegado por improvement-pass

Con `IMPROVEMENT_CONTEXT` de $improvement-pass se heredan `conductor`, `round_id`,
`project`, `codebase`, `projdir`, `branch`, `base`, `candidate_ids`, `allowed_paths`, `mode`
y `owns_git=conductor`. Ese bloque es contexto de la skill, **no un flag nuevo del helper**.
Validar que `session-worktree.sh status` describe ese proyecto/worktree/rama/base y que
la sesión o el PR pertenecen al conductor. Contexto ajeno o incoherente ⇒ bloquear antes
de escribir. El límite es **tres candidatos globales** de la ronda, no tres por skill.

Este modo tiene precedencia sobre picker, creación de worktree, commits/push/PR y menús
de las fases siguientes: se trabaja sólo sobre los candidatos y paths asignados, en el
worktree del conductor. Devolver diff, diagnóstico, evaluación de valor y `brief-perf`
con `round_id` y candidate ID en cada ítem; el conductor lleva Git y los registros. No
ejecutar QA inline ni abrir otra rama. No despachar un segundo `perf-scout` si el
conductor ya entregó inventario: devolver los hallazgos adicionales para otra ronda.

El ledger común se consulta con
`bash ~/webapps/vps-ops-toolkit/scripts/improvement/improvement-ledger.sh --show <proyecto> --projdir=<worktree>`;
sus referencias a perf mantienen el ID histórico. La selección y el registro común
son del conductor. La verificación delegada usa exclusivamente `--record-qa` del helper
común con la ronda, SHA exacto y manifest de ejecuciones de $qa; nunca el último
reporte de QA por fecha. Los modos independientes de esta skill se conservan.

**Declaración de cómputo — se imprime SIEMPRE antes de la Fase 1, con los valores literales
de `perf-ledger.sh --show`:**

> ⚙️ perf-pass — `<proyecto>` · modo `<A|B:top3|B:review3|B:refresh>` · `<aplicar|diagnóstico>` ·
> optimiza para **`<profile_id>` = `<vcpu>` vCPU / `<ram_gb>` GB RAM** (perfil `<profile_source>`,
> calibrado `<calibrated_on>`; host de trabajo `<work_host>` si difiere) · unit `<unit>`
> `<workers>`×`<threads>` · CPUQuota `<cpuquota>` ⇒ `<cpu_req>` core/request (≤ `<cpu_ms_api>` ms
> CPU en API) · MemoryMax `<memmax>` ⇒ `<worker_mb>` MB/worker, ≤ `<req_mb>` MB/request,
> `<rows_max>` filas materializables · queries listado ≤ `<query_list>` · tarea ≤ `<task_s>` s ·
> caso objetivo `worst` (fallback `conservative`) · dataset ceiling `<dataset_ceiling|10x-actual|default-estándar>`.
> Trabaja `<N≤3>` candidatos `[ids]`; el resto queda en el ledger (`<n>` candidatos; próximo
> top3 `[…]`; `<k>` stale por recalibración).

Si `profile_source=fleet_default` para un proyecto con `server:` (host sin entrada en
`config/perf/compute-profile.yml`) la fila `Perfil de cómputo` del reporte queda ⚠️ y el
Next step es declarar el host (recalibración, `docs/capacity-runbook.md`). El perfil **nunca
se pregunta ni se asume**: sale del archivo; recalibrar es editarlo.

## Cómo invocar este skill

Gating ($output-protocol §4): (1) flags explícitos (`--candidate=`, `--top3`, `--review3`,
`--refresh`, `--apply`, `--no-apply`, `--record-qa`) → ejecutar directo, sin menú; (2) **modo A**
— hay texto de requerimiento en `$ARGUMENTS`, o la sesión está a mitad de una feature (viene
de $implement / `session-worktree.sh status` devuelve un worktree de sesión con diff) →
sin picker: candidatos = el camino de código del requerimiento, **aplica por default** en el
worktree de la sesión (`--no-apply` para sólo diagnosticar); (3) **modo B** — `$perf-pass`
pelado o pedido difuso ("mejorá el rendimiento") → la Fase 0 corre primero (el helper arma
las filas) y UNA sola AskUserQuestion con Q1+Q2 fusionadas; (4) jamás en fleet/headless/cron
— esta skill no tiene modo fleet: `--all-repos`/`--all-vps` son error duro; (5) máx 4
opciones por pregunta; los candidatos que no entran se nombran en `## Next steps`; (6) Q1 y
Q2 son selección única (sets y modos excluyentes); (7) un dato faltante posterior (p. ej. el
endpoint exacto de un proceso) se pide en texto plano, ≤3 bullets, nunca un segundo picker;
(8) en Codex (sin AskUserQuestion) las mismas filas se muestran como lista numerada y se
espera la respuesta tipeada.

**Q1 — Qué trabajar** (`multiSelect: false`; las filas salen de `top3`/`review3` de `--show`):

| label | description | preview |
|---|---|---|
| Top 3 candidatos nuevos (Recommended) | `<id · categoría · severidad>` ×3 del `top3` (regressed primero, luego por severidad × confianza × esfuerzo) | `$perf-pass <proyecto> --top3` |
| Revisar 3 ya trabajados | `<id · estado · calibrado>` ×3 del `review3` (perfil recalibrado o estándar viejo primero, luego los más antiguos) | `$perf-pass <proyecto> --review3` |
| Refrescar catálogo | descubre y anota candidatos nuevos con `perf-scout` sobre `performance_paths`; no trabaja ninguno; marca stale y huérfanos | `$perf-pass <proyecto> --refresh` |
| Requerimiento actual | el proceso que está en la sesión (se tipea en Other: "listado de facturas del panel") | `$perf-pass <proyecto> <requerimiento>` |

**Q2 — Modo** (`multiSelect: false`; sólo en modo B):

| label | description | preview |
|---|---|---|
| Diagnóstico (Recommended) | inventario + contraste + propuesta + guion brief-perf; no escribe en el proyecto; registra en el ledger del toolkit | `$perf-pass <proyecto> --top3` |
| Aplicar | además edita los `paths` de cada candidato en rama de sesión + PR (un commit por candidato) y deja el handoff a $qa | `$perf-pass <proyecto> --top3 --apply` |

**Qué NO se pregunta:** el perfil de cómputo (lo fija `config/perf/compute-profile.yml`; se
imprime); el proyecto (sale del cwd; el posicional es un override); la rama/base (la resuelve
el preflight de `$qa` vía `resolve-work-coordinate.sh`); el caso `worst`/`conservative` (lo
decide la regla del estándar §4, nunca el operador); si correr `$qa` (siempre queda como Next
step, nunca se corre inline); más de 3 candidatos (rechazado por diseño). `--record-qa` se
tipea: es un modo posterior a `$qa`.

## Engine — el helper del ledger (llamalo; no lo reimplementes)

`bash ~/webapps/vps-ops-toolkit/scripts/perf/perf-ledger.sh` (contrato y schema:
`config/perf-ledger/README.md`):

- `--show <proyecto> [--candidate=<id>]` → perfil resuelto, `unit=`, `budgets=`, `standard`,
  `candidates=[id:status,…]`, `stale=[…]`, `top3=[…]`, `review3=[…]`, `ledger_orphans`.
- `--profile <proyecto>` → sólo perfil + presupuestos (lo consumen la declaración de cómputo y
  los enganches de otras skills).
- `--record <proyecto> <<'EOF'` → upsert de UN candidato; aplica la máquina de estados (campos
  exigidos por transición; `infra/*` nunca `applied`; `verified` jamás tipeado) y la regla
  anti-métricas (exit 2 ante claves prohibidas o números con unidad en `problem`/`strategy`).
- `--note <proyecto> <<'EOF'` → alta restringida del scout (status forzado a `candidate`).
- `--record-qa <proyecto> --candidate=<id>` → mide `tests_declared` + último reporte de $qa.
- `--refresh <proyecto>` → recalcula `stale` y `ledger_orphans`; no borra.

`--record` admite la evaluación de valor indicada arriba y `deferred-low-value`. El
contexto/decisión los calcula el helper; IDs, métricas y estados QA siguen protegidos.

El helper **calcula** `id`, `date`, `first_seen`, `runs`, `compute_profile`, `standard_version`,
`stale`, `top3` y `review3`: no se tipean en ningún fragmento (exit 2).

## Rol — `perf-scout`, el tomador de notas (dispatch por `subagent_type`)

Un solo subagente, distribuido con los `qa-*` a `.claude/agents/perf-scout.md` de cada
proyecto (canónico `workflows/.user-level/.claude/agents/perf-scout.md`; la primera vez que
aparece `agents/` en un scope hay que reiniciar la sesión). Read-only sobre el proyecto; su
única escritura es `perf-ledger.sh --note`. Se despacha **una vez por corrida**, al cerrar la
Fase 1, en paralelo con las Fases 2–3, con: `project · codebase · profile (id + calibrated_on)
· categories_order · excluded (ids + process + paths de los candidatos de ESTA corrida) ·
inventory (archivos leídos + hits del grep) · scope (performance_paths) · max_notes: 8`.
Devuelve `STATUS: NOTED|NOTHING-NEW|PARTIAL` + `notes:` con `persisted: yes(<id>) | no(<razón>)
| duplicate-of <id>`; el conductor re-emite `--note` por cada `persisted: no` en la Fase 6 y
espera su retorno antes de cerrar (⏸️ declarado si no vuelve). En `--refresh` es el trabajador
principal. **Dispatch resilience** como en `$qa`: un reintento inmediato ante 529, luego ~4 min,
luego ⏸️.

## Safety rails — siempre ON

1. **Modo B: diagnóstico por default.** Sin `--apply` no se escribe nada en el proyecto: ni
   código, ni tests, ni `.testquality.yml`. Modo A aplica por default porque la sesión ya está
   escribiendo ese requerimiento; `--no-apply` lo degrada a diagnóstico.
2. **Sin estándar canónico no hay corrección.** `standard=no-canonical` (no existe
   `workflows/testing/PERFORMANCE_STANDARDS.md` en el toolkit) ⇒ inventario + Next step "definir
   el estándar"; con `--apply`/modo A ⇒ 🚫 REFUSED para la parte de aplicar. `absent`/`stale`
   (la copia del repo falta o difiere) NO bloquea: se contrasta contra el canónico, la fila
   Estándar queda ⚠️ y bajo `--apply` la copia se agrega a `docs/` en la misma rama.
3. **LÍMITES del estándar §1, sin excepción.** Sólo los `paths` del candidato (o el diff del
   requerimiento en modo A); mismo shape de respuesta, mismos datos, mismas reglas; sin
   dependencias nuevas; migraciones **sólo aditivas** y **jamás `manage.py migrate`** desde el
   worktree (el `.env` enlazado apunta a producción: sólo `makemigrations` + `sqlmigrate`).
4. **La infraestructura se observa, no se toca.** systemd, nginx, MySQL, Redis, gunicorn,
   `projects.yml`: categoría `infra/*` = observación con puntero a `docs/capacity-runbook.md`
   y `bootstrap.sh --check`, para el operador. `apply-server-optimization.sh` fue retirado a
   propósito; "subir workers" es el anti-patrón §8.
5. **Evidencia sin producción.** Nunca `curl -w time_total`, nunca `COUNT`/`EXPLAIN`/`shell`
   contra la DB de producción, nunca leer un `.env` (la config se lee en `projects.yml`:
   `cache_redis_db`, `db`, `memory_max`). Lo dinámico sale de pytest (DB de test), de staging/dev,
   o de los reportes del host (`reports/Weekly-Report-*.md`, `silk-reports/*.log`, slow log).
6. **`host_status=wrong-host`** ⇒ `--apply`/modo A abortan 🚫 y nombran el VPS correcto; el
   diagnóstico puede seguir, marcado ⚠️ y declarado en el veredicto.
7. **Protocolo por sesión.** Modo B edita en un worktree propio con rama
   `fix/<DDMMYYYY>-perf-<slug>` cortada de la base resuelta; modo A reutiliza el worktree y la
   rama de la sesión (commit propio, sin PR nuevo si ya hay uno). Jamás `git checkout -b` en
   el clon principal. PR al primer push con `Sesión:`/`Intención:`. **Nunca se mergea.**
8. **La verificación es de `$qa`.** Esta skill no escribe ni corre tests de presupuesto ni se
   "verifica" con mediciones; el único autocontrol es el guard estático del diff (Fase 4). Un
   test que mide tiempo no se escribe nunca (estándar §6).
9. **Máximo 3 candidatos por corrida**; un cupo que no se puede aplicar no se rellena. Lo que
   se ve de paso lo anota el scout.
10. **Ledger sin métricas; reporte inmutable con los números.** Commit propio en `master` del
    toolkit, nunca mezclado con el commit del proyecto.

## Fase 0 — Preflight (dos llamadas; los valores viajan literales en el contexto)

`<proyecto>` es el argumento; si no vino, sale del `project=` de
`bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh status` (o del nombre
del clon). Va **literal** en ambas llamadas — post-`EnterWorktree` Claude rechaza `$(...)`:

```bash
bash ~/webapps/vps-ops-toolkit/scripts/qa/qa-agent.sh --preflight <proyecto>
#   → projdir · registry · production · staging · layers · db · app_reachable · resolved_branch · host_status · pr_state · qa_memory
```
```bash
bash ~/webapps/vps-ops-toolkit/scripts/perf/perf-ledger.sh --show <proyecto>
#   → codebase · ledger · standard · standard_version · profile_id · profile_source · profile_host · work_host ·
#     profile=vcpu,ram_gb,calibrated_on · unit=… workers=… threads=… cpuquota=… memmax=… huey=… ssr=… db=… ·
#     budgets=slots,cpu_req,cpu_ms_api,cpu_ms_page,memmax_mb,worker_mb,req_mb,rows_max,headroom_gb,timeout_s,
#             query_list,query_detail,query_mutation,page_size_max,task_s,payload_kb,bundle_initial_kb,bundle_route_kb,index_rows ·
#     perf_cfg · dataset_ceiling · candidates=[id:status,…] · stale=[…] · top3=[…] · review3=[…] · ledger_orphans
```

Qué se decide con cada clave:

- **Del preflight de `$qa`** (no se reimplementa): `projdir`, `resolved_branch`, `host_status`,
  `pr_state`, `layers`, `db`, `app_reachable`, `qa_memory`. `abstain=yes` NO abstiene esta
  skill; sólo degrada el handoff: sin capa `backend`/`frontend-unit` ⇒ `Handoff QA ⏭️` y el
  estado final de un `--apply` es `applied`, no `qa-pending`. `registry=absent` ⇒ coordenada
  no confiable: `--apply` sólo con confirmación explícita de la rama.
- **Modo**: A si hay requerimiento (texto o sesión con diff); si no, B con picker. `--refresh`
  salta a la Fase 1a + scout y luego a la Fase 6.
- **Candidatos de la corrida**: modo A ⇒ 1–3 registros nuevos (`--record` con `new: true`,
  `status: selected`, `seen_by: perf-pass`) por el camino de código del requerimiento; si el
  `process` ya existe en el ledger, se reutiliza su id (`candidates=`). Modo B ⇒ los ids del
  set elegido; cada uno pasa a `selected` (`--record` mínimo: `candidate`, `status: selected`,
  `report` = el reporte que esta corrida va a escribir).
- **`standard`**: `ok` sigue · `stale`/`absent` ⇒ canónico del toolkit, fila ⚠️ y Next step
  `bash ~/webapps/vps-ops-toolkit/scripts/maintenance/sync-test-quality-core.sh --apply --project=<proyecto>` ·
  `no-canonical` ⇒ rail 2.
- **`stale=[…]`** no vacío ⇒ se declara en la línea ⚙️; los stale sólo se trabajan si el
  operador eligió `review3` (o si están en el set pedido).
- **`ledger_orphans`** se corrigen en la Fase 6 de esta misma corrida (paths nuevos o
  `discarded` con `why_pending`).

Cierra imprimiendo la declaración de cómputo.

## Fase 1 — Inventario (una sola lectura por candidato, dos fuentes)

**1a. Estático.** Por candidato, UN `grep -nE` sobre sus `paths` (o `performance_paths` del
módulo; en modo A, los archivos del diff de sesión más los que llaman), extensiones
py/vue/tsx/jsx/ts/js, sin `*.test.*`, `*.spec.*`, `tests/`, `e2e/`:

```bash
grep -rnE --include='*.py' --include='*.vue' --include='*.tsx' --include='*.jsx' --include='*.ts' --include='*.js' \
  '\.all\(\)|\.objects\.|SerializerMethodField|\bfor .* in .*\.(all|filter)\(|\.count\(\)|len\(.*\.objects|prefetch_related|select_related|only\(|defer\(|annotate\(|Paginator|pagination_class|page_size|iterator\(\)|bulk_(create|update)|@db_task|@task|@periodic_task|shared_task|transaction\.atomic|cache\.(get|set)|cache_page|cached_property|db_index|Meta\.indexes|indexes = |useFetch|\$fetch|useAsyncData|fetch\(|axios\.|onMounted|useEffect|watch\(|computed\(|import\(|defineAsyncComponent|dynamic\(|v-for|\.map\(|loading=|<img' \
  <paths> | grep -vE '\.(test|spec)\.|/tests?/|/e2e/'
```

Luego `Read` UNA vez: las vistas/serializers/tareas/componentes del camino que el grep marcó
(cap orientativo 20 archivos; muchos más ⇒ acotar por `performance_paths`, nunca leer de a
pedazos). Se anotan `file:line` de: querysets sin cota, campos que consultan por instancia,
prefetch/select_related presentes o ausentes, punto de evaluación del queryset, paginación
y su cap, columnas de `filter`/`order_by` y si tienen índice (`Meta`), tareas y su forma de
recorrer tablas, fetch en mount/watchers, imports pesados, listas sin memoización.

**1b. Dinámico (sólo con evidencia reproducible y sin producción).** Correr los
`performance_budget_tests` que toquen el camino (pytest, DB de test); `manage.py sqlmigrate`
para un índice propuesto; `EXPLAIN` / conteo de filas **sólo** con `production=no` (dev) o
contra staging; leer el último `backend/logs/silk-reports/*.log` y el bloque
`## Silk — Queries N+1 y Lentas` / `## Queries Lentas — MySQL` de `reports/Weekly-Report-<host>.md`
si existen; `du -sh` del build (`.output/`, `.next/`) para bundles. Salida: lista `file:line` +
comandos + salidas en texto (van a "Mediciones" del reporte). Sin nada de eso ⇒
`confidence: inferred` y fila `Inventario dinámico ⏭️`; nunca un ❌.

**Al cerrar 1a se despacha `perf-scout`** (Agent, `subagent_type: perf-scout`) con `excluded`
= los candidatos de esta corrida. Sigue la Fase 2 sin esperarlo. En modo delegado, si el
conductor ya hizo inventario, no se vuelve a despachar; si necesita un scout explícito,
éste recibe `IMPROVEMENT_CONTEXT` y devuelve notas sin escribir.

## Fase 2 — Contraste contra el estándar

`Read` UNA vez el estándar (`docs/PERFORMANCE_STANDARDS.md` del proyecto si `standard=ok`; si
no, el canónico), `performance_project_doc` si existe, y las claves `performance_*` de
`.testquality.yml`. Cada rotura de la Fase 1 se vuelve un hallazgo del candidato:

| ID | Categoría | Presupuesto (§2, literal de `budgets=`) | Caso | Severidad | Confianza | Evidencia | Clase |
|---|---|---|---|---|---|---|---|

- **Caso** (regla exacta §4, en orden): (1) `worst` = slots ocupados + dataset al
  `performance_dataset_ceiling` (sin techo: 10× el conteo leído en staging/dev; sin DB:
  `10000 (default-estándar)`); (2) diseñar el fix para `worst` y pasarlo por LÍMITES; (3) si
  exige infra/async/esquema no aditivo/cambio de contrato ⇒ `conservative` (carga actual ×2 del
  traffic report o `2 usuarios concurrentes (default-estándar)`; dataset actual) + `escalation`;
  (4) si ni así entra ⇒ `diagnosed` + `why_pending: fuera-de-LÍMITES`.
- **Severidad** (§4): bloqueante · mayor · menor. **Confianza**: `measured` sólo con `cmd:` cuya
  salida está en el reporte; si no, `inferred`. **Esfuerzo**: S · M · L.
- **Clase:** `corregible` (categoría con `--apply`, dentro de LÍMITES y de `paths`) ·
  `observación` (infra, cambio funcional, archivo compartido con otro dueño ⇒ puntero) ·
  `no-cubierto` (⇒ §7: observación + propuesta de extensión al canónico).

Los `assumptions` se escriben acá, con fuente, copiando los valores literales de `budgets=`
y del perfil: `"slots=2 workers×1 thread (systemd)"`, `"cpu_req=0.20 core/request (profile)"`,
`"dataset_ceiling=200000 filas app.Model (declarado)"`.

## Fase 3 — Propuesta

Cerrar acá `value_assessment` por candidato con la evidencia de la Fase 2 y la política
común. Sólo los elegibles pasan a aplicar. Los diferidos conservan su motivo; los
inciertos necesitan evidencia. Si no hay elegibles, saltar a registro y explicar dónde
conviene parar sin crear commits vacíos ni enviar mejoras no aplicadas a QA como hechas.

Por hallazgo `corregible`: qué cambia (técnica del estándar §1/§3) y en qué `file:line`, el
`budget` como la aserción que `$qa` escribirá ("`Q(1 fila) == Q(50 filas) y ≤ 6`", "la tarea
procesa por lotes y ninguna transacción abarca el barrido", "el chunk inicial deja de incluir
`<módulo>`"), riesgo (¿el archivo lo usa otro proceso? ⇒ observación con dueño; ¿anotación
sobre otra relación multivaluada? ⇒ `distinct`/subquery), y `escalation` si el caso es
`conservative`. Agregar la constante nombrada del presupuesto (`MAX_<PROCESO>_QUERIES`) o un
`data-testid` es parte de la propuesta cuando habilita el guion. Las observaciones van en
lista aparte con su razón; las `infra/*` con el puntero al runbook. En diagnóstico, de acá se
salta a la Fase 5 (sin escribir).

## Fase 4 — Aplicar (modo A por default; modo B sólo con `--apply`)

Precondiciones: `standard≠no-canonical` · `host_status≠wrong-host` · identidad git
(`git var GIT_COMMITTER_IDENT`; si falla, `user.name`/`user.email` repo-local, nunca
`--global`) · evaluación de valor vigente y elegible · tree limpio en el worktree de sesión.
**Modo A** reutiliza el worktree/rama de la sesión.
**Modo B** crea el suyo por el protocolo por sesión (`git-branch-protocol`):

```bash
# pre-entry: corre en el clon principal, antes de EnterWorktree
SLUG="<top3|review3|candidate-slug>"
OUT="$(bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh" \
       create fix "perf-$SLUG")"
echo "$OUT"               # imprime worktree=/branch=/base=/pr_base=
WT="$(sed -n 's/^worktree=//p' <<<"$OUT")"
cd "$WT" && git rev-parse --show-toplevel   # debe caer bajo ~/webapps/.wt/
```

Claude Code: `EnterWorktree path=$WT` con el path literal impreso; Codex: el `cd` de arriba
basta. Ya adentro, UN comando simple por llamada y los valores **literales**.

**Top 3 = tres mini-ciclos secuenciales** (Fase 1 → 2 → 3 → 4 por candidato, en el orden del
set), **UN commit por candidato**, **UN PR por corrida**. Edición: sólo los `file:line` de la
propuesta de ESE candidato; sin dependencias; sin tocar `*.test.*`, `*.spec.*`, `tests/`,
`requirements*`, `package.json`, `settings*.py` fuera del bloque `CACHES`, `config/`, units,
nginx. Un índice: `Meta.indexes` + `makemigrations` + `sqlmigrate` (la salida va al reporte);
nunca `migrate`. Si `standard=absent|stale`, se copia el canónico a
`docs/PERFORMANCE_STANDARDS.md` en la misma rama. Si `.testquality.yml` no tiene ninguna clave
`performance_`, se anexa el bloque comentado del estándar §9 descomentando sólo lo que la
corrida necesitó (p. ej. `performance_dataset_ceiling`).

**Guard estático antes de cada commit:** `git diff --name-only` ⊆ `paths` del candidato ∪
{migración aditiva nueva, `docs/PERFORMANCE_STANDARDS.md`, `.testquality.yml`} y sin los
patrones prohibidos; si falla ⇒ `git checkout -- <archivo>`, el candidato queda `diagnosed` con
`why_pending` y sigue el siguiente (el cupo NO se rellena). No se corre la app desde el
worktree ni se "verifica" con curl: el dev server sirve el clon principal o staging.

```bash
git add <paths del candidato> <migración> <docs/PERFORMANCE_STANDARDS.md> <.testquality.yml>
```
```bash
git commit -m "perf(<hoja>): <process> — <estrategia, ≤60 chars> [P-<cat>-NN]"
```

Tras el último candidato (modo B; en modo A el push/PR es el de la sesión):

```bash
git push -u origin fix/<DDMMYYYY>-perf-<slug>
```
```bash
gh pr create --base <BASE literal> --title "perf: <proyecto> — <set> (<N> candidatos)" --body "Sesión: <sesión>
Intención: perf-pass <set> — <ids>, perfil <profile_id> <vcpu> vCPU / <ram_gb> GB

<P-… → archivo, por línea; caso y presupuesto de cada uno>"
```

El body es texto literal entre comillas dobles con saltos de línea reales — **nunca**
`--body "$(printf …)"`. `PR URL:` va al reporte. Sin merge.

## Fase 5 — Handoff a $qa (guion + puntero)

**5a. Guion de tests de presupuesto** — bloque ```` ```brief-perf ```` con la forma del
Architect de `$qa` (`~/.claude/agents/qa-architect.md`), un ítem por cambio aplicado y uno
por hallazgo bloqueante/mayor aunque no se haya aplicado; conductual (actúa + afirma un valor
concreto de conteo/tamaño + nombra el bug); **nunca una aserción de tiempo**; ubicado en la
capa dueña (`backend` para queries/tareas/índices; `frontend-unit` para stores/fetch;
`frontend-e2e` sólo si el comportamiento es de navegación):

```brief-perf
P1 · candidate: P-backend-queries-03 · behavior: GET /api/admin/documents/?folder=<id> lista documentos con owner_name · budget: Q(1 fila) == Q(50 filas) y <= 6 · case: worst (dataset_ceiling=200000 / slots=2)
   · layer: backend · target: backend/content/tests/views/test_document_navigation.py (extender TestDocumentListBudget)
   · assertion: with CaptureQueriesContext(connection) as one: client.get(url + '?page_size=1'); with … as fifty: client.get(url + '?page_size=50') → len(fifty) == len(one) and len(fifty) <= MAX_DOCUMENT_LIST_QUERIES (6)
   · bug: regresión del N+1 en DocumentSerializer.get_owner_name — una query por fila (P-backend-queries-03)
   · evidence: backend/content/serializers/documents.py:88 · backend/content/views/documents.py:141 (select_related agregado, commit <sha>) · cmd: pytest backend/content/tests/views/test_document_navigation.py -k budget -q
   · traps: en TestCase el conteo incluye SAVEPOINT — función con fixture db (idioma test_proposal_detail_queries.py:24-35) · la fixture crea 50 owners DISTINTOS o el prefetch cache oculta el N+1
```

Cierra con `PRECONDITIONS: none | budget-test-idiom required (backend bounded)` (si el
proyecto no tiene ningún guard de presupuesto, el estándar §6 provee el snippet) y
`HANDOFF: $qa <proyecto> --apply --layers=backend[,frontend-unit][,e2e]`.

**5b. Puntero para `$qa`** (sólo modo A / `--apply`; toolkit): una línea en `watchlist` de
`config/qa-memory/<codebase>.yml` — `"PERF pending (<fecha>): presupuestos [<ids>] declarados
por perf-pass para <module>; guion brief-perf en docs/audits/<reporte>"` (respetar el cap de
10; la memoria sólo ADD work). `$qa` la lee en su Fase 0 y el Architect toma el guion como
hipótesis a re-verificar. `--record-qa` la retira.

**5c.** Next step literal: `$qa <proyecto> --apply --layers=<capas>`. En modo A es el mismo
`$qa` que $implement ya sugiere al cierre: absorbe el guion y su PR se apila sobre la rama
de la sesión. `$qa` escribe los tests de presupuesto (Engineers), los corre (Verifier) y
devuelve su veredicto; el `tests_declared` del ledger son los archivos `target` del guion.

## Fase 6 — Registro + reporte (en cualquier modo; registrar no es escribir en el proyecto)

1. **Reporte de la corrida** (Write, toolkit):
   `docs/audits/<YYYY-MM-DD>-<proyecto>-perf-<slug>.md` (`<slug>` = `top3` / `review3` /
   `catalog` / el módulo del requerimiento; misma fecha ⇒ sufijo `-2`; nunca `.bak.md`),
   secciones fijas: Alcance y perfil de cómputo (la línea ⚙️ literal) · Preflight (estándar,
   coordenada, `budgets=`) · Inventario (archivos leídos, hits) · Hallazgos por categoría
   (tabla de la Fase 2) · Supuestos y caso por candidato · **Mediciones** (único lugar con
   números: salidas de pytest/`sqlmigrate`/`EXPLAIN` en staging/`du`, líneas de Silk/slow log)
   · Cambios aplicados (archivo:línea, commit, PR URL) · Observaciones y escalaciones (infra →
   runbook) · Guion brief-perf · Beneficio y criterio para parar (por alcance evaluado) ·
   Pendientes con razón · Propuesta de extensión al estándar (si
   hubo `no-cubierto`). El reporte es inmutable; el veredicto de QA vive en el ledger.
2. **Ledger** — `--record` por candidato trabajado, sólo con las claves que el helper acepta
   (`config/perf-ledger/README.md`; `date`/`runs`/`compute_profile`/`standard_version` los
   calcula él):

```bash
bash ~/webapps/vps-ops-toolkit/scripts/perf/perf-ledger.sh --record <proyecto> <<'EOF'
candidate: P-<cat>-NN                              # o new: true + category para un alta de modo A
status: <diagnosed|applied|qa-pending|blocked|deferred-low-value|discarded>
report: docs/audits/<YYYY-MM-DD>-<proyecto>-perf-<slug>.md
module: <módulo>
process: "<endpoint / tarea / ruta, como lo nombra el operador>"
paths:
  - <archivo>
  - <archivo>
severity: <bloqueante|mayor|menor>
confidence: <measured|inferred>
effort: <S|M|L>
value_assessment:
  benefit: <material|minor|unknown>
  effort: <S|M|L>
  change_risk: <low|medium|high>
  mandatory: <true|false>
  reason: "<utilidad y costo del cambio; sin métricas>"
  evidence: ["<file:line o sección del reporte>"]
case: <worst|conservative>
problem: "<mecanismo, sin números con unidad>"
strategy: "<qué cambia y dónde, sin números con unidad>"
assumptions:
  - "slots=2 workers×1 thread (systemd)"
  - "dataset_ceiling=200000 filas app.Model (declarado)"
budget: "<la aserción del guion>"
evidence:
  - "<archivo>:<línea>"
  - "cmd: pytest <ruta> -k budget -q"
branch: fix/<DDMMYYYY>-perf-<slug>                 # sólo applied/qa-pending
commit: <sha>                                      # sólo applied/qa-pending
pr: <url>                                          # sólo applied/qa-pending
tests_declared:                                    # sólo qa-pending: los target del guion
  - <archivo de test>
why_pending: "<razón>"                             # sólo blocked/discarded/diagnosed-sin-aplicar
escalation: "<cambio fuera de LÍMITES que alcanzaría worst>"   # sólo conservative
observations:
  - "infra/gunicorn: 2 workers en <N> cores — observación, docs/capacity-runbook.md"
EOF
```

   Las notas del scout con `persisted: no` se re-emiten con `--note` (mismo formato que el
   agente). Los `ledger_orphans` se resuelven (paths nuevos o `discarded` + `why_pending`).
3. **Commit del toolkit** (`git -C <toolkit>` está permitido desde un worktree de proyecto: es
   OTRO repo). Ledger + reporte + `qa-memory` (si la 5b escribió el watchlist) en el MISMO
   commit:

```bash
git -C ~/webapps/vps-ops-toolkit add config/perf-ledger/<codebase>.yml docs/audits/<reporte>.md config/qa-memory/<codebase>.yml
```
```bash
git -C ~/webapps/vps-ops-toolkit commit -m "docs(perf): record <proyecto> <ids> <status>"
```

Commit propio en `master` del toolkit, nunca mezclado con el commit del proyecto; el push
sigue la cadencia normal (`$git-commit`).

## `--record-qa` — registrar el veredicto de $qa (modo posterior, se tipea)

```bash
bash ~/webapps/vps-ops-toolkit/scripts/perf/perf-ledger.sh --record-qa <proyecto> --candidate=<id>
#   mide: tests_declared (present|absent|no-guard) + último docs/audits/<fecha>-<proyecto>-qa.md posterior a la corrida
#   → qa: {status, verdict, tests, rejected_because}; verified sólo si todo present ∧ veredicto ≠ 🔴 ∧ sin rechazos
```

`qa.status` es **calculado**, nunca tipeado; `regressed` aparece cuando un `verified` recibe un
veredicto 🔴 posterior. Después: retirar la línea `PERF pending` del `watchlist` de qa-memory y
commit del toolkit `docs(perf): record <proyecto> <id> qa=<status>`.

## Contrato con $qa — qué se entrega, qué se espera

| Se le entrega a $qa | Se espera de vuelta |
|---|---|
| Bloque ```brief-perf `P1..Pn` con presupuesto, aserción de conteo/tamaño y evidencia `file:line` (en el reporte; $qa lo re-verifica como hipótesis, jamás lo copia) | Veredicto de $qa: 🟢 / 🟡 / 🔴 (línea `**Veredicto:**` de su reporte) |
| Puntero en `watchlist` de qa-memory apuntando al guion | Conservación por ítem: `done` / `blocked(brief-conflict)` / `abstained`, con razón |
| Cambios aplicados: archivo:línea, commit, PR URL, rama (base para apilar el PR de QA) | Tests de presupuesto en la capa dueña con la constante nombrada `MAX_*_QUERIES` / `toHaveBeenCalledTimes` |
| Observaciones e `infra/*` (para que $qa NO las testee) | `rejected_because` del Verifier si un test es verde-pero-vacío o mide tiempo |

## Errores comunes (señales de alarma — medidas en la línea base sin skill, 2026-09-14)

- "Optimizo primero y después vemos en qué máquina corre" → la línea ⚙️ va ANTES de la
  Fase 1; los presupuestos salen de `budgets=` del helper, no de la intuición.
- "Mido con `curl -w time_total` p50/p95 contra producción, antes y después" → evidencia
  prohibida (§5): sin control de carga ni dataset. El presupuesto se afirma por conteo en un
  test que escribe $qa.
- "`SELECT COUNT(*)` / `EXPLAIN` contra la DB para saber el techo" → sólo staging/dev; el
  `.env` del worktree apunta a producción. Sin DB: `10x-actual` o `default-estándar`, declarado.
- "Leo el `.env` para ver si Redis/Silk está configurado" → jamás; `projects.yml`
  (`cache_redis_db`, `db`, `memory_max`) y la unit de systemd son la fuente.
- "El endpoint ya está optimizado, no hay mejora obvia" → el contraste es contra los
  presupuestos derivados (queries/req, `rows_max`, `req_mb`), no contra la sensación de que
  "alguien ya hizo una pasada".
- "Aplico D1, D2, D3 y D4 juntos: backend, índice y frontend" → ≤3 candidatos, un commit por
  candidato, cada uno con su id; lo demás lo anota el scout.
- "Subo gunicorn a 4 workers / cambio nginx / activo Redis como cache" → `infra/*` es
  observación con puntero al runbook; el helper rechaza `applied` ahí.
- "Instalo django-cachalot y listo" → sin dependencias nuevas (LÍMITES).
- "Quito el campo / pagino la lista para que vuele" → cambio de contrato ⇒ observación.
- "Escribo los tests de presupuesto yo y ya quedó verificado; el CI lo caza" → los escribe y
  corre $qa a partir del guion; esta skill entrega `brief-perf` y Next step.
- "`git checkout -b perf/…` en el clon" → `session-worktree.sh create fix perf-<slug>` +
  `EnterWorktree`; en modo A, el worktree de la sesión.
- "Reporte p50 antes X ms / después Y ms como cierre" → el cierre es la tabla de dimensiones
  + Next steps; los números viven sólo en "Mediciones" del reporte, si se midieron hoy.
- "Anoto en el fragmento `date`, `compute_profile`, `standard_version`, `runs`" → los calcula
  el helper (exit 2); el fragmento lleva sólo las claves del README.
- "Le pregunto al operador si el perfil vigente es el correcto" → el perfil no se pregunta:
  se imprime; recalibrar es editar `config/perf/compute-profile.yml`.
- "Cuatro confirmaciones en texto con defaults" → UNA AskUserQuestion fusionada (Q1+Q2); un
  dato faltante posterior, en texto y una sola vez.
- "Reutilizo los números del reporte de julio" → contexto histórico etiquetado en el reporte,
  nunca línea base ni evidencia; se re-inventaría.
- "El `verified` viejo lo bajo a `regressed` por las dudas" → `regressed` exige un test en
  rojo (`cmd:`); un snapshot viejo es `stale` (lo marca `--show`) y va a `review3`.
- "El cupo quedó en 2, agrego el siguiente" → el cupo no se rellena; el siguiente sale del
  `top3` de la próxima corrida.
- "Corro `manage.py migrate` para probar el índice" → sólo `makemigrations` + `sqlmigrate`;
  el `migrate` es del deploy.
- "Dejo el reporte en `docs/audits/` del proyecto" → el reporte y el ledger viven en el
  toolkit; el proyecto recibe código, la copia del estándar y `.testquality.yml`.
- "Un `assert duration < 0.2`" → un test que mide tiempo no se escribe (flaky por diseño);
  conteo de queries, de fetch o de filas.

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos (gating
$output-protocol §4), UNA AskUserQuestion. `(Recommended)` va en la fila 1 tras un
`--apply`/modo A y en la fila 2 tras un diagnóstico:

Sólo ofrecer aplicar o seguir si quedan candidatos elegibles. Si el alcance es
suficiente, explicar el criterio de parada y su condición de reapertura; no proponer
otra pasada sobre el mismo alcance. En modo delegado, el conductor emite estas acciones.

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| QA de los presupuestos | $qa escribe y corre los tests de presupuesto del guion; commitea en su propia rama (apilada) | `$qa <proyecto> --apply --layers=<capas>` |
| Aplicar la propuesta | edita los `paths` de los candidatos en rama de sesión + PR (sólo tras diagnóstico) | `$perf-pass <proyecto> --candidate=<ids> --apply` |
| Siguiente top 3 | diagnóstico del próximo set del ledger | `$perf-pass <proyecto> --top3` |
| Reporte para el cliente | reporte no técnico de esta pasada | `$client-report rendimiento de <proceso> en <proyecto>` |

Nunca como fila: merge del PR (`$merge-queue`/operador va en Next steps; `$merge-when-green`
es operator-only), deploy, git destructivo, cambios de infra — blocklist §4.

## Output final

Reportar siguiendo $output-protocol. Plantilla específica de esta skill (el veredicto es
sobre ESTA corrida; el de $qa es una fila aparte):

```markdown
🟢 perf-pass OK — <proyecto> / <set|requerimiento> (<diagnóstico|aplicado>)

| Dimensión | Estado | Detalle |
|---|---|---|
| Perfil de cómputo | ✅ | <profile_id> <vcpu> vCPU / <ram_gb> GB · calibrado <fecha> · fuente <server> (⚠️ fleet_default sin entrada · ⚠️ N stale) |
| Alcance | ✅ | N candidatos [ids] · ledger: N candidatos · próximo top3 [ids] |
| Estándar | ✅ | docs/PERFORMANCE_STANDARDS.md v<x> · sync ok (⚠️ stale/absent → canónico · 🚫 no-canonical) |
| Inventario estático | ✅ | N archivos leídos 1 vez · N hits |
| Inventario dinámico | ✅ | pytest presupuesto N · sqlmigrate · silk/slow log leídos (⏭️ sin app ni señales) |
| Hallazgos por categoría | ℹ️ | bloqueante N · mayor N · menor N — queries N · tasks N · assets N |
| Beneficio | ℹ️ | elegibles <ids> · diferidos por poco retorno <ids> · falta evidencia <ids> · alcance suficiente <alcance y condición de reapertura> |
| Caso y supuestos | ✅ | worst N · conservative N (escalación en observaciones) |
| Cambios aplicados | ✅ | N/N corregibles · commits <sha…> · PR #n (⏭️ diagnóstico · ⚠️ N bloqueados por guard) |
| Observaciones (infra) | ℹ️ | N → docs/capacity-runbook.md (operador) |
| Handoff QA | ✅ | guion P1..Pn · watchlist (⏭️ diagnóstico: guion listo · ⏭️ sin capa) |
| Scout | ✅ | N anotados · N duplicados · N re-emitidos (⏸️ sin retorno) |
| Resultado QA | ⏭️ | lo emite $qa (Next steps); se registra con --record-qa |
| Registro | ✅ | ledger <ids>=<status> · reporte docs/audits/<…> · commit toolkit <sha> |
| Pendientes con razón | ℹ️ | P-…-03 fuera-de-LÍMITES → escalación · P-…-05 no-cubierto |

## Next steps
- `$qa <proyecto> --apply --layers=<capas>` — guion brief-perf en `docs/audits/<reporte>`; PR de QA apilado sobre `<rama>`
- `$perf-pass <proyecto> --candidate=<id> --record-qa` — tras $qa: registra el veredicto medido
- `$perf-pass <proyecto> --top3` — siguiente set del ledger
- (operador) `docs/capacity-runbook.md` — observaciones infra: <resumen>
- (operador, tras QA) `$merge-queue` — drenar el PR; el worktree se retira con `$all-in-base` cuando el PR esté mergeado
```

Casos de veredicto:

- 🟢 corrida completa: perfil resuelto del host real, estándar vigente, inventario hecho,
  corregibles aplicados (o propuestos en diagnóstico), guion escrito, ledger registrado. En
  diagnóstico, N hallazgos NO bajan el veredicto: son el producto.
- 🟡 `profile_source=fleet_default` con `server:` declarado; estándar `stale`/`absent`;
  inventario dinámico ⏭️ (todo `inferred`); corregibles bloqueados por el guard;
  `conservative` usado; `registry=absent`; sin capa de tests (handoff ⏭️, estado `applied`);
  diagnóstico en `wrong-host`; scout `PARTIAL`.
- 🔴 guard del diff disparado sin poder aislar; push/PR fallido; helper del ledger ausente o
  con error; `--record` rechazado por métricas tipeadas sin corregir.
- 🚫 `--apply`/modo A sin estándar canónico, o en `wrong-host` (el diagnóstico se entrega igual).
- ⏸️ scout sin retorno tras los reintentos; sin app, sin señales del host y sin `paths` derivables.
- ⏭️ candidato/proceso no identificable tras la pregunta en texto (no se escribe nada).
