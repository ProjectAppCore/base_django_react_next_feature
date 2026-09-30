---
name: vuln-audit
description: "Audita vulnerabilidades y dependencias en backend (Python) y frontend (npm). Default report-first: escanea (pip-audit + npm audit + outdated) y arma el plan de bumps SIN escribir nada. Con --apply aplica en batch los updates patch+minor del plan respetando pins, verifica con checks mínimos y deja hasta 3 commits limpios en un PR. Con --upgrade moderniza TODO secuencialmente por nivel semver (patch, minor y cada major en su propio commit), pusheando cada commit solo y avanzando sólo con su CI verde; un major que no cierra con esfuerzo acotado se revierte y queda diferido en el reporte. Nunca mergea."
argument-hint: "[backend|frontend] [--apply (patch+minor) | --upgrade (secuencial)] [contexto VULN_CANDIDATE + IMPROVEMENT_CONTEXT para delegación acotada] # vacío = auditoría de ambas"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, AskUserQuestion, EnterWorktree
---

## Cuándo usar cuál (familia de auditoría)

| Skill | Úsala cuando | Cadencia típica |
|---|---|---|
| `/full-audit` | Veredicto integral 🟢/🟡/🔴 del VPS o del fleet (`--all`): configs, drift, envs, timers, huérfanas, integridad, health, email — 15 fases automatizadas, ~4 min | Post-cambio grande, post-incidente, trimestral |
| `/server-diagnostic` | Informe profundo por las 15 buenas prácticas con score y recomendaciones por proyecto — más narrativo y granular que full-audit | Semanal automático (cron) / a demanda |
| `/vuln-audit` | Dependencias y CVEs de UN proyecto (pip + npm): default arma el plan sin tocar nada; `--apply` aplica patch+minor en batch; `--upgrade` moderniza todo (majors incluidos) commit a commit con CI verde por commit | Por proyecto: mensual o ante CVE; `--upgrade` trimestral o al planificar una modernización |

Se orquestan en UNA sola dirección: `/deploy-and-check` (manual-only) corre el **motor** de `/server-diagnostic` al cierre de cada deploy (modo consumidor, read-only: sin email, sin histórico, `.md` aparte) y sugiere `/vuln-audit` cuando su sonda de dependencias lo amerita; `/full-audit` NO corre a las otras dos y **ninguna** skill auto-invoca `/deploy-and-check`.


# vuln-audit — Vulnerability & Dependency Audit (multi-stack)

## Beneficio y vulnerabilidades obligatorias

Aplicar `workflows/improvement/IMPROVEMENT_STANDARDS.md` al trabajo discrecional de
modernización: estar `outdated` por sí solo no demuestra un beneficio. Elegir mejoras
materiales con evidencia, o menores sólo con esfuerzo `S`, riesgo `low` y utilidad
concreta. Modernización marginal costosa ⇒ `deferred-low-value`; beneficio desconocido
⇒ `needs-evidence`, no «suficiente». Guardar razón/contexto y referencias a reportes,
sin convertir versiones o conteos de CVEs en métricas persistidas del ledger de mejoras.

Una vulnerabilidad conocida, secreto expuesto, fallo de permisos/autenticación o riesgo
de pérdida de datos demostrado **no se posterga silenciosamente por bajo retorno**.
Si el arreglo viola un pin, exige major o cambia el contrato, queda `blocked`/`remaining`
con la causa y el camino de resolución; las restricciones de esta skill siguen vigentes.
No forzar el bump ni declarar el frente resuelto. Cuando la superficie escaneada carece
de obligaciones pendientes y sólo restan bumps de poco retorno, explicar «Conviene parar
en dependencias para <alcance>: <evidencia>; revisar si cambia <condición>» sin installs
o commits de reporte vacíos. Scanner ausente o superficie sin auditar no prueba suficiencia.
`--upgrade` explícito conserva su selección y secuencia autorizadas; reportar la
recomendación económica sin recortar en silencio la modernización pedida por el operador.

## Delegación acotada por security-pass

[[security-pass]] puede delegar UN candidato de dependencias mediante dos bloques de
contexto. No son flags ni modos nuevos de pip/npm:

```yaml
IMPROVEMENT_CONTEXT:
  conductor: improvement-pass # security-pass si es la skill principal
  round_id: <id de ronda>
  project: <proyecto>
  codebase: <codebase>
  projdir: <worktree de sesión absoluto>
  branch: <rama de sesión>
  base: <base resuelta>
  candidate_ids: [<id de seguridad asignado>]
  allowed_paths: [<paths de este candidato>]
  mode: apply # check para sólo escanear
  owns_git: conductor
VULN_CANDIDATE:
  surface: frontend # backend para Python
  packages:
    - name: <paquete>
      current: <versión actual confirmada>
      target: <versión exacta propuesta>
  advisories: [<CVE/GHSA u otros IDs conocidos>]
  allowed_paths: [<manifest y lockfile o requirements asignados>]
```

Contrato con precedencia sobre las fases de batch/landing y los menús independientes:

1. Validar `session-worktree.sh status`, proyecto/remote, rama/base y pertenencia de la
   sesión/PR al conductor; tree limpio antes de aplicar y paths del descriptor incluidos
   en los autorizados. Descriptor incompleto, versión actual distinta o rama ajena ⇒
   `blocked`, sin mutaciones. Sin ambos bloques, no asumir delegación: rigen los modos
   independientes. En la ronda combinada este candidato consume uno de los tres cupos
   globales, no habilita tres nuevos candidatos de dependencias.
2. Ejecutar la auditoría read-only en la superficie asignada y verificar advisories,
   versiones, pins, constraints, peers, Node/Python y alcance semver. Otros paquetes
   encontrados se devuelven como notas, sin actualizar. Un scanner ausente o un scan
   fallido degrada/bloquea el diagnóstico; no significa «sin vulnerabilidades».
3. En `mode=apply`, aplicar **sólo los targets exactos del descriptor**, permitidos bajo
   las reglas de patch+minor existentes. Frontend: editar los paquetes seleccionados
   (directos o overrides transitivos justificados por la vuln), resolver lockfile con
   el Node autorizado y conservar overrides. Backend: editar sólo los pins seleccionados
   y resolver dentro del venv aislado del worktree. No ejecutar los batches generales
   `npm audit fix`, `npm-check-updates -u` ni actualizar el resto de `requirements.txt`.
   Los cambios transitivos necesarios se explican como cierre del mismo candidato;
   un cambio de paquete ajeno sin esa necesidad se bloquea/aisla, no se acepta de paso.
4. Major, `0.x` que cambia minor, feature release de Django, pin incompatible o peer
   irresoluble ⇒ `blocked`/`remaining` con causa y recomendación de una modernización
   explícita. La delegación no activa `--upgrade` ni cambia sus topes/gates. Una CVE
   conocida sigue siendo obligación pendiente, no un diferido económico.
5. Ejecutar únicamente los checks mínimos apropiados de esta skill sobre lo cambiado;
   no confundir `collect-only`/build/audit con tests conductuales ejecutados. Devolver
   diff, paquetes antes/target, advisories todavía presentes, evaluación de valor,
   salidas de checks y guion `brief-security` por candidate ID para [[qa]]. El conductor
   integra Git/reporte/registros y ejecuta la única etapa de QA. No escribir
   `audit-report.md` sobre el reporte independiente previo, no crear otra rama/worktree,
   no commit/push/PR ni QA inline. En `mode=check` devolver diagnóstico sin editar.

## Goal
Replicar de forma automática el flujo manual de auditoría que vive en `audit-report.md` de los proyectos del repo, en tres niveles:

- **Default (report-first, read-only):** escanear vulns + outdated y construir el **plan de bumps** como tabla (paquete · versión actual → propuesta · severidad · tipo patch/minor/major · unidad · riesgo), **sin escribir NADA** — ni archivos, ni installs sobre el proyecto, ni commits.
- **`--apply` (o selección en el menú post-reporte):** aplicar en batch los bumps **patch+minor** del plan dentro del major actual respetando pins existentes, verificar con checks mínimos y dejar **hasta 3 commits separados** en la rama de trabajo (frontend deps → backend deps → reporte), con push + PR al final.
- **`--upgrade` (modernización secuencial):** llevar TODAS las dependencias directas de las superficies pedidas a la última versión que permiten los constraints, en UN solo PR, con **un commit por unidad semver** (batch patch → batch minor → cada major en su propio commit), pusheando cada commit solo y avanzando **únicamente con su CI verde**. Un major que no queda verde con esfuerzo acotado se revierte (`git revert`, nunca force push) y queda diferido en `audit-report.md` con la causa. El CI del PR es la verificación; lo local es smoke.

## Inputs
- `$ARGUMENTS` (opcional). Valores aceptados (combinables):
  - vacío → auditar `backend/` **y** `frontend/`.
  - `backend` → solo Python.
  - `frontend` → solo npm.
  - `--apply` → además de auditar, aplicar en batch los bumps patch+minor del plan (fase de escritura). Sin él ni `--upgrade`, la corrida es **solo auditoría**.
  - `--upgrade` → modernización secuencial (ver `## Modo --upgrade`). **Excluyente con `--apply`**: si vienen los dos, abortar con «`--apply` y `--upgrade` son excluyentes: elegí uno». Combinable con `backend`/`frontend`: restringe el loop a esa superficie; worktree, rama y PR son los mismos (`deps-upgrade`), así que una corrida posterior con la otra superficie los reutiliza y el PR termina cubriendo ambas.
- Cualquier otro valor: abortar con mensaje pidiendo uno de los aceptados.

