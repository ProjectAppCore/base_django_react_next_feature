---
name: "migrate-project"
description: "Audita una migración per-project y recupera rollback/abort con autoridad root-owned. Apply/cutover están bloqueados fail-closed por P1-D; no migra un VPS completo."
---

## Qué hace esta skill

Audita la coordenada de una migración Django entre dos VPS del fleet
(origin → target) y recupera de forma cerrada una transacción histórica mediante
`--rollback` o `--abort-integrity-operation`. NO migra un VPS completo (para eso
usar `docs/migration-runbook.md`).

### Estado operativo actual — P1-D

`--apply` y `--cutover` están **bloqueados fail-closed antes del primer efecto**.
El inventario P1-D encontró writers post-`operation-join` que todavía dependen
del checkout o de paths/transferencias elegidos por el caller. El guard corre
antes de sourcear librerías, resolver proyectos, abrir SSH, leer credenciales,
crear receipts, clonar, hacer `rsync`, backup/restore/build, detener servicios o
tocar TLS. No existe flag ni variable de entorno para saltarlo.

Los únicos caminos vigentes son:

- `--check`: inventario read-only; **no** habilita ni recomienda `--apply`.
- `--rollback`: recovery de una migración que ya posee ledger schema 3 y tickets
  root-owned exactos en origin y target.
- `--apply --abort-integrity-operation`: terminaliza receipts antiguos exactos;
  es una acción de recovery, no el comienzo de un apply.

El diseño de los 20 pasos se conserva abajo como referencia para cerrar P1-D,
pero **no es un procedimiento ejecutable mientras este bloque esté vigente**.

**Casos de uso objetivo una vez reabierto P1-D:**
- Mover un proyecto de un VPS saturado a uno nuevo
- Desacoplar un cliente de un host compartido a un VPS dedicado
- Rebalancear el fleet por requisitos de hardware (memoria, disco)

## Host de invocación

El orquestador detecta automáticamente dónde corre:

| Host | Comportamiento |
|---|---|
| Dev workstation | Pivot rsync: origin → dev → target |
| Target VPS (destino) | **ABORTA**: no dispone de las identidades SSH/rsync del operador |
| Origin VPS (origen) | **ABORTA** (no migrar desde adentro del origin) |
| Otro VPS/host | **ABORTA**; nunca se trata un VPS intermedio como pivot |

La detección usa `resolve_server_alias` + `is_dev_machine` de `scripts/lib/bootstrap-common.sh`.

## Entorno requerido

**Para `--check`:**

- La entrada está activa en `projects.yml`, declara el origin real y usa
  `db: mysql`.
- Existen las credenciales canónicas del environment exacto del proyecto; el
  chequeo sólo valida forma/presencia y no imprime secretos.
- Dev workstation como host de invocación y conectividad al origin/target.

**Para recovery (`--rollback`):**

- Ledger exacto schema 3, regular, owner del caller, mode 0600 y un solo hardlink
  en `${XDG_STATE_HOME:-~/.local/state}/vps-ops-toolkit/integrity-operations/`.
- Generación runtime histórica exacta referenciada por el ticket todavía
  instalada en ambos hosts. El status de recovery carga esa generación por SHA;
  nunca cae a `current` ni a otra generación mutable.
- Tickets root-owned válidos en origin y target, brokers instalados y HEAD vivo
  exacto en ambos clones. El ledger local es sólo un índice; no autoriza efectos.

**Para recovery (`--apply --abort-integrity-operation`):**

- Directorio de receipts real, owner del caller, mode 0700.
- Cada receipt debe ser un archivo regular 0600, del caller, con un solo hardlink
  y contener exactamente un bearer `op_…` más newline.
- `vps-integrity` disponible en el host nombrado por el receipt y el alias target
  presente de forma única en el registry. No depende de `projects.yml`,
  credenciales, runtime env ni de las librerías sourceables del checkout.

**Pre-requisitos del diseño suspendido (no habilitan apply/cutover):**
- Bootstrap aplicado (`bootstrap.sh --apply` ya corrido — default desde
  2026-05-19 ya skipea Phase 4.5-4.9; el runtime del proyecto migrado
  llega por este script vía `FORCE_SINGLE_PROJECT`, no por bootstrap.sh)
- `vps-integrity` instalado y NOPASSWD accesible en ambos hosts; su ausencia o
  un JSON no evaluable abortan (fail-closed)