## Constraints (no negociables)
- **Default read-only.** Sin `--apply`/`--upgrade`, la skill NO modifica nada: ni `package.json`/`package-lock.json`, ni `requirements.txt`, ni `audit-report.md`, ni commits, ni ramas. Solo snapshots a `/tmp` y el plan en la respuesta.
- **Branching (solo modos mutantes):** sigue el protocolo por sesión: worktree propio bajo `~/webapps/.wt/<repo>/` — slug `vuln-audit` para `--apply` (rama `chore/<DDMMYYYY>-vuln-audit`) y slug `deps-upgrade` para `--upgrade` (rama `chore/<DDMMYYYY>-deps-upgrade`) — cortado de la BASE que resuelve la coordenada (`resolved_branch` si hay release activa vía `pr_state=single`; si no, la default del repo — **nunca** la default a secas ignorando la coordenada) vía `session-worktree.sh create chore <slug>`; nunca checkout de ramas ajenas ni rama nueva en el clon principal. Si la sesión YA tiene su worktree/rama de un turno anterior, se reutiliza. Detalle operativo en la Fase 0.
- **Push + PR al primer push** (tmpl §9, con `Sesión:`/`Intención:` en el body); la skill PARA con el PR abierto — el merge es del operador/`/merge-queue`, nunca de esta skill. En `--apply` el push va al final; en `--upgrade`, con el primer commit.
- **Working tree debe estar limpio** antes de aplicar (`git status` sin cambios). Si no lo está, abortar el modo mutante; la auditoría read-only puede correr igual (no toca el tree).
- **Alcance por modo.** `--apply`: **solo patch + minor** dentro del major actual. `--upgrade`: los majors entran **únicamente como unidad propia** (un paquete o grupo lockstep por commit), jamás dentro de un batch. En ambos modos `0.x → 0.y` (y `0.x → 1.x`) **es major**, y **Django cuenta cada *feature release* como major** (`6.0 → 6.1`, `6.1 → 6.2`: cambian el soporte de bases de datos y quitan APIs aunque no cambie el primer número; sólo `X.Y.Z → X.Y.W` es patch) — `--apply` la salta, `--upgrade` la trata como unidad framework con el gate de la base de producción. **Nunca** `npm audit fix --force`.
- **Respetar pins y constraints documentados:** `requirements.txt` con `<X.Y` o `>=A,<B`, los comentarios inline del propio `requirements.txt`, los constraints de `CLAUDE.md`/`AGENTS.md` y el `node_version` de producción en `projects.yml`. Un bump que los viole se salta y se reporta; nunca se fuerza ni se edita el constraint.
- **Venv aislado en el worktree (modos mutantes).** El venv del clon principal es el del servicio en **producción** y `session-worktree.sh` no lo enlaza a propósito. Toda instalación de Python en un worktree va a `backend/.venv` creado DENTRO del worktree (`python3 -m venv backend/.venv`, gitignored); jamás `source` de un venv fuera del worktree, jamás `pip install` con el pip del clon principal. El modo read-only usa el venv desplegado sólo para leer y **nunca instala un scanner faltante**: el build tipado de dependencias instala `pip-audit>=2.7,<3`; si una instalación anterior no lo trae, la auditoría reporta `degraded: scanner missing` y pide regenerar ese venv mediante el deploy/operación tipada, sin autocurarlo fuera de una operación.
- **Sin base de datos desde el worktree.** `backend/.env` del worktree es un enlace al `.env` de PRODUCCIÓN (en mimittos apunta al MySQL real). Verificación local backend = `pip check` + `python manage.py check` + `pytest --collect-only -q`, nada más; un slice de tests corre SÓLO si `backend/pytest.ini` declara un `settings_test` (sqlite) o si los settings del proyecto leen el motor del entorno (linaje base_feature: `DJANGO_DB_ENGINE`) y el comando lo fuerza a sqlite (`DJANGO_DB_ENGINE=django.db.backends.sqlite3`). Nunca `manage.py migrate`, nunca tests ni `manage.py` con `DJANGO_ENV=production`/settings de producción desde el worktree — **única excepción**, sólo en `--upgrade` y sólo para un major de Django o `mysqlclient`: `manage.py check --database default` con el selector de producción, que abre la conexión de sólo lectura y corre los checks del backend MySQL que el CI (sqlite) no puede ver; jamás `migrate`, `shell`, `dbshell` ni tests con esos settings. La suite completa la corre el CI.
- **Nunca correr la suite completa** de tests en local (regla "never run the full suite" de los `CLAUDE.md`): en `--apply` sólo `pytest --collect-only` + el slice sqlite si existe; en `--upgrade` la suite la corre el CI de cada commit y lo local es smoke de ≤3 comandos por unidad.
- **`0.x → 0.y` es major también para `npm-check-updates`:** la corrida `--target minor` lleva `--reject` con la lista literal de los paquetes directos cuyo `current` es `0.x`; un `0.x → 0.y` sólo entra como unidad major en `--upgrade`.
- **Ritmo estricto (`--upgrade`).** Un commit por unidad, un push por commit; nunca se pushea mientras el CI del push anterior está en vuelo (los workflows tienen `cancel-in-progress`); nada avanza sin `bucket=pass` en todos los checks. Rojo ⇒ corrección acotada con commit NUEVO o `git revert`; **jamás** `--amend`/force push después de un push (política de capa 1: denegado en toda forma). Topes: ≤2 iteraciones de fix por major, ≤2 pin-backs por batch; después, revert (major) o ⏸️ (batch).
- **Node de producción para instalar y compilar.** Todo `npm ci`/`npm install`/`npm run build` de un worktree corre con el major de node con el que el artefacto va a correr en PRODUCCIÓN: el `node_version:` del proyecto en `projects.yml` (escrito literal como `<node>`; si el proyecto no lo declara, el `node-version` del workflow del CI), vía `source ~/.nvm/nvm.sh && nvm use <node>` (el host tiene otro node por default). El CI puede correr con un node más nuevo que producción (hoy 22 vs 20 en algunos repos): un major de una dependencia de **runtime** (`dependencies`) cuyo `engines.node` exige más que producción se difiere aunque el CI dé verde; una `devDependency` (jest, eslint, types…) nunca corre en producción y sólo necesita el node del CI. Los installs llevan `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` (el `postinstall` de algunos repos baja chromium; el CI también lo salta).
- **Lockfile y overrides.** `package.json` y `package-lock.json` se commitean juntos y en sync (el deploy hace `npm ci`); los `overrides` de `package.json` se conservan (se elevan, nunca se borran: son el único pin de transitivos). Agregar un override nuevo vale SÓLO para cerrar una vuln transitiva que `npm audit fix` no cierra (patrón ya existente en los repos) — nunca para forzar un peer range.
- **Sin `cd` después de `EnterWorktree`.** El cwd del Bash persiste entre llamadas y `cd ..`/absolutos no pasan el gate: todo comando se escribe relativo a la raíz del worktree (`npm --prefix frontend …`, `npx --yes npm-check-updates --cwd frontend …`, `backend/.venv/bin/…`, `env --chdir=backend …`).
- **Commits:** inglés, Conventional Commits con el prefijo de la rama (tmpl §3/§8): `chore(deps): …` para bumps, `fix(deps): …` para adaptaciones/pin-backs, `revert(deps): …` para reverts, `docs: …` para el reporte. **Sin `Co-Authored-By: Claude`** ni footers de atribución de IA (regla explícita en los `CLAUDE.md` del repo). **Nunca** `git reset --hard`, **nunca** `--no-verify`; si un pre-commit hook falla, investigar y arreglar la causa raíz.
- **`--upgrade` es interactivo por naturaleza** (dura horas y cruza turnos): nunca en cron/headless/barridos; no existe variante `--all-*`.

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): si el operador pasó cualquier argumento
(`backend`/`frontend`/`--apply`/`--upgrade`) → ejecutar directo, sin menú. Si la
intención es clara por la sesión (p.ej. acaba de llegar el aviso de un CVE puntual) →
proponer el comando en una línea y esperar confirmación. Sin argumentos → UNA
sola `AskUserQuestion` con Q1+Q2 fusionadas. Nunca preguntar en modo
fleet/headless/cron ni dentro de un barrido.

La invocación delegada por [[security-pass]] hereda el contexto/selección explícitos
del conductor y nunca abre este menú; ver el contrato acotado más abajo. Los modos
independientes y `--upgrade` explícito conservan su comportamiento.

**Q1 — Modo** (selección única):

| label | description | preview |
|---|---|---|
| Auditar *(Recommended)* | read-only: escanea y arma el plan de bumps, no escribe nada | `/vuln-audit` |
| Aplicar (`--apply`) | aplica en batch los upgrades patch+minor — puede romper builds; checks mínimos, PR al final | `/vuln-audit --apply` |
| Modernizar (`--upgrade`) | secuencial por nivel semver: patch → minor → cada major en su commit; cada commit se pushea solo y espera su CI verde (N runs de CI, horas, cruza turnos); un major rojo se revierte y queda diferido | `/vuln-audit --upgrade` |

**Q2 — Capa** (selección única):

| label | description | preview |
|---|---|---|
| Ambas *(Recommended)* | backend (pip-audit) + frontend (npm audit) | `/vuln-audit` |
| Sólo backend | pip-audit + pip outdated sobre el venv | `/vuln-audit backend` |
| Sólo frontend | npm audit + npm outdated | `/vuln-audit frontend` |

**Qué NO se pregunta:** no hay más flags que estos dos ejes. `--apply` y `--upgrade`
son excluyentes y se tipean a propósito. Los majors no se eligen uno por uno en un
picker: sin `--upgrade` nunca se aplican (se evalúan read-only vía el menú
post-reporte); con `--upgrade` entran TODOS los que permiten los constraints, en
orden determinista, y es el CI —no un picker— quien decide cuáles quedan (rojo ⇒
revert + diferido). No existen `--no-wait`, `--max-iterations` ni `--skip-majors`:
el ritmo estricto y los topes de reintento son el diseño del modo. El `git push` +
PR no se ofrecen pre-run: `--apply` los hace al final, `--upgrade` con el primer
commit.

## Detección de entorno (Fase 0)
0. Parsear `$ARGUMENTS`: superficie (vacío/`backend`/`frontend`), `APPLY=true` si trae `--apply`, `UPGRADE=true` si trae `--upgrade`; los dos juntos ⇒ abortar. "Modos mutantes" = `--apply` y `--upgrade`. Sin ninguno la corrida es **solo auditoría**: los pasos marcados "(solo modos mutantes)" / "(solo `--apply`)" / "(solo `--upgrade`)" en todas las fases se saltan según corresponda.
1. (solo modos mutantes) Guard de worktree (protocolo por sesión): `git rev-parse
   --show-toplevel` debe caer bajo `~/webapps/.wt/`. Si cae en el clon principal,
   creá tu worktree de sesión ANTES de seguir — nunca busques una rama feature
   activa para hacerle checkout, ni crees una rama nueva en el clon principal. El
   slug depende del modo: `vuln-audit` para `--apply`, `deps-upgrade` para `--upgrade`:
   ```bash
   # pre-entry: corre en el clon principal, antes de EnterWorktree
   OUT="$(bash "$HOME/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh" \
          create chore vuln-audit)"       # --upgrade: create chore deps-upgrade
   echo "$OUT"   # PREFERIDO: imprime worktree=/branch=/base=/pr_base= — la BASE que
                 # resuelve es la de la coordenada (release activa o default), nunca
                 # la default a secas
   WT="$(sed -n 's/^worktree=//p' <<<"$OUT")"
   ```
   Entrá al worktree (Claude: `EnterWorktree path=$WT`; Codex: `cd "$WT"`) y confirmá
   `git rev-parse --show-toplevel` bajo `~/webapps/.wt/` antes de seguir. Si la sesión
   YA tiene su worktree/rama de un turno anterior, reutilizalo — no crees uno nuevo.
   **`--upgrade` con un worktree `deps-upgrade` preexistente:** leé
   `session-worktree.sh status` desde adentro; `pr_state=OPEN|none` ⇒ es un resume
   (ver `## Idempotencia`); `pr_state=MERGED|CLOSED` ⇒ retiralo primero desde el clon
   principal (`bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh remove deps-upgrade`)
   y creá uno nuevo.
   No hay fallback manual con `git fetch` + `git worktree add`: omitir el helper
   eludiría tanto la coordenada release-aware como el inventario `gitmeta` de la
   operación. Si el helper no está disponible o no puede resolver el SHA remoto
   exacto, abortá sin tocar el clon y repará/actualizá el toolkit primero.
2. (solo modos mutantes) `git status --porcelain` **ya dentro del worktree** → si imprime
   cualquier línea, abortar con: "Working tree no está limpio. Commitea antes de correr
   vuln-audit --apply/--upgrade (nunca stash en un clon principal del fleet)." Excepción
   de `--upgrade`: un tree sucio limitado a archivos de dependencias es una unidad a
   medias de una corrida anterior — ver `## Idempotencia`.
3. Detectar superficies:
   - Frontend: `[ -f frontend/package.json ]`.
   - Backend: `[ -f backend/requirements.txt ]`.
4. Si la superficie pedida es `backend` y no hay backend → abortar. Idem para frontend.
5. **Entorno Python** — dos reglas según el modo:
   - **Read-only (clon principal):** detectar el venv del proyecto (el primero que exista:
     `backend/.venv/bin/python`, `backend/venv/bin/python`; si ninguno existe y se va a
     auditar backend, abortar pidiendo crear el venv) y usarlo **sólo para leer**
     (`pip list --outdated`, `python -m pip_audit`). No instalar nada si el módulo falta:
     ```bash
     backend/venv/bin/python -m pip_audit --version >/dev/null 2>&1 || \
       echo "degraded: scanner missing — regenerar dependencias mediante deploy/operation-deps"
     ```
   - **Modos mutantes (worktree):** el venv del clon principal es el de producción y no
     está enlazado. Crear uno propio dentro del worktree (gitignored) — y **recrearlo
     desde cero si ya existía** de una corrida anterior (un venv que quedó con versiones
     distintas a `requirements.txt` hace mentir a `pip list --outdated`):
     ```bash
     rm -rf backend/.venv
     ```
     ```bash
     python3 -m venv backend/.venv
     ```
     ```bash
     backend/.venv/bin/pip install -q -r backend/requirements.txt && backend/.venv/bin/pip install -q pip-audit
     ```
     El intérprete es el `python-version` del workflow del CI (`grep -n python-version .github/workflows/ci.yml`);
     si el `python3` del host no coincide, usar `python3.<minor>` si existe, y si no, ⏸️
     (no se crea el venv con otro major.minor).
   En las fases siguientes, `<venv>` es `backend/venv` (o `backend/.venv`) en read-only y
   `backend/.venv` en los modos mutantes; se escribe **literal** en cada comando.
6. Rama base: en los modos mutantes sale de `session-worktree.sh status` (`base` = la de la
   coordenada: release activa si la hay, default si no) y se escribe literal (`<base literal>`).
   En read-only, `git ls-remote --symref origin HEAD` alcanza para informar sin
   mover refs locales.
7. Resolver `refs/heads/<base literal>` con `git ls-remote --exit-code --refs
   origin refs/heads/<base literal>`; si el SHA impreso falta, materializar sólo
   ese objeto con `git fetch --no-auto-gc --no-tags --no-write-fetch-head
   --quiet origin <sha literal>`. Capturar `BASE_SHA` con `git merge-base HEAD
   <sha-remoto literal>` (short). Nunca usar `origin/<base>`: puede estar stale.
8. Leer `CLAUDE.md` y `AGENTS.md` raíz si existen, y además `grep -n "#" backend/requirements.txt`
   (los comentarios inline son constraints, p.ej. «Production uses MySQL 8.0.x; Django 6.1
   requires MySQL 8.4+» ⇒ Django `<6.1`), el `node_version:` del proyecto en
   `~/webapps/vps-ops-toolkit/projects.yml` (el de producción = `<node>` literal para todo
   install/build; si falta, el `node-version` del workflow) y `python-version`/`node-version`
   de `.github/workflows/ci.yml`, para detectar:
   - Pin policies adicionales (ej. "cryptography pinned <44.0").
   - Slice de test mínimo recomendado (sólo se usa si el proyecto tiene `settings_test` sqlite
     en `backend/pytest.ini`).
   - Cualquier comando custom de build/test que corra el CI.
9. `<proyecto>` (el nombre con el que se bautizan los archivos de `/tmp`) es el
   `project=` que imprimió `session-worktree.sh status`, y se escribe **literal**
   en cada comando: `${PROJ}` es expansión de parámetros —rechazo medido de Gate A
   dentro de un worktree— y además una variable que no sobrevive entre bloques.
10. (solo `--upgrade`) **Preflight.** Todo debe pasar antes de tocar nada; cualquier fallo
    es `🚫 vuln-audit REFUSED (<razón>)` o `⏸️`, nunca se sigue:

    | Check | Comando (una llamada) | Falla ⇒ |
    |---|---|---|
    | CI presente | `ls .github/workflows` y `gh run list --limit 3` — la duración del último run es la **estimación por unidad** `T` | `🚫 REFUSED (sin CI: --upgrade exige un check verde por commit; usá --apply)` |
    | Base verde | `gh run list --branch <base literal> --limit 1` con `conclusion=success` | `🚫 REFUSED (base roja: el CI no puede arbitrar)` |
    | Sin otro PR de dependencias abierto | `gh pr list --state open --json number,headRefName,title` — cualquier rama `*vuln-audit*`, `*deps-upgrade*`, `dependabot/*` o título con `deps`/`dependenc` | `🚫 REFUSED (PR de dependencias #<n> abierto: drenalo con /merge-queue primero — conflictos de lockfile)` |
    | Node de producción disponible | `source ~/.nvm/nvm.sh && nvm ls <node>` | `⏸️` con `nvm install <node>` para el operador |
    | Lockfile en sync + `node_modules` del worktree | `source ~/.nvm/nvm.sh && nvm use <node> && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm --prefix frontend ci` | `🚫 REFUSED (package-lock fuera de sync: arreglalo en un PR aparte)` |
    | Presupuesto | imprimir `ℹ️ K unidades estimadas × T ≈ <h>; peor caso por major 4T` (sin pregunta: el flag fue explícito) | — |

## Fase 1 — Frontend
Ejecutar solo si la superficie ∈ {ambas, `frontend`} y `frontend/package.json` existe.
Los pasos 1–2 son la auditoría (siempre); el 0 y del 3 en adelante son la aplicación
en batch (solo `--apply`). En `--upgrade` la aplicación es el loop de
`## Modo --upgrade` (los pasos 3–7 no corren).

0. (solo `--apply`) **Bootstrap del worktree** (en `--upgrade` ya lo hizo el preflight):
   sin `node_modules`, `npm outdated` reporta todo como MISSING.
   ```bash
   source ~/.nvm/nvm.sh && nvm use <node> && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm --prefix frontend ci
   ```

1. **Snapshot inicial:**
   ```bash
   npm --prefix frontend audit --json > /tmp/<proyecto>-npm-audit.json || true
   ```
   ```bash
   npm --prefix frontend outdated --json > /tmp/<proyecto>-npm-outdated.json || true
   ```
   `npm outdated` retorna exit 1 cuando hay outdated; eso es esperado, no es error. En un
   clon de deploy estático (sin `node_modules`, p.ej. projectapp) `npm outdated` marca
   MISSING: `current` se toma de `package-lock.json` (`packages."node_modules/<pkg>".version`)
   — no se instala nada en el clon principal.