- Generación runtime root-owned del **commit completo** del toolkit instalada
  en origin y target, más el broker cerrado `vps-project-runtime-config` en
  ambos hosts y `vps-project-migration-data` en target
- Cuenta OS locked `vps-integrity-dbtest` instalada para que un dump no pueda
  convertir un meta-comando MySQL `\!` en ejecución root
- SSH alias funcional desde el host de invocación (Tailscale o `~/.ssh/config`)

**Pre-requisitos del diseño suspendido en projects.yml:**
- El proyecto existe en `projects.yml` con `server: <origin>` correcto
- `db: mysql`; cualquier otro engine aborta antes de la primera mutación
- Opcionalmente, declarar `extra_paths:` (dirs custom fuera de MEDIA_PATH) y `extra_packages:` (apt packages no-en-packages.list)

## Modos

| Modo | Qué hace | ¿Downtime? |
|---|---|---|
| `--check` | Ejecuta el preflight/inventario read-only. Emite aviso P1-D y no habilita mutaciones. | No |
| `--apply` | **REFUSED** por el guard P1-D antes de cualquier efecto; preserva receipts existentes. | No hay efecto |
| `--cutover --confirm-downtime` | **REFUSED** por el mismo guard antes de stop/delta/TLS; la confirmación no lo salta. | No hay downtime |
| `--rollback` | Autentica ledger contra tickets root-owned exactos y estado vivo; luego ejecuta exactamente rollback target → origin. DNS vuelve manualmente. | Reversión |
| `--apply --abort-integrity-operation` | Presenta sólo cada bearer exacto a su host, valida la respuesta terminal y elimina el receipt recién después del éxito autenticado. | Recovery |

**Flag reservado — `--accept-origin-drift`:** pertenece al diseño suspendido.
Mientras P1-D siga bloqueado no puede habilitar `--apply` ni modificar el
resultado del guard. En el diseño objetivo, el paso 1 verifica la integridad
del árbol de ORIGEN con `vps-integrity verify` antes de cualquier snapshot. Con
`drift`, `--apply` abortaría salvo que se pase este flag. No cubre `tamper` ni un
verify no evaluable: esos abortan siempre.

## Cómo invocar este skill

Gating ($output-protocol §4), en DOS niveles porque hay args posicionales:
(1) posicionales + modo vigente explícitos → directo, sin menú; (2) intención
clara de auditar → proponer `--check` en una línea y esperar confirmación;
(3) posicionales resueltos y sin modo → usar `--check`, que es la única entrada
normal vigente; (4) nunca en fleet/headless/cron. **Posicionales primero:** si
faltan `<proyecto>` y/o `<target_vps>`, pedirlos en TEXTO plano una sola vez
(son datos, no flags — no van en un picker).

**Q1 — Modo** (`multiSelect: false`):

| label | description | preview |
|---|---|---|
| --check (Recommended) | preflight read-only de los 20 pasos, sin mutaciones | `bash scripts/maintenance/migrate-project.sh --check <proyecto> <target_vps>` |

No ofrecer `--apply` ni `--cutover`: hoy siempre terminan en el guard P1-D y
mostrar una opción de continuación sería una recomendación falsa. `--rollback`
y `--apply --abort-integrity-operation` se ejecutan sólo cuando el operador los
tipea de forma explícita tras identificar una transacción previa; antes se lee
`docs/migrate-project-runbook.md`. Un `--apply`/`--cutover` explícito sin recovery
puede correrse únicamente para comprobar el fail-closed y se reporta como
`REFUSED`; nunca se propone un workaround.

## Flujo recomendado

```bash
# 1. Preflight (cualquier momento, sin riesgo)
bash scripts/maintenance/migrate-project.sh --check <proyecto> <target_vps>

# 2a. Sólo si existe un receipt de una corrida histórica que debe abortarse:
bash scripts/maintenance/migrate-project.sh --apply \
  --abort-integrity-operation <proyecto> <target_vps>

# 2b. Sólo si existe una migración histórica con ledger schema 3 + tickets válidos:
bash scripts/maintenance/migrate-project.sh --rollback <proyecto> <target_vps>
```

Un receipt ausente, ambiguo, inseguro, con payload extra o cuya respuesta remota
no coincida se preserva íntegro y el comando falla antes de continuar. Un ledger
ausente/tampered, una generación desconocida/alterada, un ticket que no coincida,
un hostname distinto o un HEAD rotado hacen fallar `--rollback` antes del primer
efecto. Si todo autentica, el orden de efectos es fijo: rollback del target y
después `origin-rollback` del origin.