2. **Parsear y clasificar:**
   - De `npm-audit.json`: lista de paquetes con `{package, severity, notes}` y totales `{critical, high, moderate, low}`.
   - De `npm-outdated.json`: por cada directo `{current, wanted, latest}`. Clasificar por el
     diff `current → latest` (nunca por `wanted`, que depende del rango `^`): `patch` (mismo
     major.minor), `minor` (mismo major ≠ 0, distinto minor), `major` (distinto major, o
     `0.x → 0.y`, o `0.x → 1.x`). Guardar la lista literal `ZEROX` = directos cuyo `current`
     es `0.x`.

   **Corte por modo:** sin flags la fase termina acá — lo parseado alimenta la tabla del
   plan (Fase 3) y no se toca `package.json` ni se corre ningún install. Con `--upgrade`,
   la aplicación es el loop de `## Modo --upgrade`.

   Para el batch independiente `--apply`, evaluar el beneficio de los bumps sin CVE
   antes de escribir. La lista literal `ELIGIBLE_NPM` contiene sólo los paquetes
   elegibles por esa evaluación (incluidos los fixes permitidos de CVEs). Los inciertos
   y diferidos quedan en el reporte con razón. La auditoría y `--upgrade` siguen listando
   todos los paquetes; no confundir una lista completa con permiso para modernizar
   paquetes sin beneficio demostrado.

3. (solo `--apply`) **Aplicar updates** (un comando por llamada; `--reject` sólo en la
   corrida minor y sólo si `ZEROX` no está vacía; nunca `npm audit fix --force`):
   ```bash
   npm --prefix frontend audit fix
   ```
   ```bash
   npx --yes npm-check-updates --cwd frontend -u --target minor --filter <ELIGIBLE_NPM literal, separado por comas> --reject <ZEROX literal, separado por comas>
   ```
   ```bash
   source ~/.nvm/nvm.sh && nvm use <node> && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm --prefix frontend install
   ```

   Omitir el comando `npm-check-updates` si `ELIGIBLE_NPM` está vacío; omitir `--reject`
   si `ZEROX` está vacío. `npm audit fix` atiende las vulnerabilidades bajo los pins;
   no se usa para modernización discrecional. Sin cambios de dependencias no instalar
   ni crear un commit de bump vacío.

4. (solo `--apply`) **Manejo de ERESOLVE:** si `npm install` falla con `ERESOLVE`:
   - Identificar el paquete ofensor del mensaje de error.
   - Editar `frontend/package.json` (Edit) para revertir ese paquete a la última versión que respete las peer deps actuales (típicamente, retroceder 1 minor o quedarse en la versión previa al `ncu`).
   - Repetir el `npm --prefix frontend install` de arriba.
   - Registrar el caso en la sección `Rollbacks` del reporte.
   - Si el reintento falla otra vez, abortar con error claro. Nunca `--legacy-peer-deps` en el commit.

5. (solo `--apply`) **Verificar:**
   ```bash
   npm --prefix frontend audit
   ```
   ```bash
   source ~/.nvm/nvm.sh && nvm use <node> && npm --prefix frontend run build
   ```
   (o el script de build que corre el CI, si es otro: `grep -n "npm run" .github/workflows/ci.yml`).
   Si el build falla:
   - Si ya se hizo commit **y aún no se pushó**, `git reset --soft HEAD~1`.
   - Reportar el error y abortar.

6. (solo `--apply`) **Commit (sin Co-Authored-By, sin footers de IA):**
   ```bash
   git add frontend/package.json frontend/package-lock.json
   ```
   ```bash
   git commit -m "chore(deps): frontend patch+minor updates"
   ```
   Si `npm install` no produjo cambios en `package.json`/`package-lock.json`, **no commitear**; registrar en el reporte que no había updates aplicables.

7. (solo `--apply`) **Capturar el snapshot final** (`npm --prefix frontend audit --json` post-update) para la sección `Updates Applied` del reporte.

## Fase 2 — Backend
Ejecutar solo si la superficie ∈ {ambas, `backend`} y `backend/requirements.txt` existe.
Los pasos 1–4 son la auditoría (siempre); del 5 en adelante es la aplicación en batch
(solo `--apply`). En `--upgrade` la aplicación es el loop de `## Modo --upgrade`.

1. **Entorno:** el `<venv>` de la Fase 0 paso 5 — el del proyecto (sólo lectura) en
   read-only, `backend/.venv` del worktree en los modos mutantes. Nunca `source …/activate`:
   los binarios se invocan por ruta.

2. **pip-audit disponible:** en read-only comprobarlo con `<venv>/bin/python -m
   pip_audit --version`. Si falta, registrar una sola señal `degraded: scanner
   missing`, conservar el resultado de `pip list --outdated` y **no** ejecutar
   `pip install`; el remedio es el próximo build tipado de dependencias. En modos
   mutantes ya está instalado dentro de `backend/.venv`, que pertenece al worktree.

3. **Snapshot inicial** (`pip-audit` sale 1 cuando hay vulns; esperado). Con `<venv>` literal
   (`backend/venv` o `backend/.venv` según el modo):
   ```bash
   backend/venv/bin/python -m pip_audit --format json --progress-spinner=off > /tmp/<proyecto>-pip-audit.json || true
   ```
   ```bash
   backend/venv/bin/pip list --outdated --format json > /tmp/<proyecto>-pip-outdated.json
   ```
   La verdad de las versiones declaradas es `requirements.txt`; el venv sólo aporta `latest`
   y las vulns de lo instalado.

4. **Construir el plan:**
   - Parsear `requirements.txt` línea por línea: capturar pin actual de cada paquete (`==X.Y.Z`, `>=A,<B`, sin pin, etc.) y los comentarios inline (constraints).
   - Para cada paquete outdated: clasificar `patch`/`minor`/`major` por el diff `current → latest`
     (`0.x → 0.y` es major; para Django también lo es una feature release `X.Y → X.Z`); calcular `target` = última versión que **respete el pin y los
     constraints documentados** (ej. pin `<44.0` ⇒ target ≤ 43.x; comentario «Django 6.1
     requires MySQL 8.4+» ⇒ Django `<6.1`). En `--apply` el target además no cruza el major
     actual. Si `target == current` ⇒ skip, y si lo que lo frena es un constraint, marcar
     `constraint: <cita>`.
   - Para cada paquete con vulns que solo se arreglan fuera del pin/constraint: marcarlo como **remaining** en el reporte (no intentar el bump).
   - Para los bumps sin CVE, agregar evaluación de beneficio y motivo. En `--apply`
     sólo los elegibles entran al batch; inciertos/diferidos permanecen en el reporte.
     Una vulnerabilidad conocida no se excluye por esa evaluación económica.

   **Corte por modo:** sin flags la fase termina acá — el plan alimenta la tabla de Fase 3
   y no se edita `requirements.txt` ni se instala nada en el venv del proyecto. Con
   `--upgrade`, la aplicación es el loop de `## Modo --upgrade`.

5. (solo `--apply`) **Aplicar:** editar sólo los paquetes elegibles de `backend/requirements.txt` (Edit) con las nuevas
   versiones (mantener el operador del pin: si era `==`, sigue `==<nuevo>`; si era rango,
   ajustar el floor sin tocar el techo). Luego:
   ```bash
   backend/.venv/bin/pip install -r backend/requirements.txt && backend/.venv/bin/pip check
   ```
   ```bash
   backend/.venv/bin/pip-audit --format json --progress-spinner=off > /tmp/<proyecto>-pip-audit-final.json || true
   ```

6. (solo `--apply`) **Verificar (sin base de datos):**
   ```bash
   env --chdir=backend .venv/bin/python manage.py check
   ```
   ```bash
   env --chdir=backend .venv/bin/python -m pytest --collect-only -q
   ```
   `manage.py check` debe imprimir "0 issues" (los checks corren con los settings por
   defecto del `manage.py`, nunca con `DJANGO_ENV=production`); `--collect-only` debe
   colectar sin errores.
   Slice mínimo — **sólo si** `grep -n settings_test backend/pytest.ini` imprime algo
   (settings de test sqlite): el comando de test ejemplar del `CLAUDE.md` o el primer
   `tests/test_*.py`, con `env --chdir=backend .venv/bin/python -m pytest <archivo literal> -q`.
   Alternativa equivalente: si `grep -n DJANGO_DB_ENGINE backend/*/settings.py` muestra que el
   motor se lee del entorno, el mismo comando con `env --chdir=backend DJANGO_DB_ENGINE=django.db.backends.sqlite3 .venv/bin/python -m pytest <archivo literal> -q`
   fuerza sqlite (el archivo de test queda en el worktree, nunca en la base real). Si no se
   cumple ninguna de las dos, registrar «⏭️ slice: los settings de test no son sqlite — la
   suite la corre el CI» y no correr ningún test (con el `.env` de producción enlazado sería
   un test contra la base real).

   Si cualquier verificación falla:
   - Si ya se hizo commit **y aún no se pushó**, `git reset --soft HEAD~1`.
   - Reportar el comando que falló y abortar.

7. (solo `--apply`) **Commit:**
   ```bash
   git add backend/requirements.txt
   ```
   ```bash
   git commit -m "chore(deps): backend patch+minor updates"
   ```
   Si `requirements.txt` no cambió, no commitear.

## Modo `--upgrade` — modernización secuencial (un PR, un commit por unidad, CI verde por commit)

Corre después de la Fase 0 (con el preflight ✅) y de los snapshots/planes de las Fases 1–2
(pasos de auditoría), ya dentro del worktree `deps-upgrade`, con `node_modules` y
`backend/.venv` propios. Las Fases 1–2 NO aplican nada en este modo: la aplicación es este
loop. Cada unidad se pushea sola y **nada avanza sin su CI verde**.

### Unidades y orden (determinista)

| Unidad | Contenido | Subject del commit |
|---|---|---|
| `lockfile(frontend)` | `npm audit fix` (transitivos in-range, sin tocar directos) | `chore(deps): frontend transitive audit fixes (lockfile)` |
| `patch(<superficie>)` | todos los directos con bump patch disponible | `chore(deps): <frontend\|backend> patch updates (<N> pkgs)` |
| `minor(<superficie>)` | todos los directos con bump minor (excluidos los `0.x`) | `chore(deps): <frontend\|backend> minor updates (<N> pkgs)` |
| `major(<grupo>)` | UN paquete (o grupo lockstep) a la mayor versión que permiten los constraints | `chore(deps): <pkg> <old> -> <new>` · grupo: `… (+react-dom, @types/react)` |

Body de todo commit de bump: una línea por paquete `<pkg> <old> -> <new>` (varios `-m`).
Unidad sin diff ⇒ ⏭️ sin commit ni run.

**Orden:** frontend → backend; dentro de cada superficie: lockfile → patch → minor → majors.
Majors: **framework → tooling → resto alfabético**.

| Superficie | Framework (grupos lockstep) | Tooling (grupos) |
|---|---|---|
| frontend | `react, react-dom, @types/react, @types/react-dom` · `next, eslint-config-next` · `nuxt, @nuxt/*` · `vue, vue-router, pinia, @vue/*` | `typescript` · `eslint, @eslint/js, @typescript-eslint/*, eslint-plugin-*, eslint-config-*` · `prettier (+ eslint-config/plugin-prettier)` · `vite, @vitejs/*` · `vitest, @vitest/*` · `jest, ts-jest, babel-jest, jest-environment-jsdom, @types/jest` · `@playwright/test, playwright` · `tailwindcss, @tailwindcss/*, postcss, autoprefixer` · `@testing-library/*` |
| backend | `Django` (+ los `django-*` que `pip check` declare incompatibles: bump lockstep permitido dentro de la unidad) | `pytest, pytest-django, pytest-cov, coverage, ruff, black, flake8, mypy, isort` |