---

## Diseño objetivo v1.3 suspendido — referencia, no procedimiento

Todo lo comprendido desde aquí hasta la sección activa **Rollback** describe el
diseño que se pretendía habilitar al cerrar P1-D. No ejecutar sus comandos a
mano, no saltar el guard y no sustituir sus writers por copias ad-hoc: hacerlo
rompería el vínculo causal que Integrity exige.

### Por qué clone era el primer paso (v1.1)

En v1 (orden original) el snapshot de DB+media+extras era el primer acto
en origin. Eso significaba que cualquier falla en la fase de target —
deploy key no autorizado, generación/broker ausente, paquete apt
inexistente — aparecía **DESPUÉS** de haber gastado 30-60 min en un
snapshot pesado que tal vez no se iba a usar.

El diseño v1.1 invertía el orden: **clone sería el primer acto de modificación**.
Failure modes operativos comunes (auth GitHub, repo no clonable) se
detectan en ≤10s, no después de un round-trip de varios GB de media.

Además, la lectura de credenciales DB ya no expone sus valores al shell: el
orquestador sólo comprueba presencia y el broker target lee el `.env` canónico,
ligando `DB_USER` al manifest root-owned. Ningún password viaja en argv/logs.

---

### Los 20 pasos previstos (v1.3; bloqueados)

Estos pasos son inventario de cierre. `migrate-project.sh` no entra hoy en ellos
desde `--apply` ni `--cutover`; el guard termina antes de sourcear librerías o
producir cualquiera de sus efectos.

### Paso 1 — Preflight SSH/Tailscale + repo version check + integridad del origen

Verifica conectividad SSH a origin y target. Después chequea que ambos
hosts tengan la versión del repo con `FORCE_SINGLE_PROJECT` implementado
en `scripts/lib/project-definitions.sh`. Si alguno tiene versión vieja,
aborta con instrucción de `git pull` (Hardening D v1.1).

Y cierra verificando la **integridad del árbol de origen** —
`sudo -n /usr/local/sbin/vps-integrity verify --project <proj> --tier stat
--offline --json` corrido EN el origen, read-only, gateado por
`[ -x /usr/local/sbin/vps-integrity ]`—, porque el paso 12 copia ese árbol tal
cual está: lo que nadie explique acá viaja al target y el cierre de la operación
`migrate` podría adoptarlo allí
como baseline legítimo, blanqueando el drift con la mudanza. Veredictos:
`ok` sigue · **sin baseline** aborta (no se puede afirmar que el árbol que
viajará esté íntegro, y nunca se siembra a ciegas) · `stale`
(baseline >90 días, sin drift) advierte y sigue · **`drift`** lista las rutas y
**aborta el `--apply`** salvo `--accept-origin-drift` · **`tamper`** y un verify
no evaluable abortan siempre el `--apply` (en `--check` se reportan). El
veredicto sale también en el summary final (`Integridad del origen: <estado>`).
Motor ausente, inaccesible o con salida malformada en cualquiera de los dos
hosts ⇒ abort duro antes de snapshot/runtime. No existe degradación silenciosa.

### Paso 2 — Target bootstrap status

Confirma que el target tiene `/etc/nginx/nginx.conf`, `/etc/letsencrypt/`,
y `certbot` instalado. Si no, aborta con instrucción de correr
`bootstrap.sh --apply` primero (default skipea Phase 4.5-4.9, que es lo
correcto para preparar un target de migración).

### Paso 3 — DNS pre-check

`dig +short A <domain>` resuelve el dominio del proyecto. Captura TTL y
avisa si > 300s (recomendación: bajar a 60s al menos 24h antes del
cutover).

### Paso 4 — Clone project repo en target (PRIMER acto de modificación)

```bash
FORCE_SINGLE_PROJECT=<proj> \
bash scripts/bootstrap/clone-projects.sh --apply
```

Usa el deploy key existente. `FORCE_SINGLE_PROJECT` permite clonar aunque
`projects.yml` aún diga `server: <origin>` (el flip de `server:` se hace
al final del paso 20).

**v1.1 insight:** movido desde paso 10 al inicio para fail-fast en auth
de GitHub (≤10s vs ≤30min después del snapshot).