`@types/<x>` viaja siempre con `<x>`. **Django**: cada feature release (`6.0 → 6.1`) es una unidad
major de framework aunque el primer número no cambie (nunca va en el batch minor: es donde se
pierde el gate de la base de producción — caso real xpandia PR #70). Un major cuyo objetivo viola un constraint documentado
(comentario en `requirements.txt`, pin en `CLAUDE.md`/`AGENTS.md`, `engines.node` mayor que
el `node_version` de producción en `projects.yml` — sólo para `dependencies` de runtime, no para
`devDependencies` —, `Requires-Python` mayor que el python del CI) **no se intenta**: fila ⏭️ `constraint: <cita>`. Si existe una versión permitida menor
que igual es major (p.ej. Django 4.2 → 6.0 con techo `<6.1`), ése es el objetivo. Versiones
disponibles: `backend/.venv/bin/pip index versions <pkg>` · `npm view <pkg>@<ver> engines.node`.
Paquetes **runtime-only** que el CI no ejercita (gunicorn/uvicorn, workers huey/celery,
mysqlclient, codecs de Pillow) se aplican igual pero llevan la nota `CI: no cubre` en el
ledger y van a «Acción operativa posterior al merge» del reporte.

### Pre-loop
1. Snapshots de auditoría (Fase 1 pasos 1–2, Fase 2 pasos 3–4) ya en el worktree.
2. Armar la lista de unidades `1..K` con paquetes y objetivos; imprimirla con la estimación
   `K × T` (T = duración del último run, del preflight).
3. Resume (`## Idempotencia`): reconciliar con `git log --format='%h %s' <BASE_SHA literal>..HEAD`
   y saltar las unidades ya aplicadas o diferidas.
4. Desde la segunda unidad, guard antes de cada push: `gh pr view <n> --json state -q .state`
   debe imprimir `OPEN`.

### Loop por unidad `k` (un comando simple por llamada, sin `cd`)

**Paso 1 — precondición:** `git status --porcelain` vacío y el último CI de HEAD visto en ✅.

**Paso 2 — aplicar la unidad.** Frontend, según el tipo (lockfile / patch / minor / major):
```bash
npm --prefix frontend audit fix
```
```bash
npx --yes npm-check-updates --cwd frontend -u --target patch --filter <directos clasificados patch, separado por comas>
```
```bash
npx --yes npm-check-updates --cwd frontend -u --target minor --filter <directos clasificados minor, separado por comas> --reject <ZEROX literal, separado por comas>
```
(los batches llevan `--filter` con la lista literal de los directos clasificados en la Fase 1 paso 2
— sin filtro, `--target patch` movería a un patch intermedio a los paquetes clasificados minor/major y
gastaría un ciclo de CI de más; lista vacía ⇒ la unidad es ⏭️ sin correr ncu)
```bash
npx --yes npm-check-updates --cwd frontend -u --target latest --filter <grupo literal, separado por comas>
```
(major con techo ⇒ editar `frontend/package.json` con Edit conservando operador y sección,
sin ncu). Sonda previa opcional para un major: `npm --prefix frontend install <pkg>@<ver> --dry-run`
corre el resolver sin tocar archivos. Leé la SALIDA, no el rc: para un paquete pedido desde la raíz
npm suele resolver con `npm warn ERESOLVE overriding peer dependency` y rc 0 (el peer de un plugin
transitivo queda sobreescrito); sólo un `npm ERR! ERESOLVE` difiere la unidad ahí mismo con el
bloqueador literal. Con warnings la unidad sigue y el veredicto lo dan el smoke y el CI. Luego, siempre:
```bash
source ~/.nvm/nvm.sh && nvm use <node> && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm --prefix frontend install && npm --prefix frontend ls --depth=0
```
Backend: editar `backend/requirements.txt` con Edit (`==` → `==<new>`; `>=A,<B`: patch/minor
sube el piso y conserva el techo, major sube el techo al próximo major Y el piso a la nueva
versión; sin techo: sube el piso) y:
```bash
backend/.venv/bin/pip install -r backend/requirements.txt && backend/.venv/bin/pip check
```
`git status --porcelain` vacío tras aplicar ⇒ unidad vacía ⇒ ⏭️, siguiente. ERESOLVE en un
batch ⇒ restaurar el spec del ofensor con Edit, reinstalar, seguir; el excluido se reintenta
UNA vez como unidad `minor-retry` después de los majors (suele destrabarse con un peer
major); si vuelve a fallar ⇒ diferido `ERESOLVE con <peer>`. `pip check` rojo en un batch ⇒
pin-back del par en conflicto antes de commitear; en un major ⇒ bump lockstep del compañero
que declara la incompatibilidad, y si no alcanza ⇒ diferir.

**Paso 3 — smoke local (≤3 comandos, nunca la suite):**

| Superficie | Siempre | Tercer slot según unidad |
|---|---|---|
| frontend | `source ~/.nvm/nvm.sh && nvm use <node> && npm --prefix frontend run build` (o el script de build del CI) | eslint/prettier/typescript ⇒ `npm --prefix frontend run lint` (si el script existe) — gatea sólo si el lint estaba limpio en HEAD antes de la unidad; si ya era rojo (medido una vez al inicio: `N problems`), gatea el conteo (no debe crecer) y un crash del lint (`TypeError`, `Error while loading rule`) sigue siendo rojo · jest/testing-library ⇒ un solo spec: `npm --prefix frontend exec -- jest <spec literal>` · playwright ⇒ `npm --prefix frontend exec -- playwright --version` |
| backend | `env --chdir=backend .venv/bin/python manage.py check` · `env --chdir=backend .venv/bin/python -m pytest --collect-only -q` — si el settings del proyecto lee el motor del entorno (linaje base_feature: `DJANGO_DB_ENGINE`), TODOS los `manage.py`/pytest del worktree llevan `DJANGO_DB_ENGINE=django.db.backends.sqlite3 DB_NAME=/tmp/<proyecto>-deps-upgrade.sqlite3` delante (con el `.env` de prod enlazado, hasta un `check` plano abre la conexión a MySQL: medido en mimittos, Django 6.1 lo rechazó desde el `check`) | major de Django o de `mysqlclient` ⇒ `env --chdir=backend .venv/bin/python manage.py makemigrations --check --dry-run && env --chdir=backend DJANGO_ENV=production .venv/bin/python manage.py check --database default` — el segundo abre la conexión a la base de PRODUCCIÓN con el selector de prod del proyecto (`DJANGO_ENV=production` o `DJANGO_SETTINGS_MODULE=<settings_prod>`, el que use su `manage.py`/systemd) y corre los checks del backend MySQL **sin escribir**: es lo único con settings de producción permitido desde el worktree, porque el CI corre sobre sqlite y no puede ver una incompatibilidad Django↔MySQL (caso real: xpandia PR #70 verde → hotfix #71, 2026-08-26). Si no es un major de Django/mysqlclient, el slice sólo con `settings_test` sqlite (o forzando `DJANGO_DB_ENGINE=django.db.backends.sqlite3` si el settings lo lee del entorno) |

Smoke rojo ⇒ fix local ≤2 intentos con el mismo alcance del Paso 7(d), sin gastar CI — uno de
los intentos puede ser bajar al major intermedio cuando el objetivo está varios majors por
delante (p.ej. typescript 5 → 7 rojo ⇒ probar 6.x; queda como `chore(deps): typescript 5.9.3 -> 6.0.3`
con la nota «7.x: <causa>»). Si no cierra: descartar **sólo** los cambios no commiteados de la unidad
(`git checkout -- frontend/package.json frontend/package-lock.json` o
`git checkout -- backend/requirements.txt` — nunca `reset --hard`, nunca `checkout .`),
resincronizar (`npm --prefix frontend ci` / `pip install -r`), registrar
`<pkg> <old> -> <new> | smoke local: <causa>` en `/tmp/<proyecto>-deps-upgrade-deferred.txt`,
ledger 🔁 diferida, siguiente unidad.

**Paso 4 — commit:**
```bash
git add frontend/package.json frontend/package-lock.json
```
```bash
git commit -m "chore(deps): frontend patch updates (12 pkgs)" -m "axios 1.7.2 -> 1.7.9" -m "dayjs 1.11.10 -> 1.11.13"
```
(backend: `git add backend/requirements.txt`).

**Paso 5 — push (+ PR la primera vez).** Rama y base salen de `session-worktree.sh status`
y van literales:
```bash
git push -u origin <branch literal>
```
```bash
gh pr create --base <base literal> --title "chore(deps): sequential dependency upgrade (<DDMMYYYY>)" --body "Sesión: <sesión>
Intención: modernización secuencial de dependencias (--upgrade): un commit por unidad semver, CI verde por commit, majors rojos revertidos y diferidos

Plan de unidades:
1. frontend lockfile (npm audit fix)
2. frontend patch (<N> pkgs)
3. frontend minor (<M> pkgs)
4. <pkg> <old> -> <new> (+<compañeros>)
..."
```
El body es texto literal con saltos de línea reales — nunca `--body "$(printf …)"`. El CI de
la rama corre **por el PR** (`pull_request`), no por el push: el PR se crea inmediatamente
después del primer push. Unidades siguientes: `git push` a secas, con el guard del pre-loop
antes.

**Paso 6 — esperar el CI** (contrato de [[pr-green]] Phase 3):
```bash
gh pr checks <n> --watch --fail-fast=false
```
Llamada foreground con `timeout: 600000` en el tool Bash, directa — sin `sleep` previo: el Bash de
Claude Code rechaza un `sleep` en foreground. «no checks reported» (el PR se creó hace segundos)
⇒ `gh run list --branch <branch literal> --limit 1` y un reintento del `--watch`; si sigue sin
checks ⇒ ⏸️ «CI no disparó para el PR». En Claude Code un `--watch` que supera los 600 s **pasa solo a background** («moved to the
background (ID: …) — You will be notified when it completes»): no montes nada, esperá esa
notificación y clasificá (Paso 7). Si en cambio muere con exit **143** (Codex, u otro harness sin
auto-background; le pasa a todo repo con `T > 8 min` — ahí montá el watcher directo, sin foreground)
⇒ **NO re-bloquees con otro `--watch`**: barré tus watchers obsoletos (`TaskStop` sólo de tasks
`CI-MONITOR [<repo>#<n> upgrade …]` de esta sesión) y montá **un solo comando** en
background (Bash `run_in_background: true`; sin loops ni sustituciones — la variante
canónica de [[merge-when-green]] usa `for` + `$(…)` y el gate del worktree la rechaza):
```bash
gh pr checks <n> --watch --fail-fast=false --interval 30 && echo "CI-MONITOR [<repo>#<n> upgrade u<k>] verde — NEXT: clasificar con gh pr checks <n> --json name,state,bucket y seguir con la unidad <k+1>" || echo "CI-MONITOR [<repo>#<n> upgrade u<k>] rojo — NEXT: gh pr checks <n> --json name,state,bucket y fix loop de la unidad <k>"
```
Reportá la plantilla intermedia de `## Output final` y **cortá el turno**. Al llegar la
notificación con `CI-MONITOR [`: clasificá SIEMPRE con `--json` (el `echo` sólo transporta la
etiqueta), re-verificá `gh pr view <n> --json state -q .state` y seguí el loop sin
reconstruir contexto. Máximo un watcher por PR.

**Paso 7 — clasificar:**
```bash
gh pr checks <n> --json name,state,bucket
```
- Todos `pass` ⇒ ledger ✅, unidad `k+1`.
- Algún `fail` ⇒ **rojo**:
  - (a) **Base verde primero:** `gh run list --branch <base literal> --limit 1` — base roja ⇒
    ⏸️ «rojo de la base, no de la unidad».
  - (b) **Logs:** `gh run list --branch <branch literal> --limit 1 --json databaseId,status,conclusion`
    → `gh run view <run-id> --log-failed`. Extraer los IDs (pytest `FAILED path::Clase::test`,
    jest `describe > it` + archivo, playwright spec + título) y la clase del error (import/API
    renombrada, tipos, config de build/test, lint, migración).
  - (c) **Infra** (runner perdido, `timed_out`, 5xx de registry, sin logs) ⇒
    `gh run rerun <run-id> --failed` una vez → Paso 6; segundo infra ⇒ ⏸️.
  - (d) **Unidad major — fix loop ≤2 iteraciones** (cada una = commit
    `fix(deps): adapt <area> to <pkg> <new>` + `git push` + Paso 6). Con el ritmo estricto el
    único delta desde el último verde es la unidad, así que el rojo es atribuible por
    construcción. Adaptaciones **permitidas sin pausar** (son la esencia del major): bajar al major
    intermedio como iteración (`fix(deps): step <pkg> down to <ver> (<causa>)`), imports y
    APIs renombradas, configs de build/test/lint (`jest.config`, `vite.config`,
    `eslint.config`, `tsconfig`, `pytest.ini`), tipos, settings renombrados documentados en las
    release notes, bumps de compañeros lockstep, elevar un `override`. **Prohibidas ⇒ revert
    inmediato + diferido:** modelos/migraciones (`makemigrations --check` sucio), settings de
    seguridad, auth, pagos/facturación, cambios de datos, o un diff de código de producción
    > ~50 líneas (excede el esfuerzo acotado). Tercer rojo ⇒ revert (Paso 8).
  - (e) **Unidad batch — pin-back:** el log nombra al ofensor ⇒ restaurar su spec exacto con
    Edit, `npm --prefix frontend install` / `pip install -r`, commit
    `fix(deps): pin <pkg> back to <old> (CI red: <cause>)`, push, Paso 6; ≤2 pin-backs por
    batch. **No atribuible** ⇒ ⏸️ con el extracto del log y las dos salidas para el operador:
    `git revert` del batch, o bisección por mitades en dos unidades nuevas (no se automatiza).
- Algún `cancel` ⇒ comparar `git ls-remote origin refs/heads/<branch literal>` con
  `git rev-parse HEAD`: si difieren, alguien pusheó a la rama ⇒ ⏸️ «rama tocada por otro actor»
  (los runs de las unidades anteriores tienen otros SHA por diseño — no son ajenos). Si coinciden,
  el `cancel` es del propio run: un job que pega su `timeout-minutes` (runners lentos; el E2E de
  xpandia lo hizo a los 18 min exactos) GitHub lo reporta `cancelled` y cuenta como infra ⇒
  `gh run rerun <run-id> --failed` una vez; segundo cancel ⇒ ⏸️.
- `pending` residual ⇒ un `--watch` más.

**Paso 8 — revert de un major.** `<sha>` = commit de la unidad (del
`git log --format='%h %s' <BASE_SHA literal>..HEAD`); el rango cubre la unidad y sus fixes:
```bash
git revert --no-commit <sha unidad literal>^..HEAD && git commit -m "revert(deps): react 18.3.1 -> 19.1.0 (CI red: <cause>)"
```
Conflicto ⇒ `git revert --abort` y ⏸️. Después: resincronizar el entorno local
(`npm --prefix frontend ci` / `backend/.venv/bin/pip install -r backend/requirements.txt`),
`git push`, Paso 6 (restaura un estado ya verde: rojo ⇒ infra/flaky ⇒ rerun una vez ⇒ ⏸️),
ledger 🔁 `diferida (<causa>)`, registrar en `/tmp/<proyecto>-deps-upgrade-deferred.txt`,
siguiente unidad. Si el diferimiento viene del check contra la base de producción (p.ej.
«MySQL 8.4 or later is required»), dejá el constraint **documentado** como comentario inline
en `backend/requirements.txt` dentro del mismo commit de revert — o, si se difirió en el smoke sin
llegar a commitear, dentro del commit `docs:` del cierre (`# Production uses MySQL
8.0.x; Django 6.1 requires MySQL 8.4+`): la próxima corrida lo salta por constraint en vez de
gastar un ciclo de CI.

**Paso 9 — ledger** (fila en la respuesta; la fuente de verdad es `git log`):
`| # | Unidad | Paquetes (antes → después) | Commit | CI run | Iter. fix | Resultado |` con
`Resultado` ∈ {✅ aplicada · ⏭️ vacía / `constraint: <cita>` · 🔁 revertida/diferida (<causa>)
· ⏸️ en vuelo · pendiente}; los runtime-only llevan además `CI: no cubre`.

### Cierre
Snapshots finales (`npm --prefix frontend audit --json`, `npm --prefix frontend outdated --json`,
`backend/.venv/bin/pip-audit …`, `backend/.venv/bin/pip list --outdated …`) →
`audit-report.md` (plantilla en Fase 3, `### Modo --upgrade — reporte final`) → commit
`docs: dependency upgrade report (<YYYY-MM-DD>)` → `git push` → Paso 6 (última espera: el
DoD de sesión es PR abierto con CI verde en HEAD; si expira, watcher con `NEXT: emitir el
veredicto final`) → opcional pero recomendado: `gh pr edit <n> --body "…"` con el ledger final
como texto literal, conservando las líneas `Sesión:`/`Intención:` (lo consume `/merge-queue`)
→ `PR URL: <url>` y **PARÁ** (merge = `/merge-queue`/operador).

### Racionalizaciones que NO valen

| Excusa | Realidad |
|---|---|
| «El CI tarda 30 min; pusheo dos unidades juntas» | Se pierde la atribución: el ritmo estricto ES el diseño. Una unidad por push. |
| «Amend + force push para dejar un commit por cambio» | Force push denegado en toda forma (capa 1). Commit nuevo o `git revert`. |
| «Corro la suite local para no gastar CI» | Nunca la suite local: el CI es el árbitro y el `.env` del worktree es el de producción. |
| «El venv del clon principal ya tiene todo instalado» | Es el venv del servicio en producción. Venv propio en el worktree, siempre. |
| «`ncu -u` a latest de una vez y listo» | Un rojo no se puede atribuir. Batch patch → batch minor → un major por commit. |
| «Este major sólo necesita una migración chica» | Migraciones = fuera de alcance: revert y diferido con causa. |
| «`cd frontend` y sigo desde ahí» | El cwd persiste entre llamadas y `cd ..` no pasa el gate: comandos relativos a la raíz (`--prefix`, `--cwd`, `env --chdir`). |
| «La suite local corre sobre sqlite, no toca prod» | Sigue siendo la suite completa (regla de casa): el CI la corre por cada commit. Local = smoke ≤3 comandos. |
| «`manage.py check` con settings de prod es sólo lectura y atrapa lo que el CI no ve» | Cierto, y por eso está permitido — SÓLO `check --database default`, SÓLO en majors de Django/mysqlclient. Todo lo demás con settings de producción sigue prohibido. |
| «Un paquete por commit es más trazable» | La granularidad es por nivel semver (decisión del operador): batches patch/minor, majors uno por uno. Un rojo en un batch se resuelve con pin-back. |
| «Con 20 minutos alcanza para 2-3 commits; después sigo» | Correcto: el loop se reanuda desde git (`## Idempotencia`) — pero cada corte deja el DoD cumplido (PR abierto + CI verde en HEAD), nunca un push sin veredicto. |
| «El repo no prohíbe `Co-Authored-By`; un commit viejo lo lleva» | Los commits de esta skill no llevan footers de IA (regla de los `CLAUDE.md` del fleet). Un commit ajeno que los tenga no es precedente. |
| «Mientras corre el CI preparo el próximo commit» | El tree tiene que estar limpio al recibir el veredicto: un rojo se resuelve sobre HEAD limpio (pin-back/revert). Esperar ES parte del ritmo. |
| «`git commit -am` es seguro, sólo cambió requirements.txt» | Siempre `git add` por path: el ledger/reporte y otros archivos pueden estar sucios sin que lo notes. |
| «Aprovecho y le pongo techo a los rangos abiertos» | El estilo del pin es del operador: `==` sigue `==`, `>=A,<B` conserva su forma, un rango sin techo sólo sube el piso. |
| «Agrego `overrides` para que los peers acepten el major» | Un override que fuerza un peer range es `--legacy-peer-deps` disfrazado. ERESOLVE ⇒ diferido con el bloqueador literal; los overrides existentes sólo se elevan. |
| «Preparo todos los commits en local y los pusheo de a uno» | Un rojo en la unidad k deja k+1..n apilados sobre un estado roto (fixes y reverts se entrelazan). El loop es aplicar → push → verde → siguiente. |
| «Uso el node/npm del PATH del host; el CI es el árbitro» | Otro major de npm normaliza el lockfile distinto (diffs ruidosos, `npm ci` del CI puede fallar). Siempre `nvm use <node>`. |

## Fase 3 — Plan / Reporte

### Modo default (sin flags) — el plan en la respuesta, nada escrito

Consolidar lo parseado en Fases 1–2 en **la tabla del plan de bumps** (esto ES
el entregable de la corrida default; se muestra en la respuesta, no se escribe
ningún archivo ni commit):

| Paquete | Superficie | Actual → Propuesta | Severidad (vulns) | Tipo | Unidad `--upgrade` | Riesgo |
|---|---|---|---|---|---|---|
| ... | frontend/backend | `X.Y.Z` → `X.Y.W` | critical/high/moderate/low/— | patch / minor / **major (skip en --apply)** | `lockfile` / `patch-batch` / `minor-batch` / `major #k` / `constraint: <cita>` | breve: pin techo, peer deps, breaking changes conocidos |

- Los **majors se listan igual**, marcados `major (skip en --apply)` — `--apply` nunca los
  aplica; `--upgrade` los aplica uno por commit (columna `Unidad`).
- `Riesgo`: una frase por paquete (qué podría romper el bump o por qué se saltea).
- Agregar evaluación de valor por paquete: beneficio, esfuerzo/riesgo, obligación,
  decisión/motivo y evidencia. La lista de `--upgrade` explícito sigue completa; el
  consejo de parar se muestra sin recortar ese alcance autorizado.
- Debajo de la tabla, la lista «**Orden de unidades para `--upgrade`**» (1..K, con paquetes
  y objetivos): el plan read-only es el dry-run exacto del modo.
- La aplicación queda para `--apply`/`--upgrade` o para la selección en el menú post-reporte.

### Modo `--apply` — reporte y commit final
Se ejecuta siempre que hubo `--apply` (incluso si una fase no produjo updates: el reporte lo refleja).

1. **Generar `audit-report.md`** en la raíz del proyecto, sobrescribiendo si existe. Plantilla:

   ```markdown
   # Vulnerability Audit & Dependency Update Report

   **Branch:** <git rev-parse --abbrev-ref HEAD>
   **Date:** <YYYY-MM-DD>
   **Base:** <BASE_BRANCH> @ <BASE_SHA>
   **Scope:** patch + minor updates only (no major version bumps)

   ## Summary

   | Surface  | Vulns (initial) | Outdated (initial) |
   |----------|-----------------|--------------------|
   | Frontend | <total / breakdown por severity> | <count> |
   | Backend  | <total across N packages>        | <count> |

   ---

   ## Frontend — `npm audit` (initial)
   Source: `/tmp/<PROJ>-npm-audit.json`

   | Package | Severity | Notes |
   |---|---|---|
   | ...  | ...       | ...    |

   **Totals:** <crit>/<high>/<mod>/<low>.

   ## Frontend — `npm outdated` (initial)
   Source: `/tmp/<PROJ>-npm-outdated.json`

   - <pkg>: <current> → <wanted> → <latest>  *(skip si major)*

   ---

   ## Backend — `pip-audit` (initial)
   Source: `/tmp/<PROJ>-pip-audit.json`

   | Package | Current | Vulns | Min in-major fix |
   |---|---|---|---|

   ## Backend — `pip list --outdated` (initial)
   Source: `/tmp/<PROJ>-pip-outdated.json`

   - <pkg> <current> → <latest> *(constrained / major bump skipped si aplica)*

   ---

   ## Plan

   ### Frontend
   - <bumps planeados>

   ### Backend
   - <bumps planeados, respetando pins>

   ## Updates Applied

   ### Frontend (commit `chore(deps): frontend patch+minor updates`)
   - <pkg> <old> -> <new>
   - Final `npm audit`: <totales>.
   - Remaining outdated (majors saltados intencionalmente): <lista>.

   ### Backend (commit `chore(deps): backend patch+minor updates`)
   - <pkg> <old> -> <new>
   - `pip-audit` final: <total remaining> en <N> paquetes (todos requieren majors saltados o están fuera de pin).

   ## Rollbacks
   - <si hubo, descripción + razón. Si no, "Ninguno.">

   ## Verification Results

   ### Frontend
   - `npm audit`: <totales>.
   - `npm run build`: <success / detalle>.

   ### Backend
   - `python manage.py check`: <output resumido>.
   - `pytest --collect-only`: <N tests collected, errors>.
   - Slice: `<comando>`: <N passed> (o «⏭️ sin settings_test sqlite»).
   ```

   Si una superficie no se auditó (por `$ARGUMENTS`), omitir sus secciones.

2. **Commit del reporte:**
   ```bash
   git add audit-report.md
   ```
   ```bash
   git commit -m "docs: vulnerability audit report (<YYYY-MM-DD>)"
   ```

3. **Push + PR al primer push** (protocolo por sesión, tmpl §9). Las variables de la
   Fase 0 no persisten entre bloques bash (sólo el cwd), y dentro del worktree Claude
   rechaza el comando compuesto: se relee el registro. **La BASE del PR es la de la
   COORDENADA, nunca la default a secas**: un PR con `base=default` en un repo con
   release activa es por definición un candidato a release, y flipearía `pr_state` a
   `ambiguous` en el próximo `resolve-work-coordinate.sh` — receta canónica, la misma
   de [[pr-green]] Phase 2 / tmpl §0:
   ```bash
   bash ~/webapps/vps-ops-toolkit/scripts/maintenance/session-worktree.sh status
   ```
   De ahí salen `branch` y `base` (ese `base` YA es el de la coordenada: la release
   activa cuando la hay, la default sólo si no la hay). Se escriben **literales** —
   post-`EnterWorktree` no hay `$(...)` que los reconstruya:
   ```bash
   git push -u origin <branch literal>
   ```
   ```bash
   gh pr create --base <base literal> --fill --body "Sesión: <sesión>
   Intención: bumps patch+minor de dependencias

   <resumen de los commits>"
   ```
   Imprimí `PR URL: <url>` y **PARÁ** ahí — el merge es del operador o de
   `/merge-queue`, nunca de esta skill.

4. **Resultado final esperado:**
   - 1 a 3 commits nuevos en TU rama de sesión (worktree), `chore/<DDMMYYYY>-vuln-audit`.
   - Working tree limpio.
   - `audit-report.md` actualizado.
   - Rama pusheada + PR abierto (arriba); sin merge.

### Modo `--upgrade` — reporte final
Se escribe UNA vez al cierre del loop (`## Modo --upgrade` › Cierre), en español, con el
estilo de casa de los `audit-report.md` del fleet; sobrescribe el archivo existente en la
raíz del proyecto:

```markdown
# Auditoría de vulnerabilidades y dependencias — modernización secuencial

**Fecha:** <YYYY-MM-DD>
**Rama:** chore/<DDMMYYYY>-deps-upgrade
**Base:** <base> @ <sha7>
**Alcance:** patch + minor + majors, un commit por unidad con CI verde por commit · superficies: <ambas | frontend | backend>

## Resultado ejecutivo

| Métrica | Antes | Después |
|---|---|---|
| npm audit (C/H/M/L) | … | … |
| npm outdated (directas) | … | … |
| pip-audit (vulns / paquetes) | … | … |
| pip outdated (directas) | … | … |
| Unidades aplicadas / vacías / diferidas | — | A / V / D |

## Actualizaciones aplicadas

### Frontend
| Paquete directo | Antes | Después | Unidad | Commit |
|---|---|---|---|---|

### Backend
| Paquete directo | Antes | Después | Unidad | Commit |
|---|---|---|---|---|

## Rollback y excepciones
(pin-backs dentro de batches, ERESOLVE, `pip check`, unidades vacías, smoke local rojo)

## Actualizaciones mayores diferidas
| Paquete | Actual | Objetivo | Causa | Evidencia (run / log) | Commit de revert |
|---|---|---|---|---|---|

## Verificaciones ejecutadas
| Verificación | Resultado |
|---|---|
(smoke local por unidad + run de CI por commit, con ids)

## Evidencia temporal de la ejecución
(ledger completo: unidad · commit · run · veredicto · iteraciones · hora; snapshots en `/tmp/<proyecto>-*.json`)

## Acción operativa posterior al merge
- El deploy reconstruye dependencias mediante el broker tipado (`operation-deps pip|npm`) y después ejecuta el build; sin migraciones nuevas (`makemigrations --check` limpio en cada major de Django).
- Paquetes runtime-only que el CI no ejercita (`CI: no cubre`): <lista> — validar con `/deploy-and-check` tras el deploy.
- Majors diferidos: orden sugerido para la próxima corrida.
```

Commit `docs: dependency upgrade report (<YYYY-MM-DD>)` → `git push` → esperar su CI (el DoD
de sesión es CI verde en HEAD) → `PR URL: <url>` y **PARÁ**.

## Idempotencia
- Corrida default: siempre re-escanea y re-muestra el plan; como no escribe nada, repetirla es gratis.
- En `--apply`, si no hay vulns ni outdated relevantes:
  - No hacer commits de deps.
  - Generar igual el `audit-report.md` indicando "No updates applicable" en cada sección.
  - Hacer el commit del reporte solo si su contenido cambió respecto al existente.
- `--upgrade` reanuda desde git, no desde memoria: (1) reutiliza worktree/rama/PR
  `deps-upgrade` si el PR sigue `OPEN` (o no existe aún); (2)
  `git log --format='%h %s' <BASE_SHA literal>..HEAD` reconstruye el ledger —
  `chore(deps):` = aplicada, `revert(deps):` = diferida, `fix(deps):` = iteración; (3)
  re-escanea outdated en HEAD → las unidades restantes; (4) los paquetes con `revert(deps):`
  en el log, los listados en `## Actualizaciones mayores diferidas` del `audit-report.md`
  commiteado y los de `/tmp/<proyecto>-deps-upgrade-deferred.txt` se **saltan** (para
  reintentar uno, el operador borra su fila y lo pide); (5) si el CI de HEAD está
  pending/rojo al reanudar, primero se resuelve ese veredicto (Pasos 6–7); (6) tree sucio
  limitado a archivos de deps (unidad a medias) ⇒ ⏸️ con las dos salidas
  (`git checkout -- <archivos literales>` o commitear) — nunca se descarta solo.

## Ejemplos de invocación
- `/vuln-audit` — auditar backend + frontend y mostrar el plan (read-only).
- `/vuln-audit frontend` — solo npm, solo plan.
- `/vuln-audit backend` — solo pip, solo plan.
- `/vuln-audit --apply` — aplicar patch+minor del plan en ambas superficies (commits separados, PR al final).
- `/vuln-audit backend --apply` — aplicar solo en Python.
- `/vuln-audit --upgrade` — modernización secuencial de ambas superficies (un PR, un commit por unidad, CI verde por commit).
- `/vuln-audit frontend --upgrade` — sólo npm; una corrida posterior `backend --upgrade` reutiliza el mismo PR.

---

## Acciones disponibles

Tras el reporte del plan (corrida default, sin flags), si la sesión es
interactiva y NO hubo flags explícitos (reglas de gating de
[[_output-protocol]] §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| Aplicar patch+minor del plan (commits separados) (Recommended) | aplica los bumps del plan respetando pins, verifica (build / check / collect-only) y deja 1–3 commits en tu worktree + PR abierto, sin merge | `/vuln-audit --apply` |
| Modernizar todo secuencialmente (`--upgrade`) | patch → minor → cada major en su commit, un push por commit y CI verde antes de seguir; majors rojos revertidos y diferidos — horas, N runs de CI, PR abierto sin merge | `/vuln-audit --upgrade` |
| Sólo backend / sólo frontend | re-corre la auditoría acotada a una superficie | `/vuln-audit backend` · `/vuln-audit frontend` |
| Evaluar los majors saltados (plan detallado por paquete) | analiza breaking changes, esfuerzo y orden sugerido de cada major — no aplica nada | análisis en la respuesta (read-only) |

## Output final

Reportar siguiendo [[_output-protocol]]. Plantilla específica de `/vuln-audit`.

**Corrida default (report-first):** el veredicto acompaña a la tabla del plan
de Fase 3 (que es el cuerpo del reporte):

```markdown
🟢 vuln-audit OK — plan de bumps listo (read-only, nada escrito)

| Dimensión | Estado | Detalle |
|---|---|---|
| Frontend — npm audit | ✅ | C/H/M/L: <totales>, N outdated |
| Backend — pip-audit | ✅ | N vulns en M paquetes, K outdated |
| Plan de bumps | ✅ | X patch+minor aplicables, Y majors (K unidades para --upgrade) |
| Escrituras | ✅ | ninguna (default report-first) |
```

**Corrida `--apply`:**

```markdown
🟢 vuln-audit OK
✨ Todo en orden — no hay acciones pendientes.

| Dimensión | Estado | Detalle |
|---|---|---|
| Working tree limpio | ✅ | git status sin cambios al iniciar |
| Branch resuelta | ✅ | git-branch-protocol aplicado |
| Frontend — npm audit | ✅ | C/H/M/L: <antes> → <después>, build OK |
| Frontend — patch+minor | ✅ | N bumps aplicados, sin --force, sin ERESOLVE |
| Backend — pip-audit | ✅ | N vulns: <antes> → <después>, pins respetados |
| Backend — patch+minor | ✅ | N bumps aplicados, check + collect-only OK |
| audit-report.md | ✅ | reporte generado, 1–3 commits en el worktree |
| PR | ✅ | #<n> — <url>, sin merge |
```

**Corrida `--upgrade` — intermedia** (cada turno que termina con CI en vuelo):

```markdown
⏸️ vuln-audit --upgrade — CI en vuelo (unidad <k>/<K>: <nombre>)
👁️ `CI-MONITOR [<repo>#<n> upgrade u<k>]` montado (task de fondo) — al llegar su notificación: `gh pr checks <n> --json name,state,bucket` y seguir el loop.

| # | Unidad | Paquetes (antes → después) | Commit | CI run | Iter. fix | Resultado |
|---|---|---|---|---|---|---|
| 1 | frontend lockfile | transitivos (npm audit fix) | <sha7> | <id> ✅ | 0 | ✅ aplicada |
| 2 | frontend patch (12) | axios 1.7.2 → 1.7.9, … | <sha7> | <id> ⏳ | 0 | ⏸️ en vuelo |
| 3 | react 18.3.1 → 19.1.0 (+3) | pendiente | — | — | — | pendiente |
```

**Corrida `--upgrade` — final** (🟢 si todo ✅; 🟡 si hubo diferidos ⇒ celdas ⚠️; el ledger
completo va arriba como cuerpo y la tabla de dimensiones se agrega por tipo de unidad para
no superar 15 filas):

```markdown
🟡 vuln-audit --upgrade OK con <D> warning(s) — <A> unidades aplicadas, <D> majors diferidos, PR #<n> verde (sin merge)

| Dimensión | Estado | Detalle |
|---|---|---|
| Preflight | ✅ | CI presente (último run <T>), base verde, sin PR de deps, node <node> |
| Worktree / venv aislado | ✅ | ~/webapps/.wt/<repo>/deps-upgrade · backend/.venv propio · sin DB |
| Frontend lockfile / patch / minor | ✅ | 1 + 12 + 7 pkgs · runs <ids> ✅ |
| Frontend majors | ⚠️ | 4 ✅ · 1 diferido (react 19: tests de auth ⇒ fuera de alcance) |
| Backend patch / minor | ✅ / ⏭️ | 4 pkgs ✅ · minor: unidad vacía |
| Backend majors | ⚠️ | 2 ✅ · 1 diferido por constraint (Django <6.1: MySQL 8.0) |
| Vulns antes → después | ✅ | npm 0/2/3/1 → 0/0/0/0 · pip 3 → 0 |
| audit-report.md | ✅ | `docs: dependency upgrade report (<fecha>)` · run <id> ✅ |
| PR | ✅ | #<n> — <url>, CI verde en HEAD, sin merge |

## Next steps
- `/merge-queue` (operador) — drenar el PR #<n>
- (operador) majors diferidos: ver `## Actualizaciones mayores diferidas` en audit-report.md
- (operador, tras el deploy) `/deploy-and-check <proyecto>` — valida los paquetes runtime-only (`CI: no cubre`)
```

Si una superficie no aplicó (sin `package.json` o sin `requirements.txt`,
sin updates aplicables, o `$ARGUMENTS` excluyó la superficie), usar ⏭️.

Si ERESOLVE forzó rollback, build falló, pip-audit deja vulns remaining por
majors saltados, o algún verify (`manage.py check`, `pytest --collect-only`,
slice mínimo) falló → reemplazar ✅ por ⚠️/❌, omitir la línea ✨ y agregar
`## Next steps` con los paquetes pendientes (majors a evaluar, ERESOLVE
manual, etc.) y el `git push -u origin <rama>` + PR. En `--upgrade`, un preflight
que no pasa es `🚫 vuln-audit REFUSED (<razón>)` y un loop detenido por un rojo no
atribuible o por la base roja es ⏸️ con el ledger hasta esa unidad.