Inmediatamente después fija el HEAD completo. Si el target está
`nobaseline`, el script se detiene antes de toda mutación posterior e imprime
el comando exacto, password-bound y nunca `sudo -n`:

```bash
tailscale ssh ryzepeck@<target>
sudo /usr/local/sbin/vps-integrity initial-authorize <proyecto> \
  --type migrate --target-commit <FULL_SHA> --ttl 15m
```

La autoridad es root-owned, expira y se consume una sola vez por el
`operation-begin` exacto. Con baseline existente no se solicita ni consume
autoridad inicial. Después se emite el runtime ticket 0600 de target ligado a
operación, host, commit, generación, plan y hashes. En origin se abre una
operación `migrate` independiente, audit-bound y ligada al HEAD que sigue
atendiendo producción; `origin-authorize` emite otro bearer 0600 host-bound y
esa operación se cierra antes del snapshot. Nunca se presenta el ticket de
target en origin ni al revés. El cierre durable de origin es la autoridad
causal que luego permite quiesce/retire/rollback sobre el set canónico de
units.

El binding CLI no es opcional: origin abre con `--migration-role origin` y sin
`--target-host`; target abre con `--migration-role target --target-host
<TARGET_VPS>`. El motor exige que `<TARGET_VPS>` sea exactamente el alias que
resuelve el bridge local. `integrity-operation.sh` rechaza `migrate`: sólo este
orquestador puede crear esas dos autoridades diferenciadas.

### Paso 5 — Read DB creds + payment keys DEL REPO (single source of truth)

```bash
grep -qE '^DB_USER=' \
  config/credentials/projects/<proj>/prod.env
grep -qE '^DB_PASSWORD=' \
  config/credentials/projects/<proj>/prod.env
```

Lectura local del repo (`config/credentials/projects/<proj>/<env>.env`),
que es el source-of-truth desde 2026-05-17 (Fase 4 de centralización de
credenciales). Sin SSH, sin file I/O remoto.

Si el archivo no existe → falla con instrucción de correr
`sync-credentials.sh capture --env=prod --apply --project=<proyecto>` primero
(usar `staging` cuando corresponda).

**v1.2 insight:** el repo ES la fuente de verdad. Antes (v1.1) leíamos
el `.env` runtime de origin via SSH; eso funcionaba pero ignoraba que el
repo ya tenía la misma información, y si live-vs-repo drift existía,
quién ganaba era ambiguo.

### Paso 6 — Credenciales target sin grants temporales

No edita `mysql-users.env`, no crea markers ni commitea secretos durante la
migración. La generación root-owned fija DB name/user; el password sólo se lee
del `.env` runtime target por el broker y nunca sale en argv.

### Paso 7 — Verificar `extra_packages` en target

```bash
dpkg-query -W ${EXTRA_PACKAGES[$proj]}
```

Los nombres se validan con una gramática cerrada. Si falta alguno, aborta antes
del snapshot e imprime el comando password-bound para que el operador lo
instale; no existe `apt-get` NOPASSWD genérico.

### Paso 8 — DB provisioning diferido

No ejecuta ningún checkout user-writable como root. La DB/user/grants exactos
se crean en paso 11 por `vps-project-migration-data prepare-db`, cuyo argv no
acepta SQL, path, user ni password.

### Paso 9 — Capture project envs en origin

```bash
FORCE_SINGLE_PROJECT=<proj> \
bash scripts/maintenance/capture-project-envs.sh --apply --out=<dir>
```

Captura `backend/.env`, `frontend/.env*` y variantes underscore
(`.env_development`, `.env_production`). Detecta `db.sqlite3` huérfano
y emite warn (decisión manual si copiarlo).

### Paso 10 — Transfer envs origin → target (lightweight, <100KB)

`rsync` normal, siempre `origin → dev → target`. Un `.env` que no sea legible
por su owner operativo aborta; no se reabre con `sudo rsync`/`sudo cat`.

### Paso 11 — Restore project envs en target

```bash
FORCE_SINGLE_PROJECT=<proj> \
bash scripts/maintenance/restore-project-envs.sh --apply --from=<dir>
```

Después invoca el broker `prepare-db`. Este deriva identificadores desde la
generación root-owned, valida `DB_USER` exacto y sólo concede ese user sobre esa
DB. La creación privilegiada usa SQL generado internamente; ningún SQL del
caller cruza el boundary.

Después detecta conflictos de Redis DB slot y emite warn con el comando
sed exacto (NO muta automáticamente — bugs de slot son silenciosos y
catastróficos).

### Paso 12 — Snapshot DB + media + extras en origin (HEAVY)

```bash
FORCE_SINGLE_PROJECT=<proj> \
bash scripts/maintenance/backup-mysql-and-media.sh
```

Genera (gracias a las extensiones del schema 2026-05-18):
- `db/<proj_db>.sql.gz`
- `apps/<proj>-<media_basename>.tar.gz`
- `apps/<proj>-extras.tar.gz` si `EXTRA_PATHS[$proj]` no vacío
- `SHA256SUMS`

Es el paso pesado del flow. Tiempo proporcional a media + DB size
(~30s mimittos, ~5min projectapp).

No selecciona `ls -t`: crea un root único por corrida, parsea el path exacto
emitido por el backup y lo ata al ledger 0600 junto con SHA256 del manifest,
operation id, HEAD del proyecto y commit del toolkit. Exige `SHA256SUMS`,
`gzip` válido y SQL descomprimido no vacío.

### Paso 13 — Transfer snapshot origin → target (HEAVY)

`rsync` del snapshot exacto a un inbox fijo derivado sólo del proyecto:
`~/.local/state/vps-ops-toolkit/migration-data/<proj>/snapshot`. Verifica
manifest, set de archivos, checksums y gzip en origin, pivot y target. El
broker no acepta un path elegido por el caller.

### Paso 14 — Restore cerrado de DB + media + extras en target

```bash
bash scripts/maintenance/deploy-project-migration-data.sh \
  --restore-snapshot --project=<proj> --expected-commit=<FULL_TOOLKIT_SHA>
python3 scripts/maintenance/restore-project-migration-files.py \
  restore <proj> <FULL_TOOLKIT_SHA>
```

El broker vuelve a abrir el dump una sola vez con `O_NOFOLLOW`, revalida el
hash sobre ese mismo inode, limita tamaño comprimido/descomprimido y corre el
cliente MySQL vía `runuser -u vps-integrity-dbtest`; así un `\! command` del
dump nunca corre como root. Se autentica con el user MySQL limitado del
proyecto y exige consultas post-import (`tables > 0`, `django_migrations > 0`).
El receipt root-owned liga ticket/generación/snapshot/delta. Media/extras se
extraen sin privilegios, sólo bajo paths declarados en el commit, rechazando
links, devices, traversal y bombas de compresión.

### Paso 15 — venv + pip + frontend build + systemd

```bash
FORCE_SINGLE_PROJECT=<proj> \
bash scripts/bootstrap/setup-project-environments.sh --apply
```

Crea venv, instala dependencias, builds frontend (si aplica), corre
`collectstatic` y deploya systemd units. **Deja services STOPPED** —
origin sigue sirviendo tráfico.

### Paso 16 — Stage runtime canónico mediante broker

`deploy-project-runtime-config.sh --apply --expected-commit=<SHA>
--leave-nginx-disabled --leave-timers-disabled` presenta el bearer 0600 y pide
al executor root-owned el plan exacto. El manifest incluye socket, gunicorn,
huey, scheduler, frontend, additional services, timers, drop-ins y site. El
stage verifica hashes y deja **todas** las applications/timers y nginx
inactive/disabled; además guarda un snapshot completo para rollback.

### Paso 17 — Deploy nginx site para el proyecto (v1.3 NEW, NO enable todavía)

El mismo broker deja el payload en `sites-available` y prueba que no exista el
symlink en `sites-enabled`. No hay `sudo install` ni `ln -sf` directo.

### Paso 18 — Propagar project_skills

Sólo corre `sync-shared-skills.sh --check`. Los cambios versionados de skills
deben llegar por su PR/worktree normal; la migración no los reescribe.

### Paso 19 — Atestar warm spare y cerrar Integrity

Valida que el plan TLS commit-bound exista, pero no emite certificado ni activa
nginx. Exige ticket target `staged` sin transición pendiente, ledger con
snapshot exacto y cierre causal ya probado del ticket independiente de origin;
luego cierra la operación `migrate` de target. Cada `operation-end` produce su
tombstone/companion y baseline exactos; un cierre rechazado conserva el bearer
para `--resume-integrity-operation` y nunca cae a `accept` o `baseline` manual.

### Paso 20 — CUTOVER (ventana de downtime)

Sólo se ejecuta con `--cutover --confirm-downtime`:

0. **SKIP exacto**: antes del downtime exige ledger 0600, tombstone/companion,
   baseline+HEAD+drift, runtime ticket/generación/hashes, snapshot en
   origin+target, los dos ticket refs host-bound, restore de media/extras y
   consulta DB exactos. Cualquier gap aborta; nunca cae a heurísticas de
   presencia ni reejecuta 1-19.
1. **Quiesce** en origin mediante `origin-quiesce`: el broker captura de forma
   durable el estado enabled/active exacto y detiene todas las application
   units y timers del manifest (socket, gunicorn, huey, scheduler, frontend,
   additional). No acepta un nombre de unit del caller.
2. **Final dump** sin sudo mediante `export-project-migration-delta.py`: valida
   DB name/user/env contra la generación root-owned, ejecuta `mysqldump` con el
   principal MySQL limitado del proyecto, comprime con cap/timeout y publica
   checksum+fsync en un path fijo. Después rsync al inbox fijo e
   `import-delta` con el sandbox OS y el mismo principal limitado.
3. **App started** en target por broker; timers y site siguen apagados.
4. **Integridad ya cerrada**: la operación target `migrate`, abierta
   después del clone y antes del resto de las mutaciones, debe haber terminado
   al completar el warm spare (paso 19). `operation-end` exige el mismo bearer,
   HEAD/target, Git limpio, scope y sensores; si era el primer baseline escanea
   el candidato completo antes de firmarlo. Un cierre pendiente bloquea el
   cutover y se recupera explícitamente con `--resume-integrity-operation`; no
   existe fallback a `baseline --if-missing`. La operación independiente de
   origin también debe tener tombstone/companion/baseline exactos para el HEAD
   que autorizó el ticket; su bearer no autoriza al target.
5. **DNS flip guidance** interactivo. Dominio/IP deben ser canónicos.
6. **Dig loop duro** hasta resolver exactamente el target; timeout revierte
   target y reactiva origin.
7. **TLS** por broker root-owned; sólo usa dominios/options del manifest.
8. **Timers activos**, después **site activo**, en ese orden monotónico.
9. **Gates duros**: HTTPS root 2xx/3xx, `/api/health/` 2xx y ticket final
   `site-active`, sin pending.
10. Recién entonces ejecuta `origin-retire`, que deshabilita y detiene el set
    canónico completo, y hace un único flip surgical de `projects.yml`. Un
    fallo previo deja `cutover-pending` y dispara `origin-rollback`, que
    restaura exactamente el snapshot durable.

No existe cleanup de `mysql-users.env`: el flujo nunca lo modificó.

---

## Edge cases conocidos

### Twin staging co-ubicado

Si el proyecto tiene un staging twin en el mismo VPS (caso `kore_project` + `kore_project_staging` en `srv571894`), correr la skill **dos veces** — una por environment. NO hay modo bulk. El operador decide el orden (recomendación: staging primero, validar, después prod).

### `db.sqlite3` huérfano

Si origin tiene `backend/db.sqlite3` además de MySQL (caso `projectapp`), la skill emite warn pero NO copia automáticamente. Casos:
- Si es runtime de silk → ignorar (silk lo regenera en target)
- Si tiene state real → copiar manual: `scp <origin>:/home/ryzepeck/webapps/<proj>/backend/db.sqlite3 <target>:/home/ryzepeck/webapps/<proj>/backend/`

### Redis DB slot conflict

Si el `redis_db: N` del proyecto colisiona con otro proyecto ya residente en target, la skill emite warn pero NO muta. El operador decide:
- Reasignar slot del proyecto migrado (sed sobre `HUEY_REDIS_URL` en `.env`)
- Reasignar slot del otro proyecto (más invasivo)

### Frontend port collision

Si el proyecto tiene frontend service (mimittos puerto 3002, tuhuella 3001, xpandia 3003, vastago 3004) y el puerto está tomado en target, la skill emite warn en paso 2 (preflight). El operador reasigna manualmente en el `frontend/.env` antes de continuar.

### Pago en producción (downtime impacta cobros)

Para proyectos con Wompi/Stripe/PayPal PROD activos, acordar la ventana y bajar
el TTL con antelación. El broker emite/valida TLS después de que DNS llega al
target y antes de activar timers/site; cualquier falla revierte runtime/origin.

---

## Rollback

`--rollback` existe **únicamente** para recuperar una migración previamente
emitida. No crea tickets, no renueva operaciones y no sirve para iniciar una
migración nueva. Puede ejecutarse incluso si el `server:` ya apunta al target o
la entrada quedó inactive/ausente, porque obtiene el origin del ledger antes de
cargar `projects.yml`.

```bash
bash scripts/maintenance/migrate-project.sh --rollback <project> <target_vps>
```

Antes del primer efecto exige todo lo siguiente:

1. Ledger schema 3 estricto con `origin_vps`, `origin_hostname`,
   `origin_project_commit`, toolkit/project SHA, operation refs y ticket refs.
   Su owner/mode/links/formato se validan, pero el archivo es caller-owned y por
   eso **no se considera autoridad**.
2. Hostname vivo de origin y target igual al registry; HEAD vivo en ambos clones
   igual al SHA exacto ligado por el ledger.
3. `origin-ready-status` del broker root-owned del origin y `ticket-status` del
   broker root-owned del target. Cada documento debe corresponder al commit
   histórico exacto del toolkit, ticket/opref, proyecto, rol, host y plan
   digest. Esos status cargan sólo la generación autenticada por SHA del ticket,
   aun si `current` ya rotó; generación ausente/tampered/unknown falla sin
   fallback.

Sólo después ejecuta, en este orden exacto:

1. Target `rollback`: restaura bytes/modes de systemd+nginx, estados
   enabled/active, symlink previo, `daemon-reload` y nginx test/reload.
2. Origin `origin-rollback`: restaura el estado enabled/active exacto de todas
   las application units y timers canónicos. El ticket target no sirve aquí.
3. Actualiza de forma atómica el ledger a `rolled-back` e imprime la instrucción
   manual para DNS flip back.

Ledger ausente o alterado, selector runtime rotado sin la generación histórica,
ticket/status no coincidente, host distinto o SHA vivo distinto ⇒ exit 2 antes
de target rollback y antes de origin rollback.

Un ticket sin snapshot termina el rollback como no-op `rolled-back`; no queda
pendiente indefinidamente. Los tickets no terminales expiran a los siete días.
Los terminales (`site-active`, `retired`, `rolled-back`) conservan 24 h de
autoridad de recuperación. Otra migración puede archivarlos de inmediato, pero
sólo sin una transición pending; un ticket activo o pending nunca se reemplaza.

Datos escritos en target durante la ventana histórica de cutover pueden perderse.
El operador hace DNS flip back en el panel del provider después de verificar que
el origin quedó restaurado.

## Abort explícito de una operación histórica

Si existe un bearer escrowed que no debe reanudarse:

```bash
bash scripts/maintenance/migrate-project.sh --apply \
  --abort-integrity-operation <project> <target_vps>
```

El dispatcher corre antes del guard P1-D y antes de sourcear cualquier librería.
Valida **todos** los receipts encontrados antes de presentar el primero, para no
terminalizar sólo media pareja. Admite el receipt target exacto y, como máximo,
un receipt origin con alias canónico. La respuesta schema 2 de
`operation-abort` debe probar el mismo proyecto y `operation_ref`, más un estado
terminal permitido (`aborted`, `already-absent` o `already-closed`). Sólo
entonces elimina y fsync el receipt local. Cualquier mismatch conserva la
capability para triage; nunca intenta adivinarla desde `status`.

---

## Verificación end-to-end

### `--check` smoke test (runnable hoy)

```bash
bash scripts/maintenance/migrate-project.sh --check <project> <target_vps>
```

Usar un target distinto al `server:` declarado del proyecto. Esperado: aviso
`P1-D closure=blocked`, inventario read-only y cero efectos. Los errores de
coordenada, motor, credenciales o conectividad siguen siendo fallos reales del
preflight.

### Candidato futuro, no autorizado hoy: `mimittos_project`

Era el caso más simple del set analizado: sin twin staging, sin `extra_paths`,
sólo `extra_packages: [ffmpeg]`. Esta observación **no autoriza** `--apply`; debe
reevaluarse con datos vivos cuando P1-D esté cerrado y el guard sea retirado por
un cambio versionado y testeado.

---

## Acciones disponibles

No hay continuación mutante normal mientras P1-D siga bloqueado. Tras un
`--check`, reportar el inventario y detenerse: no ofrecer `--apply` ni cutover.

Tras un `--check` exitoso:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| Cerrar sin mutar (Recommended) | P1-D sigue bloqueado; conservar el reporte como inventario | — |

Sólo si el reporte o el operador identifican estado histórico concreto, mostrar
el comando exacto correspondiente **sin ejecutarlo por inferencia**:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| Mostrar abort exacto | terminaliza sólo receipts históricos exactos; requiere intención explícita | `bash scripts/maintenance/migrate-project.sh --apply --abort-integrity-operation <proj> <target>` |
| Mostrar rollback exacto | exige ledger schema 3 y tickets root-owned históricos; requiere intención explícita | `bash scripts/maintenance/migrate-project.sh --rollback <proj> <target>` |

`--apply` y `--cutover` no son opciones disponibles. Si se invocan de forma
explícita, se comprueba y reporta el fail-closed; no se intenta continuar.

## Output final

Reportar siguiendo $output-protocol. Plantilla específica de esta skill
(migra UN proyecto origin → target; el veredicto nombra ambos hosts):

🟢 migrate-project recovery <proj> <origin> → <target> OK — rollback/abort autenticado y terminal
🟡 migrate-project <proj> <origin> → <target> OK con N warning(s) — ≥1 ⚠️ (blue-green, redis slot, port)
🔴 migrate-project <proj> <origin> → <target> — N error(es), revisar arriba — ≥1 ❌
⏸️ migrate-project <proj> <origin> → <target> — pausa manual pendiente — DNS flip / confirmar downtime
🚫 migrate-project <proj> <origin> → <target> — REFUSED (P1-D post-join bloqueado antes del primer efecto)
⏭️ migrate-project <proj> <origin> → <target> — N/A o saltado — modo `--check` (dry-run)

| Dimensión | Estado | Detalle |
|---|---|---|
| Preflight (SSH + bootstrap + DNS) | ✅ | conectividad origin/target, target listo, TTL DNS |
| Boundary P1-D | 🚫/⏭️ | apply/cutover detenidos antes de sources/SSH/credenciales/efectos |
| Ledger recovery | ✅/⏭️ | schema 3 estricto; origin/hostname/SHA cargados antes de projects.yml |
| Autoridad root-owned | ✅/⏭️ | tickets exactos de ambos hosts + generación histórica sin fallback |
| Estado vivo | ✅/⏭️ | registry hostname y HEAD exactos en origin/target |
| Efectos rollback | ✅/⏭️ | exactamente target rollback → origin rollback |
| Receipt abort | ✅/⏭️ | capability exacta; respuesta terminal validada antes de consumirla |

Sustituciones por modo/estado:
- `--check` → veredicto ⏭️; cada dimensión reporta el plan (sin mutar).
- `--apply`/`--cutover` → 🚫 P1-D; confirmar explícitamente que no hubo SSH,
  clone, operation begin/join/renew, rsync, backup, restore, build, stop ni TLS.
- `--rollback` autenticado y completado → 🟢; DNS flip back sigue manual.
- `--abort-integrity-operation` autenticado y completado → 🟢; enumerar qué
  receipts se retiraron. Un receipt inválido/mismatch → 🔴 y se preserva.

## Next steps

- Tras `--check`: cerrar sin mutar y conservar el resultado como inventario P1-D.
- Si existe un receipt antiguo: el operador puede tipear el comando de abort
  exacto mostrado arriba; no borrar el archivo manualmente.
- Si existe una migración histórica post-cutover: el operador puede tipear el
  rollback exacto, verificar services/HTTPS del origin y después revertir DNS
  manualmente.
- No editar `server:` a mano, no hacer stops parciales y no fabricar/reparar un
  ledger o ticket. Un recovery rechazado requiere triage de la evidencia.
- Para reabrir migraciones nuevas se necesita un cambio versionado que cierre
  todos los writers P1-D, retire/modifique el guard y agregue sus killer tests.

---

## Suspensión de proyecto

La suspensión ya no forma parte de este runbook de migración ni se ejecuta con
un checklist ad-hoc. Usar $project-lifecycle con action `suspend`: atribuye
units/timers al proyecto exacto, crea el snapshot final, apaga todo trabajo
recurrente, actualiza `projects.yml` y exige una decisión TLS explícita. La misma
skill maneja `activate`; la migración conserva su flujo propio de warm
spare/cutover/rollback.
